# This Python file uses the following encoding: utf-8
"""
电源管理工具：在 Windows 上阻止系统息屏/睡眠，任务空闲时立即释放。
具备线程安全的引用计数与上下文管理器支持。
"""

import sys
import threading
from contextlib import contextmanager

from module.logger import logger

# Windows Execution State Flags
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


class PowerManager:
    """
    通过 Windows SetThreadExecutionState API 保持系统唤醒。
    非 Windows 平台或调用失败时自动降级为无操作，不影响原有逻辑。
    采用线程安全的引用计数机制，防止嵌套任务调用提前误释放。
    """

    _lock: threading.Lock = threading.Lock()
    _ref_count: int = 0

    @classmethod
    def acquire(cls) -> None:
        """阻止系统息屏与睡眠（引用计数递增）。"""
        if sys.platform != 'win32':
            return
        with cls._lock:
            cls._ref_count += 1
            if cls._ref_count == 1:
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetThreadExecutionState(
                        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
                    )
                    logger.info('PowerManager: acquired keep-awake (ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED)')
                except Exception as e:
                    logger.warning(f'PowerManager: failed to acquire keep-awake: {e}')
            else:
                logger.debug(f'PowerManager: acquire nested (ref_count={cls._ref_count})')

    @classmethod
    def release(cls) -> None:
        """释放息屏阻止，当引用计数归零时让系统恢复默认电源策略。"""
        if sys.platform != 'win32':
            return
        with cls._lock:
            if cls._ref_count > 0:
                cls._ref_count -= 1
            if cls._ref_count == 0:
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                    logger.info('PowerManager: released keep-awake')
                except Exception as e:
                    logger.warning(f'PowerManager: failed to release keep-awake: {e}')
            else:
                logger.debug(f'PowerManager: release nested (ref_count={cls._ref_count})')

    @classmethod
    def release_all(cls) -> None:
        """强制清空引用计数并恢复系统默认电源策略。"""
        if sys.platform != 'win32':
            return
        with cls._lock:
            was_active = (cls._ref_count > 0)
            cls._ref_count = 0
            if was_active:
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                    logger.info('PowerManager: released all keep-awake')
                except Exception as e:
                    logger.warning(f'PowerManager: failed to release all keep-awake: {e}')

    @classmethod
    @contextmanager
    def keep_awake(cls):
        """上下文管理器：with PowerManager.keep_awake(): ..."""
        cls.acquire()
        try:
            yield
        finally:
            cls.release()

    @classmethod
    def is_active(cls) -> bool:
        """查询当前是否正处于保活状态。"""
        with cls._lock:
            return cls._ref_count > 0
