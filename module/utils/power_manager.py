# This Python file uses the following encoding: utf-8
"""
电源管理工具：在 Windows 上阻止系统息屏/睡眠，任务空闲时立即释放。
"""

import sys

from module.logger import logger


class PowerManager:
    """
    通过 Windows SetThreadExecutionState API 保持系统唤醒。
    非 Windows 平台或调用失败时自动降级为无操作，不影响原有逻辑。
    """

    _acquired: bool = False

    @classmethod
    def acquire(cls) -> None:
        """阻止系统息屏与睡眠。重复调用幂等。"""
        if cls._acquired:
            return
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_DISPLAY_REQUIRED = 0x00000002
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
            cls._acquired = True
            logger.info('PowerManager: acquired keep-awake')
        except Exception as e:
            logger.warning(f'PowerManager: failed to acquire keep-awake: {e}')

    @classmethod
    def release(cls) -> None:
        """释放息屏阻止，让系统恢复默认电源策略。重复调用幂等。"""
        if not cls._acquired:
            return
        if sys.platform != 'win32':
            cls._acquired = False
            return
        try:
            import ctypes
            ES_CONTINUOUS = 0x80000000
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            cls._acquired = False
            logger.info('PowerManager: released keep-awake')
        except Exception as e:
            logger.warning(f'PowerManager: failed to release keep-awake: {e}')
