# This Python file uses the following encoding: utf-8
import asyncio
import inspect
import tempfile
import threading
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, WebSocketDisconnect
from starlette.websockets import WebSocketState

from module.server import home_router, log_router, script_router, stats_router
from module.server.config_manager import ConfigManager, ConfigNameError
from module.server.main_manager import MainManager, mm
from module.server.script_process import ScriptProcess, ScriptState
from module.server.script_websocket import ScriptWSManager
from module.server.setting import State


class FakeProcess:
    """模拟子进程对象，覆盖存活、terminate/join 退避与强制 kill 路径。"""

    def __init__(self, alive_sequence: list[bool], exitcode: int | None = 0):
        self._alive_sequence = list(alive_sequence)
        self.exitcode = exitcode
        self.terminated = False
        self.killed = False
        self.closed = False
        self.join_timeouts: list[float | None] = []

    def is_alive(self) -> bool:
        if self._alive_sequence:
            if len(self._alive_sequence) > 1:
                return self._alive_sequence.pop(0)
            return self._alive_sequence[0]
        return False

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)

    def close(self) -> None:
        self.closed = True


class TestServerLifecycleAndRoutes(unittest.IsolatedAsyncioTestCase):

    def test_main_manager_has_no_background_push_thread(self):
        before_threads = {t.ident for t in threading.enumerate()}
        with patch.object(ConfigManager, "all_script_files", return_value=[]):
            manager = MainManager()
        after_threads = {t.ident for t in threading.enumerate()}
        self.assertEqual(before_threads, after_threads)
        self.assertFalse(hasattr(manager, "push_data_thread"))
        self.assertEqual(manager._broadcast_tasks, {})

    async def test_main_manager_single_loop_broadcast_and_graceful_shutdown(self):
        fake_proc = FakeProcess([True, False], exitcode=0)
        with patch.object(ConfigManager, "all_script_files", return_value=["template"]):
            manager = MainManager()
        script_p = manager.script_process["template"]
        script_p._process = fake_proc
        script_p.state = ScriptState.RUNNING

        fake_server = SimpleNamespace(should_exit=False)
        old_server = State.uvicorn_server
        old_kill_flag = MainManager.signal_kill_server
        State.uvicorn_server = fake_server
        try:
            manager.start_broadcast_loop()
            manager.ensure_script_tasks("template")
            self.assertIn("coroutine_state_template", manager._broadcast_tasks)
            self.assertIn("coroutine_log_template", manager._broadcast_tasks)

            manager.request_server_shutdown(delay=0.02)
            self.assertTrue(MainManager.signal_kill_server)
            await asyncio.sleep(0.08)
            self.assertTrue(fake_server.should_exit)

            await manager.shutdown()
            self.assertEqual(manager._broadcast_tasks, {})
            self.assertIsNone(manager._supervisor_task)
            self.assertEqual(script_p.state, ScriptState.INACTIVE)
            self.assertTrue(fake_proc.terminated)
            self.assertTrue(fake_proc.closed)
            self.assertIsNone(script_p.log_pipe_out)
            self.assertIsNone(script_p.state_queue)
        finally:
            State.uvicorn_server = old_server
            MainManager.signal_kill_server = old_kill_flag

    async def test_script_process_stop_force_kills_unresponsive_child_and_closes_ipc(self):
        with patch.object(ConfigManager, "all_script_files", return_value=["template"]):
            proc_mgr = ScriptProcess("template")

        # terminate 后仍存活，触发 kill + join(1.0)
        stubborn = FakeProcess([True, True, False], exitcode=-9)
        proc_mgr._process = stubborn
        proc_mgr.state = ScriptState.RUNNING

        await proc_mgr.stop()
        self.assertEqual(proc_mgr.state, ScriptState.INACTIVE)
        self.assertIsNone(proc_mgr._process)
        self.assertTrue(stubborn.terminated)
        self.assertTrue(stubborn.killed)
        self.assertEqual(stubborn.join_timeouts, [3.0, 1.0])
        self.assertTrue(stubborn.closed)
        self.assertIsNone(proc_mgr.log_pipe_out)
        self.assertIsNone(proc_mgr.log_pipe_in)
        self.assertIsNone(proc_mgr.state_queue)

    async def test_kill_server_route_schedules_uvicorn_exit_without_killing_workers_early(self):
        with patch.object(mm, "request_server_shutdown") as mock_shutdown:
            res = await home_router.kill_server()
        self.assertEqual(res, "success")
        mock_shutdown.assert_called_once()

    def test_blocking_routes_are_sync_and_dead_sse_routes_removed(self):
        sync_endpoints = [
            home_router.image_server_info,
            home_router.ocr_server_info,
            home_router.notify_test,
            home_router.get_chinese_translate,
            home_router.chinese_translate,
            home_router.additional_translate,
            home_router.export_diagnostic,
            script_router.script_menu,
            script_router.config_list,
            script_router.config_copy,
            script_router.config_new_name,
            script_router.config_all,
            script_router.config_export,
            script_router.config_task_export,
            script_router.config_task_copy_json,
            script_router.task_copy,
            script_router.task_group_copy,
            script_router.get_script_task,
            script_router.set_script_task,
            log_router.get_error_logs,
            log_router.get_error_log_detail,
            log_router.get_error_log_image,
            log_router.get_log_window,
            stats_router.stats_available_dates,
            stats_router.stats_snapshot,
        ]
        for fn in sync_endpoints:
            self.assertFalse(inspect.iscoroutinefunction(fn), f"{fn.__name__} should be sync def")

        script_paths = {route.path for route in script_router.script_app.routes}
        self.assertNotIn("/{script_name}/state", script_paths)
        self.assertNotIn("/{script_name}/log", script_paths)

    async def test_config_routes_reject_path_traversal_and_template(self):
        with self.assertRaises(HTTPException) as ctx_copy:
            script_router.config_copy("../evil", "template")
        self.assertEqual(ctx_copy.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx_rename:
            await script_router.config_rename("template", "oas99")
        self.assertEqual(ctx_rename.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx_rename_trav:
            await script_router.config_rename("oas1", "../evil")
        self.assertEqual(ctx_rename_trav.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx_del_tpl:
            await script_router.config_delete("template")
        self.assertEqual(ctx_del_tpl.exception.status_code, 400)

        with self.assertRaises(HTTPException) as ctx_del_trav:
            await script_router.config_delete("../../bad")
        self.assertEqual(ctx_del_trav.exception.status_code, 400)

    def test_config_manager_rename_and_delete_validate_names_and_real_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            (tmp_root / "config").mkdir()
            (tmp_root / "config" / "template.json").write_text('{"config_name": "oas"}', encoding="utf-8")
            with patch("pathlib.Path.cwd", return_value=tmp_root):
                ConfigManager.copy("demo1", "template")
                demo1_path = tmp_root / "config" / "demo1.json"
                self.assertTrue(demo1_path.exists())
                self.assertIn('"demo1"', demo1_path.read_text(encoding="utf-8"))
                self.assertTrue(ConfigManager.rename("demo1", "demo2"))
                demo2_path = tmp_root / "config" / "demo2.json"
                self.assertTrue(demo2_path.exists())
                self.assertIn('"demo2"', demo2_path.read_text(encoding="utf-8"))
                self.assertTrue(ConfigManager.delete("demo2"))
                self.assertFalse(demo2_path.exists())
                with self.assertRaises(ConfigNameError):
                    ConfigManager.copy("../bad", "template")

    def test_set_script_task_validates_boolean_and_time_delta(self):
        mock_model = MagicMock()
        mock_model.script_set_arg.return_value = True
        mock_cfg = SimpleNamespace(model=mock_model)

        with patch.object(mm, "config_cache", return_value=mock_cfg):
            with self.assertRaises(HTTPException) as bad_bool:
                script_router.set_script_task("oas1", "Task", "Group", "enable", "boolean", "invalid_bool")
            self.assertEqual(bad_bool.exception.status_code, 400)

            res = script_router.set_script_task("oas1", "Task", "Group", "limit_time", "time_delta", "12 01:02:03")
            self.assertTrue(res)
            args, _ = mock_model.script_set_arg.call_args
            self.assertEqual(args[3], timedelta(days=12, hours=1, minutes=2, seconds=3))

    async def test_websocket_get_state_and_get_schedule_use_unicast_send_json(self):
        ws = MagicMock()
        ws.client_state = WebSocketState.CONNECTED
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_json = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=["get_state", "get_schedule", WebSocketDisconnect()])

        with patch.object(ConfigManager, "all_script_files", return_value=["demo"]):
            proc_mgr = ScriptProcess("demo")

        fake_cfg = MagicMock()
        fake_cfg.pending_task = []
        fake_cfg.waiting_task = []
        fake_cfg.get_schedule_data.return_value = {"running": None, "pending": [], "waiting": []}

        old_entry = mm.script_process.get("demo")
        mm.script_process["demo"] = proc_mgr
        try:
            with patch.object(mm, "config_cache", return_value=fake_cfg), \
                 patch.object(proc_mgr, "broadcast_state", new=AsyncMock()) as mock_broadcast, \
                 patch("module.server.script_router.log_ws_event"):
                await script_router.websocket_endpoint(ws, "demo")

            mock_broadcast.assert_not_awaited()
            # 初始化发送 state + schedule 共 2 次，之后 get_state 和 get_schedule 各单播 1 次，共 4 次
            self.assertEqual(ws.send_json.await_count, 4)
        finally:
            proc_mgr.close_ipc()
            if old_entry is None:
                mm.script_process.pop("demo", None)
            else:
                mm.script_process["demo"] = old_entry

    async def test_websocket_invalid_name_closes_with_1008(self):
        ws = MagicMock()
        ws.close = AsyncMock()
        await script_router.websocket_endpoint(ws, "../bad")
        ws.close.assert_awaited_once()
        _, kwargs = ws.close.call_args
        self.assertEqual(kwargs.get("code"), 1008)


if __name__ == "__main__":
    unittest.main()

