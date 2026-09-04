# This Python file uses the following encoding: utf-8
import sys

_dpi_awareness_initialized = False


def enable_dpi_awareness() -> bool:
    """
    为当前 Python 进程开启 Windows 高 DPI 感知能力（Per-Monitor DPI Aware V2）。
    彻底消除 Windows DWM 针对高分屏（如 125%、150%、200% 缩放）的 DPI 虚拟化，
    确保所有 Win32 API（GetClientRect、GetDC、BitBlt、SendMessage）均在物理真实像素坐标系下运行，
    避免后台截图被裁切/放大失真以及点击坐标偏移。
    """
    global _dpi_awareness_initialized
    if _dpi_awareness_initialized:
        return True

    if not sys.platform.startswith("win"):
        _dpi_awareness_initialized = True
        return False

    import ctypes

    # 1. 尝试 Windows 10 1703+ / Windows 11 的 Per-Monitor V2 感知
    # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
    try:
        res = ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        if res:
            _dpi_awareness_initialized = True
            return True
    except Exception:
        pass

    # 2. 尝试 Windows 8.1 / 10 的 Per-Monitor 感知
    # PROCESS_PER_MONITOR_DPI_AWARE = 2
    try:
        res = ctypes.windll.shcore.SetProcessDpiAwareness(2)
        if res == 0:  # S_OK
            _dpi_awareness_initialized = True
            return True
    except Exception:
        pass

    # 3. 降级兼容 Windows Vista / 7 的系统级 DPI 感知
    try:
        res = ctypes.windll.user32.SetProcessDPIAware()
        if res:
            _dpi_awareness_initialized = True
            return True
    except Exception:
        pass

    _dpi_awareness_initialized = True
    return False
