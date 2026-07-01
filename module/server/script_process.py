# This Python file uses the following encoding: utf-8
# @author runhey
# 脚本进程
# github https://github.com/runhey
import sys, os
import signal
import multiprocessing
import logging
import asyncio
import threading
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
    STOPPING = 4
    STARTING = 5


class ScriptProcess(ScriptWSManager):

    def __init__(self, config_name: str) -> None:
        super().__init__()
        if config_name not in ConfigManager.all_script_files():
            raise FileNotFoundError(f'{config_name}.json not found')
        self.config_name = config_name  # config_name
        self.log_queue = multiprocessing.Queue()
        self.state_queue = multiprocessing.Queue()
        self.command_queue = multiprocessing.Queue()
        self.stop_event = multiprocessing.Event()
        self.state: ScriptState = ScriptState.INACTIVE
        self._process = None
        self._state_lock = threading.Lock()

    async def _stop_process(self, process: multiprocessing.Process):
        """终止指定子进程；不修改实例状态。join 使用 run_in_executor 避免阻塞事件循环。"""
        if process is None or not process.is_alive():
            return
        logger.info(f'Script {self.config_name} stopping gracefully')
        self.stop_event.set()
        try:
            self.command_queue.put_nowait({"action": "stop"})
        except Exception:
            pass
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, process.join, 2)
        if process.is_alive():
            logger.debug(f'Script {self.config_name} graceful stop timeout, terminate')
            process.terminate()
            await loop.run_in_executor(None, process.join, 2)
        if process.is_alive():
            logger.error(f'Script {self.config_name} subprocess terminate failed, force kill')
            process.kill()
            await loop.run_in_executor(None, process.join, 1)

    async def start(self):
        # 第一阶段：检查并占用停止态，防止并发 start/stop 冲突
        with self._state_lock:
            if self.state in (ScriptState.RUNNING, ScriptState.STARTING):
                logger.warning(f'Script {self.config_name} already running/starting')
                return
            if self.state == ScriptState.STOPPING:
                logger.warning(f'Script {self.config_name} is stopping, please wait')
                return
            old_process = self._process
            self._process = None
            self.state = ScriptState.STOPPING

        try:
            # 第二阶段：在锁外终止旧进程，避免阻塞事件循环
            if old_process is not None and old_process.is_alive():
                await self._stop_process(old_process)

            # 第三阶段：启动新进程
            with self._state_lock:
                # 若状态已被其他操作改变，则放弃本次启动
                if self.state != ScriptState.STOPPING:
                    return
                self.stop_event.clear()
                self.state = ScriptState.STARTING
            await self.broadcast_state({"state": self.state})

            new_process = multiprocessing.Process(target=func,
                                                  args=(self.config_name, self.state_queue,
                                                        self.command_queue, self.log_queue,
                                                        self.stop_event,),
                                                  name=self.config_name,
                                                  daemon=True
                                                  )
            new_process.start()
            await asyncio.sleep(0.3)

            with self._state_lock:
                if self.state != ScriptState.STARTING:
                    # 启动期间被停止，终止刚创建的进程
                    new_process.terminate()
                    return
                self._process = new_process
                if new_process.is_alive():
                    self.state = ScriptState.RUNNING
                else:
                    self._process = None
                    logger.error(f'Script {self.config_name} failed to start')
                    self.state = ScriptState.WARNING
            await self.broadcast_state({"state": self.state})
        except Exception as e:
            logger.exception(f'Script {self.config_name} start failed: {e}')
            with self._state_lock:
                if self.state in (ScriptState.STOPPING, ScriptState.STARTING):
                    self._process = None
                    self.state = ScriptState.WARNING
            await self.broadcast_state({"state": self.state})

    async def stop(self):
        process = None
        with self._state_lock:
            if self.state == ScriptState.INACTIVE:
                return
            if self.state == ScriptState.STOPPING:
                logger.warning(f'Script {self.config_name} is already stopping')
                return
            process = self._process
            self._process = None
            self.state = ScriptState.STOPPING
        await self.broadcast_state({"state": self.state})

        try:
            await self._stop_process(process)
        except Exception as e:
            logger.exception(f'Script {self.config_name} stop failed: {e}')
        finally:
            with self._state_lock:
                if self.state == ScriptState.STOPPING:
                    self.state = ScriptState.INACTIVE
            await self.broadcast_state({"state": self.state})

    async def coroutine_broadcast_state(self):
        try:
            while 1:
                if self.state == ScriptState.INACTIVE:
                    await sleep(1)
                    continue

                # 进程看门狗：检测子进程是否意外退出
                state_changed = False
                new_state = None
                with self._state_lock:
                    process = self._process
                    state = self.state
                    if (process is not None and not process.is_alive()
                            and state not in (ScriptState.STOPPING, ScriptState.INACTIVE)):
                        exitcode = process.exitcode
                        logger.warning(
                            f'Script {self.config_name} exited unexpectedly, exitcode={exitcode}'
                        )
                        self._process = None
                        new_state = ScriptState.INACTIVE if exitcode == 0 else ScriptState.WARNING
                        self.state = new_state
                        state_changed = True
                if state_changed:
                    await self.broadcast_state({"state": new_state})
                    await sleep(0.5)
                    continue

                await sleep(0.1)
                try:
                    if self.state_queue.empty():
                        await sleep(0.5)
                        continue
                    data = self.state_queue.get_nowait()
                    if not data:
                        await sleep(0.5)
                        continue
                    if 'state' in data and data['state'] == ScriptState.WARNING:
                        with self._state_lock:
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
            logger.debug(f'{self.config_name} state coroutine is cancelled')
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
            logger.debug(f'{self.config_name} log coroutine is cancelled')
            return


def func(config: str, state_queue: multiprocessing.Queue,
         command_queue: multiprocessing.Queue, log_queue: multiprocessing.Queue,
         stop_event: multiprocessing.Event) -> None:
    import threading
    import time
    # 子进程内同样避免 Windows ProactorEventLoop 的 pipe 竞争断言
    if sys.platform.startswith("win"):
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    local_stop = threading.Event()

    def signal_handler(signum, frame):
        logger.info(f'Script {config} received signal {signum}, exiting gracefully')
        local_stop.set()
        try:
            # 先 flush 所有 handler，确保本地文件日志落盘
            for h in list(logging.root.handlers) + list(logger.handlers):
                try:
                    h.flush()
                except Exception:
                    pass
        finally:
            for q in (log_queue, state_queue, command_queue):
                try:
                    q.close()
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
        """读取主进程通过 command_queue 下发的控制命令（如调整日志级别、停止）。"""
        while not local_stop.is_set():
            try:
                msg = command_queue.get(timeout=0.1)
                if not isinstance(msg, dict):
                    continue
                action = msg.get('action')
                if action == 'set_log_level':
                    from module.logger import set_log_level
                    set_log_level(msg.get('level', 'INFO'))
                elif action == 'stop':
                    logger.info(f'Script {config} received stop command')
                    local_stop.set()
            except QueueEmpty:
                if stop_event.is_set():
                    local_stop.set()
                continue
            except Exception:
                continue

    threading.Thread(target=control_loop, name=f'{config}_control', daemon=True).start()

    try:
        from script import Script
        script = Script(config_name=config, stop_event=stop_event)
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
