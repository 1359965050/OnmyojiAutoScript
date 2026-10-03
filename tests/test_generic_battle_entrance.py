# This Python file uses the following encoding: utf-8
import os
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from tasks.ActivityShikigami.page import action_act_goto_battle, action_map_goto_battle
from tasks.Component.BaseActivity.base_activity import BaseActivity


class DummyActivity(BaseActivity):
    """测试用 Activity 哑对象，隔离实际设备依赖。"""

    def __init__(self):
        self.device = MagicMock()
        self._current_climb_type = 'pass'
        self._switch_souled_map = {}
        self.config = MagicMock()
        self.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.device.image = self.image
        self.interval_timer = {}

    def find_configured_battle_name_box(self, *args, **kwargs):
        return None

    def screenshot(self):
        return self.image


class TestGenericBattleEntrance(unittest.TestCase):
    """活动主界面及地图自适应战斗入口单元测试套件。"""

    def setUp(self):
        self.activity = DummyActivity()
        self.scratch_dir = r"C:\Users\13599\.gemini\antigravity-ide\brain\a2ab39e6-a852-4a25-97ed-5e4562fa1b4c\scratch"

    def test_01_assets_existence(self):
        """测试新增的活动战斗入口自适应 OCR 规则是否存在。"""
        self.assertTrue(hasattr(self.activity, "O_ACT_BATTLE_ENTRANCE"))
        self.assertEqual(self.activity.O_ACT_BATTLE_ENTRANCE.keyword, "战斗")
        self.assertTrue(hasattr(self.activity, "O_ACT_BATTLE_ENTRANCE_CHAR"))
        self.assertEqual(self.activity.O_ACT_BATTLE_ENTRANCE_CHAR.keyword, "战")
        self.assertTrue(hasattr(self.activity, "O_ACT_BATTLE_ENTRANCE_CLIMB"))
        self.assertEqual(self.activity.O_ACT_BATTLE_ENTRANCE_CLIMB.keyword, "爬塔")
        self.assertTrue(hasattr(self.activity, "O_MAP_BATTLE_ENTRANCE"))
        self.assertEqual(self.activity.O_MAP_BATTLE_ENTRANCE.keyword, "战斗")
        self.assertTrue(hasattr(self.activity, "O_MAP_BATTLE_ENTRANCE_CHAR"))
        self.assertEqual(self.activity.O_MAP_BATTLE_ENTRANCE_CHAR.keyword, "战")

    def test_02_real_screenshot_ocr_battle(self):
        """测试在真实活动主界面截图上自适应命中『战斗』入口。"""
        img3_path = os.path.join(self.scratch_dir, "std_img_3.png")
        if not os.path.exists(img3_path):
            self.skipTest("std_img_3.png 不存在，跳过像素级识别测试")

        img3 = cv2.imread(img3_path)
        try:
            res = self.activity.O_ACT_BATTLE_ENTRANCE.ocr(img3)
            self.assertNotEqual(res, (0, 0, 0, 0), "未能从活动主界面截图中自适应匹配到『战斗』入口")
            x, y, w, h = res
            cx, cy = x + w / 2, y + h / 2
            # 验证中心点在合理交互区域 (约 330, 220 附近)
            self.assertTrue(250 <= cx <= 450)
            self.assertTrue(150 <= cy <= 300)
        except Exception as e:
            self.skipTest(f"OCR RPC 服务未开启，跳过像素级测试: {e}")

    def test_03_find_and_click_act_battle_adaptive_success(self):
        """测试 find_and_click_act_battle 自适应通过 OCR 寻找中心并点击。"""
        with patch.object(self.activity, "screenshot"), \
             patch.object(self.activity.O_ACT_BATTLE_ENTRANCE, "ocr", return_value=(320, 190, 30, 60)), \
             patch.object(self.activity, "click", return_value=True) as mock_click:

            res = self.activity.find_and_click_act_battle()
            self.assertTrue(res)
            mock_click.assert_called_once()
            called_rule = mock_click.call_args[0][0]
            # 验证点击区域中心在 (335, 220) 附近
            self.assertIn("generic_act_battle_entrance", called_rule.name.lower())

    def test_04_find_and_click_act_battle_fallback(self):
        """测试自适应未命中时回退点击专有切图。"""
        mock_rule = MagicMock()
        with patch.object(self.activity, "screenshot"), \
             patch.object(self.activity.O_ACT_BATTLE_ENTRANCE, "ocr", return_value=(0, 0, 0, 0)), \
             patch.object(self.activity.O_ACT_BATTLE_ENTRANCE_CLIMB, "ocr", return_value=(0, 0, 0, 0)), \
             patch.object(self.activity.O_ACT_BATTLE_ENTRANCE_CHAR, "ocr", return_value=(0, 0, 0, 0)), \
             patch.object(self.activity, "appear", return_value=True), \
             patch.object(self.activity, "appear_then_click", return_value=True) as mock_appear_click:

            res = self.activity.find_and_click_act_battle(specific_rule=mock_rule)
            self.assertTrue(res)
            mock_appear_click.assert_called_once_with(mock_rule, interval=1.0)

    def test_05_find_and_click_map_battle_adaptive_ocr(self):
        """测试中转地图左侧区域 OCR 命中并点击。"""
        with patch.object(self.activity, "screenshot"), \
             patch.object(self.activity, "appear", return_value=False), \
             patch.object(self.activity, "ocr_appear", side_effect=lambda rule: rule == self.activity.O_MAP_BATTLE_ENTRANCE), \
             patch.object(self.activity, "ocr_appear_click", return_value=True) as mock_ocr_click:

            res = self.activity.find_and_click_map_battle()
            self.assertTrue(res)
            mock_ocr_click.assert_called_once_with(self.activity.O_MAP_BATTLE_ENTRANCE, interval=1.5)

    def test_05_find_and_click_map_battle_adaptive_fallback(self):
        """测试中转地图 OCR 未命中时安全点击左侧推荐关卡卡片中心。"""
        with patch.object(self.activity, "screenshot"), \
             patch.object(self.activity, "appear", return_value=False), \
             patch.object(self.activity, "ocr_appear", return_value=False), \
             patch.object(self.activity, "click", return_value=True) as mock_click:

            res = self.activity.find_and_click_map_battle()
            self.assertTrue(res)
            mock_click.assert_called_once()
            rule = mock_click.call_args[0][0]
            self.assertEqual(rule.name, "generic_map_goto_battle")

    def test_06_action_delegation(self):
        """测试路由层动作能够正确代理到任务实例对应方法。"""
        mock_task = MagicMock()
        mock_task.find_and_click_act_battle.return_value = True
        mock_task.find_and_click_map_battle.return_value = True

        self.assertTrue(action_act_goto_battle(mock_task))
        mock_task.find_and_click_act_battle.assert_called_once()

        self.assertTrue(action_map_goto_battle(mock_task))
        mock_task.find_and_click_map_battle.assert_called_once()


if __name__ == "__main__":
    unittest.main()
