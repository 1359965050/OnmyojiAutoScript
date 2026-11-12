# This Python file uses the following encoding: utf-8
from __future__ import annotations

import numpy as np
import unittest
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

from module.device.device import Device
from module.device.handle import EmulatorFamily
from module.device.method import windows_impl
from module.device.method.windows_impl import Window


class _FakeWindowState:
    """模拟 Win32 窗口外框、客户区与最大化/最小化状态。"""

    def __init__(
        self,
        client_w: int,
        client_h: int,
        border_w: int = 16,
        border_h: int = 39,
        zoomed: bool = False,
        iconic: bool = False,
        resizable: bool = True,
    ) -> None:
        self.client_w = client_w
        self.client_h = client_h
        self.border_w = border_w
        self.border_h = border_h
        self.zoomed = zoomed
        self.iconic = iconic
        self.resizable = resizable
        self.set_pos_calls: list[tuple[int, int]] = []
        self.show_window_calls: list[int] = []

    def get_client_rect(self, hwnd: int) -> tuple[int, int, int, int]:
        if self.iconic:
            return (0, 0, 0, 0)
        return (0, 0, self.client_w, self.client_h)

    def get_window_rect(self, hwnd: int) -> tuple[int, int, int, int]:
        if self.iconic:
            return (-32000, -32000, -31840, -31970)
        return (100, 100, 100 + self.client_w + self.border_w, 100 + self.client_h + self.border_h)

    def show_window(self, hwnd: int, cmd: int) -> int:
        self.show_window_calls.append(cmd)
        if cmd == windows_impl.SW_RESTORE:
            self.zoomed = False
            self.iconic = False
        return 1

    def set_window_pos(self, hwnd: int, insert_after: int, x: int, y: int, w: int, h: int, flags: int) -> int:
        self.set_pos_calls.append((w, h))
        if self.resizable and not self.zoomed and not self.iconic:
            self.client_w = max(1, w - self.border_w)
            self.client_h = max(1, h - self.border_h)
        return 1


class DummyDesktopWindow(Window):
    """隔离真实 Win32 句柄与配置初始化的桌面端窗口测试替身。"""

    def __init__(self, hwnd: int = 123456) -> None:
        self.emulator_family = EmulatorFamily.FAMILY_WINDOWS_CLIENT
        self.root_node = MagicMock(num=hwnd)
        self.screenshot_handle_num = hwnd
        self.control_handle_list = [hwnd]
        # 模拟 Handle.init_handle() 预先缓存了校准前的错误尺寸
        self.__dict__['screenshot_size'] = (1640, 924)


class TestDesktopWindowCalibration(unittest.TestCase):
    """测试《阴阳师》桌面端窗口自适应校准与坐标一致性。"""

    def _run_calibration(self, state: _FakeWindowState, dummy: DummyDesktopWindow | None = None):
        win = dummy or DummyDesktopWindow()
        user32_mock = MagicMock()
        user32_mock.IsZoomed.side_effect = lambda _hwnd: 1 if state.zoomed else 0

        with patch.object(windows_impl, 'dpi_awareness', return_value=nullcontext()), \
             patch.object(windows_impl, 'IsWindow', return_value=True), \
             patch.object(windows_impl, 'IsIconic', side_effect=lambda _hwnd: state.iconic), \
             patch.object(windows_impl, 'ShowWindow', side_effect=state.show_window), \
             patch.object(windows_impl, 'GetClientRect', side_effect=state.get_client_rect), \
             patch.object(windows_impl, 'GetWindowRect', side_effect=state.get_window_rect), \
             patch.object(windows_impl, 'SetWindowPos', side_effect=state.set_window_pos), \
             patch.object(windows_impl.ctypes.windll, 'user32', user32_mock), \
             patch('time.sleep', return_value=None):
            ok = win.desktop_window_set_size(1280, 720)
        return ok, win

    def test_enlarged_window_calibrates_without_oscillation(self):
        """窗口被手动拉大到 1640x924 时，应一步准确缩回 1280x720，绝不震荡到 916x516。"""
        state = _FakeWindowState(client_w=1640, client_h=924, border_w=16, border_h=39)
        ok, win = self._run_calibration(state)

        self.assertTrue(ok)
        self.assertEqual((state.client_w, state.client_h), (1280, 720))
        self.assertEqual(state.set_pos_calls, [(1280 + 16, 720 + 39)])
        self.assertNotIn('screenshot_size', win.__dict__)

    def test_shrunk_window_calibrates_up_to_target(self):
        """窗口被缩小到 916x516 时，应准确放大回 1280x720。"""
        state = _FakeWindowState(client_w=916, client_h=516, border_w=16, border_h=39)
        ok, win = self._run_calibration(state)

        self.assertTrue(ok)
        self.assertEqual((state.client_w, state.client_h), (1280, 720))
        self.assertEqual(state.set_pos_calls, [(1280 + 16, 720 + 39)])
        self.assertNotIn('screenshot_size', win.__dict__)

    def test_maximized_window_restores_before_resizing(self):
        """窗口处于最大化 (IsZoomed) 时，应先 SW_RESTORE 再收缩回 1280x720。"""
        state = _FakeWindowState(client_w=1920, client_h=1040, border_w=16, border_h=39, zoomed=True)
        ok, _ = self._run_calibration(state)

        self.assertTrue(ok)
        self.assertIn(windows_impl.SW_RESTORE, state.show_window_calls)
        self.assertFalse(state.zoomed)
        self.assertEqual((state.client_w, state.client_h), (1280, 720))

    def test_minimized_window_restores_before_resizing(self):
        """窗口处于最小化 (IsIconic) 时，应先调用 ensure_window_restored 再校准。"""
        state = _FakeWindowState(client_w=1640, client_h=924, border_w=16, border_h=39, iconic=True)
        win = DummyDesktopWindow()
        with patch.object(win, 'ensure_window_restored', side_effect=lambda _h: state.show_window(_h, windows_impl.SW_RESTORE) or True) as mock_restore:
            ok, _ = self._run_calibration(state, dummy=win)

        mock_restore.assert_called_once()
        self.assertTrue(ok)
        self.assertEqual((state.client_w, state.client_h), (1280, 720))

    def test_unresizable_window_stops_early_and_clears_cache(self):
        """当外部窗口锁死尺寸拒绝变化时，应提前终止重试而不是空转并清理缓存。"""
        state = _FakeWindowState(client_w=1600, client_h=900, resizable=False)
        ok, win = self._run_calibration(state)

        self.assertFalse(ok)
        self.assertEqual(len(state.set_pos_calls), 1)
        self.assertNotIn('screenshot_size', win.__dict__)

    def test_long_click_and_foreground_click_use_live_client_coords(self):
        """即使缓存的 screenshot_size 仍为旧尺寸，长按与前台点击也应按实时客户区换算坐标。"""
        win = DummyDesktopWindow()
        # 缓存为旧尺寸 1640x924，但当前真实客户区已调整为 1280x720
        win.__dict__['screenshot_size'] = (1640, 924)

        with patch.object(windows_impl, 'IsWindow', return_value=True), \
             patch.object(windows_impl, 'IsIconic', return_value=False), \
             patch.object(windows_impl, 'GetClientRect', return_value=(0, 0, 1280, 720)), \
             patch.object(windows_impl, 'PostMessage') as mock_post, \
             patch('time.sleep', return_value=None):
            win.long_click_window_message(640, 360, 0.1)

        expected_lparam = windows_impl.MAKELONG(640, 360)
        self.assertEqual(mock_post.call_args_list[1].args[3], expected_lparam)

        with patch.object(win, 'bring_to_front', return_value=True), \
             patch.object(windows_impl, 'IsWindow', return_value=True), \
             patch.object(windows_impl, 'GetClientRect', return_value=(0, 0, 1280, 720)), \
             patch.object(windows_impl, 'ClientToScreen', side_effect=lambda _h, pt: pt), \
             patch.object(windows_impl, 'SetCursorPos') as mock_cursor, \
             patch.object(windows_impl, 'mouse_event'), \
             patch('time.sleep', return_value=None):
            win.click_window_foreground(640, 360)

        mock_cursor.assert_called_once_with((640, 360))

    def test_device_app_start_and_wait_ready_recalibrate_windows_client(self):
        """桌面端在 app_start 重拉起及 wait_app_start_ready 画面就绪后，均应自动校准为 1280x720。"""
        dev = object.__new__(Device)
        dev.config = MagicMock()
        dev.config.script.error.handle_error = True
        dev.config.script.device.screenshot_method = 'window_background'
        dev.is_windows_client = True
        dev.emulator_family = EmulatorFamily.FAMILY_WINDOWS_CLIENT
        dev.__dict__['root_node'] = MagicMock()
        dev.__dict__['screenshot_handle_num'] = 111
        dev.__dict__['screenshot_size'] = (1640, 924)
        dev.stuck_record_clear = MagicMock()
        dev.click_record_clear = MagicMock()

        with patch('module.device.app_control.AppControl.app_start') as mock_super_start, \
             patch.object(dev, '_ensure_windows_client_window', return_value=True) as mock_ensure:
            dev.app_start()

        mock_super_start.assert_called_once()
        mock_ensure.assert_called_once_with(timeout=25.0, log_if_matched=True)
        self.assertNotIn('root_node', dev.__dict__)
        self.assertNotIn('screenshot_handle_num', dev.__dict__)
        self.assertNotIn('screenshot_size', dev.__dict__)

        ready_frame = np.full((720, 1280, 3), 80, dtype=np.uint8)
        dev.screenshot_methods = {'window_background': MagicMock(return_value=ready_frame)}
        dev.app_is_running = MagicMock(return_value=True)
        with patch.object(dev, 'desktop_window_set_size', return_value=True) as mock_set_size, \
             patch('time.sleep', return_value=None):
            dev.wait_app_start_ready(timeout=2.0, interval=0.1)

        mock_set_size.assert_called_once_with(1280, 720, log_if_matched=False)


if __name__ == '__main__':
    unittest.main()
