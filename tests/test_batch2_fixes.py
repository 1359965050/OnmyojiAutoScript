# This Python file uses the following encoding: utf-8
import io
import json
import sys
import tempfile
import threading
import types
import unittest
from contextlib import nullcontext
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

import module.device.handle as handle_mod
import module.device.method.windows_impl as windows_impl
from module.config.anti_ban import AntiBanGuard
from module.config.config import Config
from module.config.config_manual import ConfigManual
from module.config.config_model import ConfigModel
from module.device.connection import Connection
from module.device.control import Control
from module.device.device import Device
from module.device.emulator import EmulatorManager
from module.device.handle import EmulatorFamily, Handle
from module.device.method.nemu_ipc import CaptureNemuIpc, CaptureStd
from module.device.method.scrcpy.core import ScrcpyCore
from module.device.screenshot import Screenshot
from module.exception import GameNotRunningError
from module.handler.sensitive_info import handle_sensitive_text
from module.logger import normalize_log_name
from module.notify.notify import Notifier
from module.server.config_manager import ConfigManager
from module.server.log_service import normalize_script_name
from module.server.log_stats import LogStatsService
from module.server.main_manager import MainManager
from module.utils.power_manager import ES_CONTINUOUS, PowerManager
from script import Script
from tasks.base_task import BaseTask


class TestBatch2Fixes(unittest.TestCase):
    def test_emulator_handle_screenshot_size_uses_client_rect_and_dc(self):
        h = object.__new__(Handle)
        h.emulator_family = EmulatorFamily.FAMILY_MUMU
        h.screenshot_handle_num = 123

        with patch.object(handle_mod, "is_handle_valid", return_value=True), \
             patch.object(handle_mod, "GetClientRect", return_value=(0, 0, 1280, 720)) as mock_crect, \
             patch.object(handle_mod, "GetWindowRect", side_effect=AssertionError("Must not call GetWindowRect")), \
             patch.object(handle_mod, "window_scale_rate", return_value=1.0):
            self.assertEqual(h.screenshot_size, (1280, 720))
            mock_crect.assert_called_once_with(123)

        h_bad = object.__new__(Handle)
        h_bad.emulator_family = EmulatorFamily.FAMILY_OTHER
        h_bad.screenshot_handle_num = 456
        with patch.object(handle_mod, "is_handle_valid", return_value=True), \
             patch.object(handle_mod, "GetClientRect", return_value=(0, 0, 0, 0)), \
             patch.object(handle_mod, "window_scale_rate", return_value=1.0):
            self.assertIsNone(h_bad.screenshot_size)

        # 非桌面端 screenshot_window_background 使用 GetDC 而非包含边框标题栏的 GetWindowDC
        win = object.__new__(windows_impl.Window)
        win.emulator_family = EmulatorFamily.FAMILY_MUMU
        win.screenshot_handle_num = 789
        win.__dict__["screenshot_size"] = (1280, 720)
        fake_bitmap = MagicMock()
        fake_bitmap.GetBitmapBits.return_value = np.zeros(1280 * 720 * 4, dtype=np.uint8).tobytes()
        fake_mfc_dc = MagicMock()
        fake_save_dc = MagicMock()
        fake_mfc_dc.CreateCompatibleDC.return_value = fake_save_dc

        with patch.object(windows_impl, "IsWindow", return_value=True), \
             patch.object(windows_impl, "IsIconic", return_value=False), \
             patch.object(windows_impl, "GetDC", return_value=555) as mock_get_dc, \
             patch.object(windows_impl, "GetWindowDC", side_effect=AssertionError("Must not call GetWindowDC")), \
             patch.object(windows_impl, "ReleaseDC") as mock_release_dc, \
             patch.object(windows_impl, "CreateDCFromHandle", return_value=fake_mfc_dc), \
             patch.object(windows_impl, "CreateBitmap", return_value=fake_bitmap), \
             patch.object(windows_impl, "DeleteObject"):
            img = win.screenshot_window_background()
            self.assertEqual(img.shape, (720, 1280, 3))
            mock_get_dc.assert_called_once_with(789)
            mock_release_dc.assert_called_once_with(789, 555)

    def test_device_screenshot_scrcpy_no_shared_mutable_class_attrs(self):
        # 类属性本身不持有可变的跨实例队列/锁/集合
        self.assertFalse(hasattr(Device, "detect_record"))
        self.assertFalse(hasattr(Device, "click_record"))
        self.assertFalse(hasattr(Screenshot, "_last_save_time"))
        self.assertFalse(hasattr(ScrcpyCore, "_scrcpy_control_socket_lock"))

        d1 = object.__new__(Device)
        d2 = object.__new__(Device)
        d1._init_runtime_state()
        d2._init_runtime_state()
        d1.detect_record.add("BTN_A")
        self.assertEqual(d2.detect_record, set())

        cfg = SimpleNamespace(
            script=SimpleNamespace(
                optimization=SimpleNamespace(screenshot_interval=0.1, combat_screenshot_interval=1.0),
                device=SimpleNamespace(screenshot_method="nemu_ipc"),
            )
        )
        s = object.__new__(Screenshot)
        s._screenshot_interval = MagicMock(limit=0.1)
        s.config = cfg
        s.screenshot_interval_set()
        self.assertEqual(s._screenshot_interval.limit, 0.1)

        with patch.object(Connection, "__init__", lambda self, c: None):
            c1 = ScrcpyCore("cfg1")
            c2 = ScrcpyCore("cfg2")
        self.assertIsNot(c1._scrcpy_control_socket_lock, c2._scrcpy_control_socket_lock)

    def test_control_connection_emulator_and_config_manual_fixes(self):
        self.assertEqual(ConfigManual.SCRCPY_FILEPATH_LOCAL, "./bin/scrcpy/scrcpy-server-v1.20.jar")
        self.assertEqual(ConfigManual.SCRCPY_FILEPATH_REMOTE, "/data/local/tmp/scrcpy-server-v1.20.jar")

        ctrl = object.__new__(Control)
        ctrl.config = SimpleNamespace(script=SimpleNamespace(device=SimpleNamespace(control_method="ADB")))
        ctrl.handle_control_check = MagicMock()
        ctrl.sleep = MagicMock()
        ctrl.click = MagicMock()
        ctrl.swipe_adb = MagicMock()

        ctrl.multi_click((120, 240), 2, interval=0)
        self.assertEqual(ctrl.click.call_count, 2)
        ctrl.click.assert_called_with(120, 240, control_check=False, control_name="(120, 240)")

        ctrl.drag((10, 20), (100, 200))
        ctrl.swipe_adb.assert_called_once()

        # adb_reverse 应调用 adb_reverse_remove 而非 adb_forward_remove
        conn = object.__new__(Connection)
        conn.config = SimpleNamespace(FORWARD_PORT_RANGE=(20000, 21000))
        conn.adb = MagicMock()
        conn.adb.reverse_list.return_value = [
            SimpleNamespace(remote="tcp:999", local="tcp:20001"),
            SimpleNamespace(remote="tcp:999", local="tcp:20002"),
        ]
        conn.adb_reverse_remove = MagicMock()
        conn.adb_forward_remove = MagicMock(side_effect=AssertionError("Must not call adb_forward_remove"))
        port = conn.adb_reverse("tcp:999")
        self.assertEqual(port, 20001)
        conn.adb_reverse_remove.assert_called_once_with("tcp:20002")

        # emulator_restart 读取 script.device.emulatorinfo_type
        emu = object.__new__(EmulatorManager)
        emu.serial = "127.0.0.1:16384"
        emu.config = SimpleNamespace(script=SimpleNamespace(device=SimpleNamespace(emulatorinfo_type="auto")))
        emu.detect_emulator = MagicMock(return_value=("emu_inst", 0))
        emu.emulator_kill = MagicMock(return_value=True)
        emu.emulator_start = MagicMock(return_value=True)
        with patch("os.name", "nt"):
            self.assertTrue(emu.emulator_restart())
        emu.detect_emulator.assert_called_once()

    def test_capture_std_fallback_and_thread_safety(self):
        fake_out = io.StringIO()
        fake_err = io.StringIO()
        with patch.object(sys, "stdout", fake_out), patch.object(sys, "stderr", fake_err):
            with CaptureStd() as cap:
                print("hello_cap")
                print("err_cap", file=sys.stderr)
            self.assertIn(b"hello_cap", cap.stdout)
            self.assertIn(b"err_cap", cap.stderr)

            # 嵌套与异常下均安全释放锁和恢复 stdout/stderr
            with self.assertRaises(RuntimeError):
                with CaptureNemuIpc() as outer:
                    with CaptureNemuIpc() as inner:
                        self.assertIs(outer, outer)
                        print("nested_line")
                    raise RuntimeError("boom")
            self.assertIs(sys.stdout, fake_out)
            self.assertIs(sys.stderr, fake_err)

    def test_main_manager_config_cache_and_config_reload_task_delay_getattr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg_dir = root / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            cfg_file = cfg_dir / "demo_cfg.json"
            cfg_file.write_text(json.dumps({"config_name": "demo_cfg"}), encoding="utf-8")

            with patch.object(ConfigManager, "all_script_files", return_value=["demo_cfg"]), \
                 patch("module.server.main_manager.filepath_config", side_effect=lambda n: str(cfg_dir / f"{n}.json")), \
                 patch("module.config.config.filepath_config", side_effect=lambda n: str(cfg_dir / f"{n}.json")), \
                 patch.object(ConfigModel, "read_json", side_effect=lambda n: json.loads((cfg_dir / f"{n}.json").read_text(encoding="utf-8"))), \
                 patch.object(ConfigModel, "write_json", side_effect=lambda n, d: (cfg_dir / f"{n}.json").write_text(json.dumps(d, default=str), encoding="utf-8")):
                manager = MainManager()
                c1 = manager.config_cache("demo_cfg")
                c2 = manager.config_cache("demo_cfg")
                self.assertIs(c1, c2)

                # 文件内容变化触发自动失效重载
                cfg_file.write_text(json.dumps({"config_name": "demo_cfg", "updated": 1}), encoding="utf-8")
                c3 = manager.config_cache("demo_cfg")
                self.assertIsNot(c1, c3)

                manager.invalidate_config_cache("demo_cfg")
                c4 = manager.config_cache("demo_cfg")
                self.assertIsNot(c3, c4)

                # Config.__getattr__ 对不存在字段抛出 AttributeError
                with self.assertRaises(AttributeError):
                    _ = c4.nonexistent_typo_attr

                # task_delay 文件未变时不触发全量 reload，且字符串 interval 正常解析
                with patch.object(c4, "reload", wraps=c4.reload) as mock_reload:
                    c4.task_delay("Orochi", success=True, server=False)
                    mock_reload.assert_not_called()

                    td = c4._parse_timedelta_interval("01 02:03:04")
                    self.assertEqual(td, timedelta(days=1, hours=2, minutes=3, seconds=4))
                    c4.orochi.scheduler.success_interval = "00 03:00:00"
                    start_dt = datetime(2026, 11, 11, 10, 0, 0)
                    c4.task_delay("Orochi", start_time=start_dt, success=True, server=False)
                    self.assertEqual(c4.orochi.scheduler.next_run, start_dt + timedelta(hours=3))

    def test_notifier_and_config_notifier_wiring(self):
        n_bad_yaml = Notifier(":::invalid: [yaml", enable=True)
        self.assertFalse(n_bad_yaml.enable)
        self.assertFalse(n_bad_yaml.push(title="t", content="c"))

        n_no_provider = Notifier("token: abc", enable=True)
        self.assertFalse(n_no_provider.enable)

        fake_provider = MagicMock()
        fake_provider.params = {"required": ["url"]}
        fake_provider.notify.return_value = SimpleNamespace(status_code=200)
        custom_cls = type(fake_provider)

        with patch("module.notify.notify.Custom", custom_cls), \
             patch("module.notify.notify.get_notifier", return_value=fake_provider):
            n_ok = Notifier("provider: custom\nurl: http://example.com\ndata: null\n", enable=True)
            n_ok.config_name = "oas1"
            self.assertTrue(n_ok.enable)
            self.assertTrue(n_ok.push(title="Hello", content="World"))
            self.assertTrue(n_ok.push(title="Again", content="Second"))
            # 不重复累加前缀 oas1 oas1
            self.assertEqual(fake_provider.notify.call_args.kwargs["title"], "oas1 Again")

        # Config.notifier 读取 script.error.notify_enable / notify_config 并透传 BaseTask.push_notify
        cfg = object.__new__(Config)
        cfg.config_name = "oas_test"
        cfg.model = ConfigModel(config_name="oas_test")
        cfg.model.script.error.notify_enable = True
        cfg.model.script.error.notify_config = "provider: custom\nurl: http://127.0.0.1"
        with patch("module.notify.notify.get_notifier", return_value=fake_provider):
            n_cfg = cfg.notifier
            self.assertTrue(n_cfg.enable)
            self.assertEqual(n_cfg.config_name, "oas_test")

        task = BaseTask.__new__(BaseTask)
        task.name = "DemoTask"
        task.config = SimpleNamespace(notifier=MagicMock(enable=True, push=MagicMock(return_value=True)))
        task.push_notify(content="msg")
        task.config.notifier.push.assert_called_once_with(title="DemoTask", content="msg")

    def test_script_syncs_device_config_save_error_log_and_game_not_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = Path.cwd()
            import os
            os.chdir(tmp)
            try:
                # 用真实 Config 属性行为验证 _reload_config 更新 dev.config
                cfg1 = SimpleNamespace(
                    script=SimpleNamespace(error=SimpleNamespace(save_error=True, error_count=0)),
                    model=SimpleNamespace(running_task="Orochi"),
                    task=SimpleNamespace(command="Orochi"),
                    notifier=MagicMock(),
                    task_call=MagicMock(),
                )
                cfg2 = SimpleNamespace(
                    script=SimpleNamespace(error=SimpleNamespace(save_error=True, error_count=0)),
                    model=SimpleNamespace(running_task="Orochi"),
                    task=None,
                    notifier=MagicMock(),
                    task_call=MagicMock(),
                )
                s2 = Script.__new__(Script)
                s2.config_name = "my_oas_1"
                s2.failure_record = {}
                fake_dev = SimpleNamespace(config=cfg1, package="pkg", sleep=MagicMock())
                s2.__dict__["config"] = cfg1
                s2.__dict__["device"] = fake_dev
                with patch("module.config.config.Config", return_value=cfg2):
                    reloaded = s2._reload_config()
                    self.assertIs(reloaded, cfg2)
                    self.assertIs(fake_dev.config, cfg2)

                # 设备未初始化时 save_error_log 不会触发 self.device 初始化，且缺少 log/error 与横幅时保留日志并建目录
                s3 = Script.__new__(Script)
                s3.config_name = "my_oas_1"
                s3.failure_record = {"Orochi": 1}
                s3.__dict__["config"] = cfg1
                log_path = Path(tmp) / "today.log"
                log_path.write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")
                with patch("script.logger") as mock_logger, \
                     patch.object(Script, "device", new_callable=lambda: property(lambda self: self.fail("Should not initialize device"))):
                    mock_logger.log_file = str(log_path)
                    s3.save_error_log(RuntimeError("crash"))

                dirs = list((Path(tmp) / "log" / "error").iterdir())
                self.assertEqual(len(dirs), 1)
                self.assertTrue(dirs[0].name.startswith("my_oas_1_"))
                content = (dirs[0] / "log.txt").read_text(encoding="utf-8")
                self.assertIn("line1", content)
                self.assertIn("line4", content)

                # GameNotRunningError 返回 False 以便 cumulative failure count 正常递增
                s3.exception_handler = MagicMock()
                self.assertFalse(s3._handle_task_exception(GameNotRunningError("died"), "Orochi"))
                cfg1.task_call.assert_called_once_with("Restart")
            finally:
                os.chdir(old_cwd)

    def test_anti_ban_persistence_and_daily_cap_after_rest(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "antiban.json"
            ab_cfg = SimpleNamespace(
                enable=True,
                sleep_start=datetime.strptime("02:00:00", "%H:%M:%S").time(),
                sleep_end=datetime.strptime("02:00:00", "%H:%M:%S").time(),
                daily_active_limit=timedelta(hours=1),
                long_rest_duration=timedelta(minutes=30),
            )
            now = datetime(2026, 11, 11, 10, 0, 0)
            guard1 = AntiBanGuard(state_file=state_path)
            guard1.record_active(3600.0, now=now)
            wake1 = guard1.wake_time(now, ab_cfg)
            self.assertGreaterEqual(wake1, datetime(2026, 11, 12, 0, 0, 0))

            # 重启恢复状态后在同一天仍受每日活跃上限约束
            guard2 = AntiBanGuard(state_file=state_path)
            after_rest = now + timedelta(minutes=35)
            wake2 = guard2.wake_time(after_rest, ab_cfg)
            self.assertGreaterEqual(wake2, datetime(2026, 11, 12, 0, 0, 0))

            # 次日零点之后自动重置清零
            next_day = datetime(2026, 11, 12, 9, 0, 0)
            self.assertIsNone(guard2.wake_time(next_day, ab_cfg))

    def test_power_manager_per_thread_isolation(self):
        PowerManager._thread_refs.clear()
        fake_k32 = SimpleNamespace(SetThreadExecutionState=MagicMock())
        fake_windll = SimpleNamespace(kernel32=fake_k32)

        with patch("sys.platform", "win32"), patch("ctypes.windll", fake_windll, create=True):
            PowerManager.acquire()
            main_tid = threading.get_ident()
            self.assertTrue(PowerManager.is_thread_active(main_tid))

            def worker():
                PowerManager.acquire()
                self.assertTrue(PowerManager.is_thread_active())
                PowerManager.release()
                self.assertFalse(PowerManager.is_thread_active())

            t = threading.Thread(target=worker)
            t.start()
            t.join()

            # 子线程释放不应清零主线程的保活引用
            self.assertTrue(PowerManager.is_thread_active(main_tid))
            PowerManager.release()
            self.assertFalse(PowerManager.is_thread_active(main_tid))
            # 两个线程各有一次释放调用 ES_CONTINUOUS
            es_cont_calls = [c.args[0] for c in fake_k32.SetThreadExecutionState.call_args_list if c.args[0] == ES_CONTINUOUS]
            self.assertEqual(len(es_cont_calls), 2)

    def test_sensitive_info_and_script_name_normalization_with_underscores(self):
        sample = 'File "D:\\Projects\\OnmyojiAutoScript\\script.py"\n[Adb_binary] C:\\Users\\Alice\\OnmyojiAutoScript\\adb.exe'
        redacted = handle_sensitive_text(sample)
        self.assertIn("fakepath\\OnmyojiAutoScript", redacted)
        self.assertNotIn("D:\\Projects", redacted)
        self.assertNotIn("Alice", redacted)

        # 带下划线的配置名不应被错误截断
        self.assertEqual(normalize_log_name("my_oas_1"), "my_oas_1")
        self.assertEqual(normalize_script_name("my_oas_1"), "my_oas_1")
        self.assertEqual(LogStatsService._normalize_script_name("my_oas_1"), "my_oas_1")
        self.assertEqual(normalize_script_name("../bad:name"), "__bad_name")


if __name__ == "__main__":
    unittest.main()
