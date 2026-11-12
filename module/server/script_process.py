# This Python file uses the following encoding: utf-8
# @author runhey
# 脚本进程
# github https://github.com/runhey
import asyncio
import multiprocessing
from asyncio import QueueEmpty, CancelledError, sleep
from enum import Enum

from module.logger import logger
from module.server.config_manager import ConfigManager
from module.server.script_websocket import ScriptWSManager


class ScriptState(int, Enum):
    INACTIVE = 0
    RUNNING = 1
    WARNING = 2
    UPDATING = 3


class ScriptProcess(ScriptWSManager):

    def __init__(self, config_name: str) -> None:
        super().__init__()
        if config_name not in ConfigManager.all_script_files():
            raise FileNotFoundError(f'{config_name}.json not found')
        self.config_name = config_name  # config_name
        self.log_pipe_out = None
        self.log_pipe_in = None
        self.state_queue = None
        self._init_ipc()
        self.state: ScriptState = ScriptState.INACTIVE
        self._process = None

    def _init_ipc(self) -> None:
        self.log_pipe_out, self.log_pipe_in = multiprocessing.Pipe(False)
        self.state_queue = multiprocessing.Queue()

    def close_ipc(self) -> None:
        """关闭并释放子进程通信管道与状态队列。"""
        for pipe_conn in (self.log_pipe_out, self.log_pipe_in):
            if pipe_conn is not None:
                try:
                    pipe_conn.close()
                except Exception:
                    pass
        self.log_pipe_out = None
        self.log_pipe_in = None
        if self.state_queue is not None:
            try:
                self.state_queue.close()
                self.state_queue.cancel_join_thread()
            except Exception:
                pass
            self.state_queue = None

    @staticmethod
    def _extract_log_dedup_key(log: str) -> str | None:
        text = str(log).strip()
        if not text:
            return None
        parts = str(log).split('|', 2)
        if len(parts) != 3:
            return None
        level, timestamp, message = [part.strip() for part in parts]
        if not level or not timestamp or not message:
            return None
        return message

    async def start(self):
        if self._process is not None:
            if self._process.is_alive():
                logger.warning(f'Script {self.config_name} is already running and first stop it')
            await self.stop()
        self.close_ipc()
        self._init_ipc()
        self.state = ScriptState.RUNNING
        await self.broadcast_state({"state": self.state})
        self._process = multiprocessing.Process(
            target=func,
            args=(self.config_name, self.state_queue, self.log_pipe_in,),
            name=self.config_name,
            daemon=True,
        )
        self._process.start()

    async def stop(self):
        self.state = ScriptState.INACTIVE
        await self.broadcast_state({"state": self.state})
        proc = self._process
        self._process = None
        if proc is None:
            logger.warning(f'Script {self.config_name} process is removed')
            self.close_ipc()
            return
        try:
            if proc.is_alive():
                proc.terminate()
                await asyncio.to_thread(proc.join, 3.0)
                if proc.is_alive():
                    logger.warning(f'Script {self.config_name} did not exit cleanly, forcing kill')
                    if hasattr(proc, 'kill'):
                        proc.kill()
                    await asyncio.to_thread(proc.join, 1.0)
            else:
                logger.warning(f'Script {self.config_name} is not running')
        finally:
            if hasattr(proc, 'close'):
                try:
                    proc.close()
                except Exception:
                    pass
            self.close_ipc()

    async def coroutine_broadcast_state(self):
        try:
            while self.state != ScriptState.INACTIVE:
                await sleep(0.1)
                queue = self.state_queue
                if queue is None:
                    await sleep(0.5)
                    continue
                try:
                    if queue.empty():
                        proc = self._process
                        if proc is not None and not proc.is_alive() and self.state == ScriptState.RUNNING:
                            await sleep(0.1)
                            if not queue.empty():
                                continue
                            exit_code = getattr(proc, 'exitcode', None)
                            self.state = ScriptState.WARNING if exit_code not in (0, None) else ScriptState.INACTIVE
                            await self.broadcast_state({"state": self.state})
                            break
                        await sleep(0.5)
                        continue
                    data = queue.get_nowait()
                    if not data:
                        await sleep(0.2)
                        continue
                    if 'state' in data and data['state'] == ScriptState.WARNING:
                        self.state = ScriptState.WARNING
                    await self.broadcast_state(data)
                    if self.state == ScriptState.WARNING:
                        break
                except QueueEmpty as e:
                    logger.warning(f'QueueEmpty: {e}')
                    await sleep(0.5)
                    continue
                except (OSError, ValueError, EOFError):
                    await sleep(0.5)
                    continue
                except Exception as e:
                    logger.error(f'Error: {e}')
                    await sleep(0.5)
                    continue
        except CancelledError:
            logger.warning(f'{self.config_name} state coroutine is cancelled')
            return

    async def coroutine_broadcast_log(self):
        try:
            previous_log_key = None  # 缓存上一条正文日志，用于相邻重复去重
            while True:
                pipe_out = self.log_pipe_out
                if pipe_out is None or getattr(pipe_out, 'closed', False):
                    if self.state in (ScriptState.INACTIVE, ScriptState.WARNING):
                        break
                    await sleep(0.5)
                    continue
                await sleep(0.05)
                try:
                    if not pipe_out.poll():
                        if self.state in (ScriptState.INACTIVE, ScriptState.WARNING):
                            break
                        await sleep(0.25)
                        continue
                    log = pipe_out.recv()
                    if not str(log).strip():
                        continue
                    current_log_key = self._extract_log_dedup_key(log)
                    if current_log_key is not None:
                        if current_log_key == previous_log_key:
                            continue
                        previous_log_key = current_log_key
                    else:
                        previous_log_key = None
                    await self.broadcast_log(log)
                except (EOFError, OSError, ValueError) as e:
                    if self.state in (ScriptState.INACTIVE, ScriptState.WARNING):
                        break
                    await sleep(0.5)
                    logger.warning(f'Pipe/EOFError: {e}')
                    continue
                except Exception as e:
                    logger.error(f'Log Error: {e}')
                    await sleep(0.5)
                    continue
        except CancelledError:
            logger.warning(f'{self.config_name} log coroutine is cancelled')
            return


def func(config: str, state_queue: multiprocessing.Queue, log_pipe_in) -> None:

    def start_log() -> None:
        try:
            from module.logger import set_file_logger, set_func_logger
            set_file_logger(name=config)
            set_func_logger(log_pipe_in.send)
        except Exception as e:
            logger.exception(f'Start log error')
            logger.error(f'Error: {e}')
            raise
    start_log()
    import time
    try:
        # while 1:
        #     time.sleep(1)
        #     logger.info(f'Script {config} is running')
        #     state_queue.put({"state": ScriptState.RUNNING})
        from script import Script
        script = Script(config_name=config)
        script.state_queue = state_queue
        script.loop()
    except SystemExit as e:
        logger.info(f'Script {config} process exit')
        logger.error(f'Error: {e}')
        state_queue.put({"state": ScriptState.WARNING})
        time.sleep(0.1)
        exit(-1)
    except Exception as e:
        logger.exception(f'Run script {config} error')
        logger.error(f'Error: {e}')
        try:
            state_queue.put({"state": ScriptState.WARNING})
            time.sleep(0.1)
        except Exception:
            pass
        raise
    finally:
        try:
            from module.utils.power_manager import PowerManager
            PowerManager.release_all()
        except Exception:
            pass


if __name__ == '__main__':
    p = ScriptProcess('oas1')
    p.start()
    from time import sleep
    sleep(10)
    logger.info(p._process.exitcode)
