# This Python file uses the following encoding: utf-8
# @author runhey
# 脚本进程
# github https://github.com/runhey
import sys, os
import signal
import multiprocessing
import logging
from queue import Empty as QueueEmpty
from asyncio import CancelledError, sleep
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
        self.log_queue = multiprocessing.Queue()
        self.state_queue = multiprocessing.Queue()
        self.state: ScriptState = ScriptState.INACTIVE
        self._process = None

    async def start(self):
        self.state = ScriptState.RUNNING
        await self.broadcast_state({"state": self.state})
        if self._process:
            logger.warning(f'Script {self.config_name} is initialized')
        if self._process and self._process.is_alive():
            logger.warning(f'Script {self.config_name} is already running and first stop it')
            self.stop()
        self._process = multiprocessing.Process(target=func,
                                                args=(self.config_name, self.state_queue, self.log_queue,),
                                                name=self.config_name,
                                                daemon=True
                                                )
        self._process.start()

    async def stop(self):
        self.state = ScriptState.INACTIVE
        await self.broadcast_state({"state": self.state})
        if self._process is None:
            logger.warning(f'Script {self.config_name} process is removed')
            return
        if not self._process.is_alive():
            logger.warning(f'Script {self.config_name} is not running')
            return
        self._process.terminate()
        self._process.join(timeout=0.7)
        if self._process.is_alive():
            logger.error(f'Script {self.config_name} subprocess terminate failed')
            self._process.kill()
        self._process = None

    async def coroutine_broadcast_state(self):
        try:
            while 1:
                if self.state == ScriptState.INACTIVE:
                    await sleep(1)
                    continue
                await sleep(0.1)
                try:
                    if self.state_queue.empty():
                        await sleep(1)
                        continue
                    data = self.state_queue.get_nowait()
                    if not data:
                        await sleep(0.5)
                        continue
                    if 'state' in data and data['state'] == ScriptState.WARNING:
                        self.state = ScriptState.WARNING
                    await self.broadcast_state(data)
                except QueueEmpty as e:
                    logger.warning(f'QueueEmpty: {e}')
                    await sleep(0.5)
                    continue
                except Exception as e:
                    logger.error(f'Error: {e}')
                    continue
        except CancelledError as e:
            logger.warning(f'{self.config_name} state coroutine is cancelled')
            return

    async def coroutine_broadcast_log(self):
        try:
            while 1:
                if self.state == ScriptState.INACTIVE:
                    await sleep(1)
                    continue
                try:
                    batch = []
                    # 批量取日志，降低空转；单次最多取 50 条
                    while len(batch) < 50:
                        try:
                            batch.append(self.log_queue.get_nowait())
                        except QueueEmpty:
                            break
                    if batch:
                        # 每条日志都是独立 JSON 记录，分别广播，方便前端解析
                        for log_record in batch:
                            await self.broadcast_log(log_record)
                    else:
                        await sleep(0.05)
                except CancelledError:
                    raise
                except Exception as e:
                    logger.error(f'Log broadcast error: {e}')
                    await sleep(0.5)
                    continue
        except CancelledError as e:
            logger.warning(f'{self.config_name} log coroutine is cancelled')
            return


def func(config: str, state_queue: multiprocessing.Queue, log_queue: multiprocessing.Queue) -> None:
    def signal_handler(signum, frame):
        logger.info(f'Script {config} received signal {signum}, exiting gracefully')
        try:
            # 先 flush 所有 handler，确保本地文件日志落盘
            for h in list(logging.root.handlers) + list(logger.handlers):
                try:
                    h.flush()
                except Exception:
                    pass
        finally:
            try:
                log_queue.close()
            except Exception:
                pass
            try:
                state_queue.close()
            except Exception:
                pass
            sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    def start_log() -> None:
        try:
            from module.logger import set_file_logger, set_structured_func_logger, set_log_level
            set_file_logger(name=config)

            def queue_send(msg: str) -> None:
                try:
                    # Queue.put 在 Windows 下对并发写更友好；超时避免业务阻塞
                    log_queue.put(msg, timeout=0.5)
                except Exception:
                    # 日志通道异常时丢弃，避免反压影响脚本主逻辑
                    pass

            set_structured_func_logger(config, queue_send)
        except Exception as e:
            logger.exception(f'Start log error')
            logger.error(f'Error: {e}')
            raise
    start_log()

    def control_loop():
        """读取主进程通过 state_queue 下发的控制命令（如调整日志级别）。"""
        while True:
            try:
                msg = state_queue.get(timeout=1)
                if not isinstance(msg, dict):
                    continue
                action = msg.get('action')
                if action == 'set_log_level':
                    from module.logger import set_log_level
                    set_log_level(msg.get('level', 'INFO'))
            except QueueEmpty:
                continue
            except Exception:
                continue

    import threading
    threading.Thread(target=control_loop, name=f'{config}_control', daemon=True).start()

    import time
    try:
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
        raise


if __name__ == '__main__':
    p = ScriptProcess('oas1')
    p.start()
    from time import sleep
    sleep(10)
    logger.info(p._process.exitcode)
