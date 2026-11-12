# This Python file uses the following encoding: utf-8
import os
import types
import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

import tasks.Exploration.page as exp_pages
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import BattleAction
from tasks.Exploration.config import Exploration, UserStatus
from tasks.Exploration.script_task import ScriptTask
from tasks.GameUi.page import page_battle_prepare, page_battle_result


class DummyBattlePrepareTask(ScriptTask):
    """隔离设备与 RPC 的探索战斗准备测试桩。"""

    def __init__(self):
        self.device = MagicMock()
        self.device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.device.image_frame_id = 1
        self.device.detect_record = set()
        self.interval_timer = {}
        self.animates = {}
        self.current_count = 0
        self._custom_pages_registered = True
        self._battle_shared_state = {}
        self._battle_context = None
        self.screenshot_calls = 0

        exploration_model = Exploration(
            general_battle_config=GeneralBattleConfig(lock_team_enable=True)
        )
        self.config = types.SimpleNamespace(
            exploration=exploration_model,
            model=types.SimpleNamespace(
                exploration=exploration_model,
                script=types.SimpleNamespace(
                    optimization=types.SimpleNamespace(
                        schedule_rule="fifo",
                    )
                ),
            ),
            global_game=types.SimpleNamespace(
                emergency=types.SimpleNamespace(
                    friend_invitation=types.SimpleNamespace(accept=False)
                ),
                battle_timeout=180,
            ),
        )

    def screenshot(self):
        self.screenshot_calls += 1
        return self.device.image


class _ExpiredTimer:
    """模拟立即超时的 Timer，验证 fire 循环不会在无按钮无页面时死循环。"""

    def __init__(self, limit, count=0):
        self.limit = limit
        self._started = False

    def start(self):
        self._started = True
        return self

    def reached(self):
        return True


class TestExplorationBattlePrepare(unittest.TestCase):

    def test_exploration_config_disables_lock_team_and_clicks_prepare_immediately(self):
        task = DummyBattlePrepareTask()
        cfg = task._config
        self.assertFalse(cfg.general_battle_config.lock_team_enable)
        self.assertEqual(task.limit_time, timedelta(minutes=30))

        ctx = task._build_context(cfg.general_battle_config, buff=[], battle_key="default")
        task._battle_context = ctx
        with patch.object(task, "appear_then_click", return_value=False) as mock_click, \
             patch.object(task, "switch_preset_team", return_value=True), \
             patch.object(task, "check_and_open_buff", return_value=True):
            action = task._handle_prepare(ctx, cfg.general_battle_config)

        self.assertEqual(action, BattleAction.CONTINUE)
        mock_click.assert_any_call(task.I_PREPARE_HIGHLIGHT, interval=0.8)
        self.assertFalse(ctx.prepare_click_timer.started())

    def test_fire_uses_detect_page_in_reuses_first_frame_and_records_battle_page(self):
        task = DummyBattlePrepareTask()
        button = MagicMock()
        detect_results = [None, exp_pages.page_battle_prepare]

        with patch.object(task, "get_current_page", side_effect=AssertionError("should not scan all pages")), \
             patch.object(task, "detect_page_in", side_effect=detect_results) as mock_detect, \
             patch.object(task, "appear_then_click", return_value=True) as mock_click:
            ok = task.fire(button)

        self.assertTrue(ok)
        self.assertEqual(task._last_fire_page, exp_pages.page_battle_prepare)
        self.assertEqual(task.screenshot_calls, 1)
        mock_click.assert_called_once_with(button, interval=0.8)
        self.assertEqual(mock_detect.call_count, 2)
        first_args, first_kwargs = mock_detect.call_args_list[0]
        self.assertEqual(
            first_args,
            (exp_pages.page_exp_exit, exp_pages.page_battle_prepare, exp_pages.page_battle),
        )
        self.assertEqual(first_kwargs, {"include_global": False})

    def test_fire_respects_timer_timeout_when_page_and_button_missing(self):
        task = DummyBattlePrepareTask()
        button = MagicMock()

        with patch("tasks.Exploration.base.Timer", _ExpiredTimer), \
             patch.object(task, "detect_page_in", return_value=None) as mock_detect, \
             patch.object(task, "appear_then_click", return_value=False) as mock_click:
            ok = task.fire(button)

        self.assertFalse(ok)
        self.assertIsNone(task._last_fire_page)
        mock_detect.assert_not_called()
        mock_click.assert_not_called()

    def test_run_on_exp_main_enters_battle_directly_without_extra_loop(self):
        task = DummyBattlePrepareTask()
        task.user_status = UserStatus.ALONE
        fake_btn = MagicMock()

        def fake_fire(btn):
            task._last_fire_page = exp_pages.page_battle_prepare
            return True

        with patch.object(task, "collect_reward", return_value=False), \
             patch.object(task, "switch_rotate", return_value=False), \
             patch.object(task, "get_fire_button", return_value=fake_btn), \
             patch.object(task, "fire", side_effect=fake_fire), \
             patch.object(task, "run_on_battle") as mock_run_battle, \
             patch.object(task, "swipe") as mock_swipe:
            task.run_on_exp_main()

        mock_run_battle.assert_called_once_with(skip_first_screenshot=True)
        mock_swipe.assert_not_called()

    def test_run_general_battle_skip_first_screenshot_uses_current_frame_first(self):
        task = DummyBattlePrepareTask()
        task.screenshot_calls = 0
        pages_seq = [page_battle_prepare, page_battle_result, None]

        def fake_detect(*args, **kwargs):
            return pages_seq.pop(0) if pages_seq else None

        def fake_appear(target, *args, **kwargs):
            return target in (task.I_WIN, task.I_PREPARE_HIGHLIGHT)

        with patch("tasks.Component.GeneralBattle.general_battle.GameUi.detect_page_in", side_effect=fake_detect), \
             patch.object(task, "appear", side_effect=fake_appear), \
             patch.object(task, "appear_then_click", side_effect=lambda target, *a, **k: target is task.I_PREPARE_HIGHLIGHT) as mock_click:
            win = task.run_general_battle(
                config=task._config.general_battle_config,
                exit_matcher=lambda: True,
                skip_first_screenshot=True,
            )

        self.assertTrue(win)
        # 首帧复用已有画面直接处理 page_battle_prepare，随后两轮各截图一次（共 2 次而非 3 次）
        self.assertEqual(task.screenshot_calls, 2)
        mock_click.assert_any_call(task.I_PREPARE_HIGHLIGHT, interval=0.8)

    def test_prepare_assets_have_search_margins_and_match_offline_screenshot(self):
        self.assertEqual(GeneralBattleAssets.I_PRESET.roi_back, (16, 634, 80, 78))
        self.assertEqual(GeneralBattleAssets.I_PREPARE_DARK.roi_back, (1110, 500, 169, 200))

        sample_path = (
            r"C:\Users\13599\.gemini\antigravity\brain\1077feab-b702-401b-ac06-c95d557e9e45"
            r"\.user_uploaded\media_1794494585113_66281385.jpg"
        )
        if not os.path.exists(sample_path):
            self.skipTest("本地离线截图不存在，跳过模板匹配置信度校验")

        raw = cv2.imread(sample_path)
        cropped = raw[36:610, 2:1022]
        frame = cv2.resize(cropped, (1280, 720), interpolation=cv2.INTER_AREA)

        for rule in (
            GeneralBattleAssets.I_BUFF,
            GeneralBattleAssets.I_PREPARE_HIGHLIGHT,
            GeneralBattleAssets.I_PRESET,
        ):
            tmpl = cv2.imread(rule.file)
            rx, ry, rw, rh = rule.roi_back
            res = cv2.matchTemplate(frame[ry:ry + rh, rx:rx + rw], tmpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            self.assertGreaterEqual(max_val, rule.threshold, f"{rule.file} score={max_val:.4f}")


if __name__ == "__main__":
    unittest.main()
