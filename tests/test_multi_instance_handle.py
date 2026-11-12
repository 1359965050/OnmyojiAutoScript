# This Python file uses the following encoding: utf-8
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import module.device.handle as handle_mod
from module.device.connection_attr import is_windows_client_config
from module.device.handle import EmulatorFamily, Handle, WindowNode
from script import Script


def _make_device_config(emulatorinfo_type='MuMuPlayer12', package_name='com.netease.onmyoji.wyzymnqsd_cps',
                        serial='127.0.0.1:16384', handle='auto'):
    device = SimpleNamespace(
        emulatorinfo_type=emulatorinfo_type,
        package_name=package_name,
        serial=serial,
        handle=handle,
    )
    return SimpleNamespace(script=SimpleNamespace(device=device))


class TestMultiInstanceHandleSelection(unittest.TestCase):
    def test_emulator_config_never_steals_windows_pc_client_window(self):
        windows = ['阴阳师-MuMu模拟器专版', 'MuMu安卓设备']
        with patch.object(handle_mod, 'FindWindow', return_value=0):
            # 1) 双端同开时，MuMu12 配置应精准选中 MuMu安卓设备，而非 Windows 客户端窗口
            title = Handle.auto_handle_title(windows, is_windows_client=False, serial='127.0.0.1:16384')
            self.assertEqual(title, 'MuMu安卓设备')

            # 2) target_candidates 未命中、落入关键字回退时，仍应跳过桌面客户端窗口
            title_fallback = Handle.auto_handle_title(
                ['阴阳师-MuMu模拟器专版', '自定义模拟器'],
                is_windows_client=False,
                serial='127.0.0.1:16384',
            )
            self.assertEqual(title_fallback, '自定义模拟器')

            # 3) 仅存在桌面客户端窗口、模拟器窗口未就绪时，应返回 None 而不是抢占配置1窗口
            title_missing = Handle.auto_handle_title(
                ['阴阳师-MuMu模拟器专版', '阴阳师'],
                is_windows_client=False,
                serial='127.0.0.1:16384',
            )
            self.assertIsNone(title_missing)

    def test_windows_client_config_selects_pc_client_window(self):
        windows = ['MuMu安卓设备', '阴阳师-MuMu模拟器专版']
        with patch.object(handle_mod, 'FindWindow', return_value=0):
            title = Handle.auto_handle_title(windows, is_windows_client=True, serial='windows-0')
            self.assertEqual(title, '阴阳师-MuMu模拟器专版')

    def test_process_name_distinguishes_pc_client_and_emulator(self):
        with patch.object(handle_mod, 'FindWindow', return_value=1001), \
             patch.object(handle_mod, 'IsWindow', return_value=True), \
             patch.object(handle_mod, 'handle_num2pid', return_value=30048), \
             patch('psutil.Process', return_value=SimpleNamespace(name=lambda: 'onmyoji.exe')):
            self.assertTrue(Handle._is_windows_pc_client_window('任意自定义标题'))

        with patch.object(handle_mod, 'FindWindow', return_value=1002), \
             patch.object(handle_mod, 'IsWindow', return_value=True), \
             patch.object(handle_mod, 'handle_num2pid', return_value=29320), \
             patch('psutil.Process', return_value=SimpleNamespace(name=lambda: 'MuMuNxMain.exe')):
            self.assertFalse(Handle._is_windows_pc_client_window('阴阳师-安卓测试窗口'))

    def test_standalone_handle_infers_mode_from_config(self):
        emu_cfg = _make_device_config()
        pc_cfg = _make_device_config(
            emulatorinfo_type='WindowsClient',
            package_name='onmyoji.exe',
            serial='windows-0',
        )
        self.assertFalse(is_windows_client_config(emu_cfg))
        self.assertTrue(is_windows_client_config(pc_cfg))

        h = object.__new__(Handle)
        h.config = emu_cfg
        self.assertFalse(h._is_windows_client_mode())

        with patch.object(Handle, 'all_windows', return_value=['阴阳师-MuMu模拟器专版', 'MuMu安卓设备']), \
             patch.object(handle_mod, 'FindWindow', return_value=0), \
             patch.object(handle_mod, 'handle_title2num', return_value=20001), \
             patch.object(handle_mod, 'is_handle_valid', return_value=True), \
             patch.object(handle_mod, 'GetClientRect', return_value=(0, 0, 1280, 720)), \
             patch.object(Handle, 'handle_tree', return_value=None):
            h.init_handle()
            self.assertEqual(h.root_handle_title, 'MuMu安卓设备')
            self.assertEqual(h.root_handle_num, 20001)
            self.assertEqual(h.emulator_family, EmulatorFamily.FAMILY_MUMU)
            self.assertEqual(h.screenshot_size, (1280, 720))

    def test_emulator_family_respects_children_and_config_mode(self):
        emu_handle = object.__new__(Handle)
        emu_handle.config = _make_device_config()
        emu_handle.root_handle_title = '阴阳师小号'
        root = WindowNode(name='阴阳师小号', num=100)
        WindowNode(name='MuMuNxDevice', num=101, parent=root)
        emu_handle.root_node = root
        self.assertEqual(emu_handle.emulator_family, EmulatorFamily.FAMILY_MUMU)

        # 未显式设置 config/is_windows_client 的传统句柄对象保持旧标题判定兼容
        legacy_handle = object.__new__(Handle)
        legacy_handle.root_handle_title = '阴阳师'
        legacy_handle.root_node = WindowNode(name='阴阳师', num=102)
        self.assertEqual(legacy_handle.emulator_family, EmulatorFamily.FAMILY_WINDOWS_CLIENT)

    def test_script_resolve_target_window_name(self):
        self.assertEqual(
            Script._resolve_target_window_name('auto', is_win_client=False, resolved_title='MuMu安卓设备'),
            'MuMu安卓设备',
        )
        self.assertEqual(
            Script._resolve_target_window_name('auto', is_win_client=False, resolved_title=''),
            '',
        )
        self.assertEqual(
            Script._resolve_target_window_name('auto', is_win_client=True, resolved_title='阴阳师-MuMu模拟器专版'),
            '阴阳师-MuMu模拟器专版',
        )
        self.assertEqual(
            Script._resolve_target_window_name('MuMuPlayer', is_win_client=True, resolved_title=''),
            '阴阳师',
        )
        self.assertEqual(
            Script._resolve_target_window_name('123456', is_win_client=False, resolved_title='MuMu安卓设备'),
            'MuMu安卓设备',
        )


if __name__ == '__main__':
    unittest.main()
