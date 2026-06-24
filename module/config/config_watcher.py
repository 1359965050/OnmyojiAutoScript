# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import os
import time
import threading
from datetime import datetime
from typing import Callable, Optional

from module.config.utils import filepath_config, DEFAULT_TIME
from module.logger import logger


class ConfigWatcher:
    config_name = 'script'
    start_mtime = DEFAULT_TIME
    _watch_thread: Optional[threading.Thread] = None
    _watch_stop_event: Optional[threading.Event] = None
    _watch_callbacks: list[Callable[[str], None]] = []
    _watch_interval = 2.0

    def start_watching(self) -> None:
        self.start_mtime = self.get_mtime()

    def get_mtime(self) -> datetime:
        timestamp = os.stat(filepath_config(self.config_name)).st_mtime
        mtime = datetime.fromtimestamp(timestamp).replace(microsecond=0)
        return mtime

    def should_reload(self) -> bool:
        mtime = self.get_mtime()
        if mtime > self.start_mtime:
            logger.info(f'Config "{self.config_name}" changed at {mtime}')
            return True
        else:
            return False

    def add_watch_callback(self, callback: Callable[[str], None]) -> None:
        if callback not in self._watch_callbacks:
            self._watch_callbacks.append(callback)

    def remove_watch_callback(self, callback: Callable[[str], None]) -> None:
        if callback in self._watch_callbacks:
            self._watch_callbacks.remove(callback)

    def _notify_callbacks(self) -> None:
        for callback in self._watch_callbacks:
            try:
                callback(self.config_name)
            except Exception as e:
                logger.error(f'Error in config watch callback for {self.config_name}: {e}')

    def start_monitoring(self, interval: float = 2.0) -> None:
        if self._watch_thread and self._watch_thread.is_alive():
            return

        self._watch_interval = max(0.5, interval)
        self._watch_stop_event = threading.Event()
        self._watch_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name=f'config_watcher_{self.config_name}'
        )
        self._watch_thread.start()
        logger.debug(f'Started config monitor for "{self.config_name}" with interval {self._watch_interval}s')

    def stop_monitoring(self) -> None:
        if self._watch_stop_event:
            self._watch_stop_event.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=5.0)
        self._watch_thread = None
        self._watch_stop_event = None
        logger.debug(f'Stopped config monitor for "{self.config_name}"')

    def _monitor_loop(self) -> None:
        last_mtime = self.get_mtime()
        while not self._watch_stop_event.is_set():
            try:
                current_mtime = self.get_mtime()
                if current_mtime > last_mtime:
                    logger.info(f'Config "{self.config_name}" changed, notifying callbacks')
                    self.start_mtime = current_mtime
                    last_mtime = current_mtime
                    self._notify_callbacks()
            except Exception as e:
                logger.debug(f'Error monitoring config "{self.config_name}": {e}')
            time.sleep(self._watch_interval)


class ConfigWatchManager:
    _watchers: dict[str, ConfigWatcher] = {}
    _global_callbacks: list[Callable[[str], None]] = []
    _instance: Optional['ConfigWatchManager'] = None

    def __new__(cls) -> 'ConfigWatchManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_watcher(self, config_name: str) -> ConfigWatcher:
        if config_name not in self._watchers:
            watcher = ConfigWatcher()
            watcher.config_name = config_name
            watcher.start_watching()
            for callback in self._global_callbacks:
                watcher.add_watch_callback(callback)
            self._watchers[config_name] = watcher
        return self._watchers[config_name]

    def add_global_callback(self, callback: Callable[[str], None]) -> None:
        if callback not in self._global_callbacks:
            self._global_callbacks.append(callback)
            for watcher in self._watchers.values():
                watcher.add_watch_callback(callback)

    def remove_global_callback(self, callback: Callable[[str], None]) -> None:
        if callback in self._global_callbacks:
            self._global_callbacks.remove(callback)
            for watcher in self._watchers.values():
                watcher.remove_watch_callback(callback)

    def start_all_monitoring(self, interval: float = 2.0) -> None:
        for watcher in self._watchers.values():
            watcher.start_monitoring(interval)

    def stop_all_monitoring(self) -> None:
        for watcher in self._watchers.values():
            watcher.stop_monitoring()

    def get_stats(self) -> dict:
        return {
            "watchers_count": len(self._watchers),
            "watcher_names": list(self._watchers.keys()),
            "global_callbacks_count": len(self._global_callbacks),
        }


config_watch_manager = ConfigWatchManager()

