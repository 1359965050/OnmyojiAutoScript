# This Python file uses the following encoding: utf-8
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from module.atom.click import RuleClick
from module.atom.image import RuleImage
from tasks.Exploration.script_task import ScriptTask
from tasks.GameUi.default_pages import page_reward
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.base_task import BaseTask


class DummyRewardTask(BaseTask):
    """隔离设备与截屏的 BaseTask 奖励测试桩。"""

    def __init__(self):
        self.device = MagicMock()
        self.device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.device.image_frame_id = 1
        self.config = MagicMock()
        self.interval_timer = {}
        self.animates = {}

    def screenshot(self):
        return self.device.image


class DummyExplorationTask(ScriptTask):
    """隔离设备与截屏的 Exploration 测试桩。"""

    def __init__(self):
        self.device = MagicMock()
        self.device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.device.image_frame_id = 1
        self.config = MagicMock()
        self.interval_timer = {}
        self.animates = {}

    def screenshot(self):
        return self.device.image


class TestExplorationRewardPopup(unittest.TestCase):

    def setUp(self):
        self.base_task = DummyRewardTask()
        self.exp_task = DummyExplorationTask()

    def test_page_reward_includes_scroll_reward_asset(self):
        self.assertTrue(hasattr(GlobalGameAssets, "I_UI_REWARD_SCROLL"))
        targets = [child.target for child in page_reward.recognizer.children]
        self.assertIn(GlobalGameAssets.I_UI_REWARD_SCROLL, targets)

    def test_ui_reward_appear_and_click_supports_scroll_variant(self):
        def fake_appear(target, interval=None, threshold=None):
            return target is self.base_task.I_UI_REWARD_SCROLL

        with patch.object(self.base_task, "appear", side_effect=fake_appear), \
             patch.object(self.base_task, "click", return_value=True):
            self.assertTrue(self.base_task.ui_reward_appear())
            self.assertTrue(self.base_task.ui_reward_appear_click())

        self.base_task.device.click.assert_called_once()
        cx, cy = self.base_task.device.click.call_args[0]
        rx, ry, rw, rh = self.base_task.C_UI_REWARD.roi_front
        self.assertTrue(rx <= cx <= rx + rw)
        self.assertTrue(ry <= cy <= ry + rh)

    def test_ui_get_reward_waits_until_scroll_reward_disappears(self):
        target = RuleImage(
            roi_front=(100, 100, 20, 20),
            roi_back=(100, 100, 20, 20),
            threshold=0.8,
            method="Template matching",
            file="./tasks/Exploration/res/res_battle_reward.png",
        )
        state = {"stage": "target"}
        scroll_checks = 0

        def fake_appear(rule, interval=None, threshold=None):
            nonlocal scroll_checks
            if rule is target:
                return state["stage"] == "target"
            if rule is self.base_task.I_UI_REWARD_SCROLL:
                if state["stage"] == "scroll":
                    scroll_checks += 1
                    if scroll_checks >= 3:
                        state["stage"] = "done"
                        return False
                    return True
                return False
            return False

        def fake_click(x, y, control_name=None):
            if control_name == target.name:
                state["stage"] = "scroll"
            return True

        self.base_task.device.click.side_effect = fake_click
        with patch.object(self.base_task, "appear", side_effect=fake_appear), \
             patch("tasks.base_task.sleep", return_value=None):
            self.assertTrue(self.base_task.ui_get_reward(target, click_interval=0, exit_when_target_gone=True))

        self.assertEqual(state["stage"], "done")
        self.assertGreaterEqual(self.base_task.device.click.call_count, 2)

    def test_collect_reward_closes_lingering_scroll_popup(self):
        scroll_frames = {"left": 2}

        def fake_appear(rule, interval=None, threshold=None):
            if rule is self.exp_task.I_UI_REWARD_SCROLL:
                return scroll_frames["left"] > 0
            return False

        def fake_click(x, y, control_name=None):
            scroll_frames["left"] -= 1
            return True

        self.exp_task.device.click.side_effect = fake_click
        with patch.object(self.exp_task, "appear", side_effect=fake_appear), \
             patch("tasks.Exploration.base.time.sleep", return_value=None):
            self.assertTrue(self.exp_task.collect_reward())

        self.assertEqual(scroll_frames["left"], 0)
        self.assertEqual(self.exp_task.device.click.call_count, 2)

    def test_collect_treasure_box_handles_direct_scroll_popup(self):
        state = {"stage": "box"}

        def fake_appear(rule, interval=None, threshold=None):
            if rule is self.exp_task.I_E_REWARD_BOX_SMALL:
                return state["stage"] == "box"
            if rule is self.exp_task.I_UI_REWARD_SCROLL:
                return state["stage"] == "scroll"
            return False

        def fake_click(x, y, control_name=None):
            if state["stage"] == "box":
                state["stage"] = "scroll"
            elif state["stage"] == "scroll":
                state["stage"] = "done"
            return True

        self.exp_task.device.click.side_effect = fake_click
        with patch.object(self.exp_task, "appear", side_effect=fake_appear), \
             patch("tasks.Exploration.base.time.sleep", return_value=None):
            self.assertTrue(self.exp_task.collect_treasure_box())

        self.assertEqual(state["stage"], "done")


if __name__ == "__main__":
    unittest.main()
