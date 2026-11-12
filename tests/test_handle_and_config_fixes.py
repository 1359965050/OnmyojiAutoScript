# This Python file uses the following encoding: utf-8
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from win32api import MAKELONG

import module.device.handle as handle_mod
import module.device.method.windows_impl as windows_impl
from module.config.config import Config
from module.config.config_model import ConfigModel
from module.device.handle import EmulatorFamily, Handle, window_scale_rate
from module.device.method.windows_impl import Window


class _DummyEmulatorWindow(Window):
    def __init__(self, family: EmulatorFamily, handles: list[int], scale: float = 1.5) -> None:
        self.emulator_family = family
        self.control_handle_list = handles
        self.screenshot_handle_num = handles[0] if handles else 0
        self.window_scale_rate = scale


class TestHandleAndWindowsFixes(unittest.TestCase):
    def test_window_scale_rate_always_releases_dc(self):
        with patch.object(handle_mod, 'GetDC', return_value=777) as mock_get_dc, \
             patch.object(handle_mod, 'ReleaseDC') as mock_release_dc, \
             patch.object(handle_mod, 'GetDeviceCaps', return_value=2880), \
             patch.object(handle_mod, 'GetSystemMetrics', return_value=1920):
            rate = window_scale_rate()
            self.assertEqual(rate, 1.5)
            mock_get_dc.assert_called_once_with(0)
            mock_release_dc.assert_called_once_with(0, 777)

        # Even if GetDeviceCaps raises, ReleaseDC must still run
        with patch.object(handle_mod, 'GetDC', return_value=888), \
             patch.object(handle_mod, 'ReleaseDC') as mock_release_dc, \
             patch.object(handle_mod, 'GetDeviceCaps', side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                window_scale_rate()
            mock_release_dc.assert_called_once_with(0, 888)

        # Handle.window_scale_rate delegates safely and releases DC too
        dummy_handle = object.__new__(Handle)
        with patch.object(handle_mod, 'GetDC', return_value=999), \
             patch.object(handle_mod, 'ReleaseDC') as mock_release_dc, \
             patch.object(handle_mod, 'GetDeviceCaps', return_value=1920), \
             patch.object(handle_mod, 'GetSystemMetrics', return_value=1920):
            self.assertEqual(dummy_handle.window_scale_rate, 1.0)
            mock_release_dc.assert_called_once_with(0, 999)

    def test_emulator_click_and_long_click_do_not_divide_by_scale_rate(self):
        win = _DummyEmulatorWindow(EmulatorFamily.FAMILY_MUMU, handles=[101, 202], scale=1.5)
        with patch.object(windows_impl, 'SendMessage') as mock_send, \
             patch('time.sleep', return_value=None):
            win.click_window_message(900, 600, fast=True)
            win.long_click_window_message(900, 600, duration=0.1)

        down_lparams = [
            call.args[3]
            for call in mock_send.call_args_list
            if call.args[1] == windows_impl.WM_LBUTTONDOWN
        ]
        self.assertEqual(len(down_lparams), 2)
        for lp in down_lparams:
            self.assertEqual(lp, MAKELONG(900, 600))

    def test_swipe_and_scroll_work_with_family_other_and_multiple_handles(self):
        for handles, expected in [([11], 11), ([11, 22], 22), ([11, 22, 33, 44], 44)]:
            win = _DummyEmulatorWindow(EmulatorFamily.FAMILY_OTHER, handles=handles, scale=1.5)
            with patch.object(windows_impl, 'SendMessage') as mock_send, \
                 patch.object(windows_impl, 'PostMessage') as mock_post, \
                 patch.object(windows_impl, 'SetForegroundWindow'), \
                 patch('time.sleep', return_value=None):
                win.swipe_window_message([100, 200], [300, 400])
                win.swipe_vector_window_message2([100, 200], [300, 400])
                win.scroll_window_message(100, 200)

            self.assertTrue(any(c.args[0] == expected for c in mock_send.call_args_list))
            self.assertTrue(any(c.args[0] == expected for c in mock_post.call_args_list))


class TestRunningTaskSeparation(unittest.TestCase):
    def test_running_task_updates_do_not_trigger_save_and_survive_reload(self):
        with patch.object(ConfigModel, 'save') as mock_save:
            model = ConfigModel()
            model.running_task = 'Orochi'
            self.assertEqual(model.running_task, 'Orochi')
            model.running_task = ''
            self.assertEqual(model.running_task, '')
            mock_save.assert_not_called()

            # Excluded from serialized config dump
            self.assertNotIn('running_task', model.model_dump())

        # Reload preserves runtime running_task without touching disk
        fake_data = {'config_name': 'test_cfg'}
        with ExitStack() as stack:
            stack.enter_context(patch.object(ConfigModel, 'read_json', side_effect=lambda _: dict(fake_data)))
            mock_save = stack.enter_context(patch.object(ConfigModel, 'save'))
            stack.enter_context(patch('module.config.config_state.ConfigState.__init__', return_value=None))
            cfg = Config.__new__(Config)
            cfg.config_name = 'test_cfg'
            cfg._running_task = ''
            cfg.model = ConfigModel(config_name='test_cfg')
            cfg.model.running_task = 'RealmRaid'
            cfg.reload()
            self.assertEqual(cfg.model.running_task, 'RealmRaid')
            mock_save.assert_not_called()


if __name__ == '__main__':
    unittest.main()

