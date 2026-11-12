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
    _thread_refs: dict[int, int] = {}

    @classmethod
    def acquire(cls) -> None:
        """当前线程阻止系统息屏与睡眠（按线程 ID 独立计数）。"""
        if sys.platform != 'win32':
            return
        tid = threading.get_ident()
        with cls._lock:
            count = cls._thread_refs.get(tid, 0) + 1
            cls._thread_refs[tid] = count
            if count == 1:
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetThreadExecutionState(
                        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
                    )
                    logger.info(f'PowerManager[tid={tid}]: acquired keep-awake (ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED)')
                except Exception as e:
                    logger.warning(f'PowerManager[tid={tid}]: failed to acquire keep-awake: {e}')
            else:
                logger.debug(f'PowerManager[tid={tid}]: acquire nested (ref_count={count})')

    @classmethod
    def release(cls) -> None:
        """当前线程释放息屏阻止，仅在本线程引用计数归零时恢复本线程默认电源策略。"""
        if sys.platform != 'win32':
            return
        tid = threading.get_ident()
        with cls._lock:
            count = cls._thread_refs.get(tid, 0)
            if count <= 0:
                return
            count -= 1
            if count == 0:
                cls._thread_refs.pop(tid, None)
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                    logger.info(f'PowerManager[tid={tid}]: released keep-awake')
                except Exception as e:
                    logger.warning(f'PowerManager[tid={tid}]: failed to release keep-awake: {e}')
            else:
                cls._thread_refs[tid] = count
                logger.debug(f'PowerManager[tid={tid}]: release nested (ref_count={count})')

    @classmethod
    def release_all(cls) -> None:
        """释放当前线程全部引用计数并清理已退出线程的陈旧记录。"""
        if sys.platform != 'win32':
            return
        tid = threading.get_ident()
        alive_tids = {t.ident for t in threading.enumerate() if t.ident is not None}
        with cls._lock:
            had_current = cls._thread_refs.pop(tid, 0) > 0
            # 清理已销毁线程残留计数，保留其他仍在运行的活线程计数互不干扰
            stale_tids = [t for t in cls._thread_refs if t not in alive_tids]
            for stale_tid in stale_tids:
                cls._thread_refs.pop(stale_tid, None)
            if had_current:
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                    logger.info(f'PowerManager[tid={tid}]: released all keep-awake for current thread')
                except Exception as e:
                    logger.warning(f'PowerManager[tid={tid}]: failed to release all keep-awake: {e}')

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
        """查询当前是否存在处于保活状态的线程。"""
        with cls._lock:
            return any(count > 0 for count in cls._thread_refs.values())

    @classmethod
    def is_thread_active(cls, tid: int | None = None) -> bool:
        """查询指定线程（默认当前线程）是否正处于保活状态。"""
        target_tid = threading.get_ident() if tid is None else tid
        with cls._lock:
            return cls._thread_refs.get(target_tid, 0) > 0
