# This Python file uses the following encoding: utf-8
# @author runhey
# 主进程的管理
# github https://github.com/runhey
import asyncio
import os
import threading

from module.logger import logger
from module.config.config import Config
from module.config.utils import filepath_config
from module.server.script_process import ScriptProcess, ScriptState
from module.server.config_manager import ConfigManager
from module.server.setting import State


class MainManager(ConfigManager):
    script_process: dict[str, ScriptProcess] = None  # 脚本进程
    signal_kill_server: bool = False

    def __init__(self) -> None:
        super().__init__()
        self.script_process: dict[str, ScriptProcess] = {}  # 脚本进程
        self._all_script_files = self.all_script_files()
        for script_name in self._all_script_files:
            self.script_process[script_name] = ScriptProcess(script_name)
        self._broadcast_tasks: dict[str, asyncio.Task] = {}
        self._supervisor_task: asyncio.Task | None = None
        self._shutdown_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._config_cache: dict[str, tuple[tuple[int, int] | None, Config]] = {}
        self._config_cache_lock = threading.RLock()

    @staticmethod
    def _config_file_signature(name: str) -> tuple[int, int] | None:
        try:
            st = os.stat(filepath_config(name))
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def config_cache(self, name: str) -> Config:
        sig = self._config_file_signature(name)
        with self._config_cache_lock:
            cached = self._config_cache.get(name)
            if cached is not None and sig is not None and cached[0] == sig:
                return cached[1]
            cfg = Config(name)
            new_sig = self._config_file_signature(name)
            self._config_cache[name] = (new_sig, cfg)
            return cfg

    def invalidate_config_cache(self, name: str | None = None) -> None:
        with self._config_cache_lock:
            if name is None:
                self._config_cache.clear()
            else:
                self._config_cache.pop(name, None)

    def refresh_script_files(self) -> list[str]:
        self._all_script_files = self.all_script_files()
        return self._all_script_files

    def add_script_file(self, file_name: str):
        # 当你添加了新的脚本文件后，需要添加缓存的列表
        self.refresh_script_files()
        if file_name in self.script_process:
            logger.warning(f'[{file_name}] script file already exists')
            return
        self.script_process[file_name] = ScriptProcess(file_name)

    def _get_loop(self) -> asyncio.AbstractEventLoop | None:
        if self._loop is not None and not self._loop.is_closed():
            return self._loop
        try:
            loop = asyncio.get_running_loop()
            self._loop = loop
            return loop
        except RuntimeError:
            return None

    def _prune_finished_tasks(self) -> None:
        for task_name, task in list(self._broadcast_tasks.items()):
            if not task.done():
                continue
            self._broadcast_tasks.pop(task_name, None)
            if not task.cancelled():
                exc = task.exception()
                if exc is not None:
                    logger.error(f'Broadcast task {task_name} failed: {exc}')

    def ensure_script_tasks(self, name: str) -> None:
        script_p = self.script_process.get(name)
        if script_p is None or script_p.state not in (ScriptState.RUNNING, ScriptState.UPDATING):
            return
        loop = self._get_loop()
        if loop is None:
            return
        state_task_name = f'coroutine_state_{name}'
        existing_state = self._broadcast_tasks.get(state_task_name)
        if existing_state is None or existing_state.done():
            self._broadcast_tasks[state_task_name] = loop.create_task(
                script_p.coroutine_broadcast_state(),
                name=state_task_name,
            )
        log_task_name = f'coroutine_log_{name}'
        existing_log = self._broadcast_tasks.get(log_task_name)
        if existing_log is None or existing_log.done():
            self._broadcast_tasks[log_task_name] = loop.create_task(
                script_p.coroutine_broadcast_log(),
                name=log_task_name,
            )

    async def _cancel_script_tasks(self, name: str) -> None:
        to_cancel: list[asyncio.Task] = []
        for prefix in ('coroutine_state_', 'coroutine_log_'):
            task = self._broadcast_tasks.pop(f'{prefix}{name}', None)
            if task is not None and not task.done():
                task.cancel()
                to_cancel.append(task)
        if to_cancel:
            await asyncio.gather(*to_cancel, return_exceptions=True)

    async def remove_script_process(self, name: str) -> None:
        await self._cancel_script_tasks(name)
        script_p = self.script_process.pop(name, None)
        if script_p is not None:
            await script_p.stop()
            await script_p.close_all()
        self.refresh_script_files()

    def start_broadcast_loop(self) -> None:
        MainManager.signal_kill_server = False
        loop = asyncio.get_running_loop()
        self._loop = loop
        if self._supervisor_task is None or self._supervisor_task.done():
            self._supervisor_task = loop.create_task(
                self.push_data_handle(),
                name='main_manager_push_data',
            )

    async def stop_broadcast_loop(self) -> None:
        tasks_to_cancel: list[asyncio.Task] = []
        if self._supervisor_task is not None and not self._supervisor_task.done():
            self._supervisor_task.cancel()
            tasks_to_cancel.append(self._supervisor_task)
        self._supervisor_task = None

        for task in self._broadcast_tasks.values():
            if not task.done():
                task.cancel()
                tasks_to_cancel.append(task)
        self._broadcast_tasks.clear()

        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

    async def push_data_handle(self):
        try:
            while not MainManager.signal_kill_server:
                self._prune_finished_tasks()
                for task_name, task in list(self._broadcast_tasks.items()):
                    script_name = task_name.removeprefix('coroutine_state_').removeprefix('coroutine_log_')
                    script_p = self.script_process.get(script_name)
                    if script_p is None or script_p.state == ScriptState.INACTIVE:
                        if not task.done():
                            task.cancel()
                        self._broadcast_tasks.pop(task_name, None)

                for name, script_p in list(self.script_process.items()):
                    if script_p.state in (ScriptState.RUNNING, ScriptState.UPDATING):
                        self.ensure_script_tasks(name)
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            return

    def request_server_shutdown(self, delay: float = 0.2) -> None:
        MainManager.signal_kill_server = True
        loop = self._get_loop()

        def _trigger_uvicorn_exit() -> None:
            if State.uvicorn_server is not None:
                State.uvicorn_server.should_exit = True

        if loop is None:
            _trigger_uvicorn_exit()
            return

        if self._shutdown_task is None or self._shutdown_task.done():
            async def _delayed_shutdown() -> None:
                await asyncio.sleep(max(0.0, delay))
                logger.info('Gracefully stopping OAS web service')
                _trigger_uvicorn_exit()

            self._shutdown_task = loop.create_task(_delayed_shutdown(), name='oas_graceful_shutdown')

    async def shutdown(self) -> None:
        MainManager.signal_kill_server = True
        await self.stop_broadcast_loop()
        for script_p in list(self.script_process.values()):
            await script_p.stop()
            await script_p.close_all()

    async def restart_processes(self, script_instances: list[str]):
        for instance in script_instances:
            logger.info(f'Restart script {instance}')
            if instance not in self.script_process:
                try:
                    self.script_process[instance] = ScriptProcess(instance)
                except FileNotFoundError:
                    logger.error(f'{instance} file not found')
                    continue
            await self.script_process[instance].start()
            self.ensure_script_tasks(instance)


mm = MainManager()
