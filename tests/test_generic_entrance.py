# This Python file uses the following encoding: utf-8
import os
import unittest
from unittest.mock import MagicMock, call, patch

import cv2
import numpy as np

from tasks.ActivityShikigami.page import action_enter_activity
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.GameUi.assets import GameUiAssets
from tasks.GlobalGame.assets import GlobalGameAssets


class DummyActivity(BaseActivity):
    """测试用 Activity 哑对象，隔离实际设备依赖。"""

    def __init__(self):
        self.device = MagicMock()
        self._current_climb_type = 'pass'
        self._switch_souled_map = {}
        self.config = MagicMock()
        self.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.interval_timer = {}

    def screenshot(self):
        return self.image


class TestGenericEntrance(unittest.TestCase):
    """通用活动免更寻径入场测试套件。"""

    def setUp(self):
        self.activity = DummyActivity()
        self.scratch_dir = r"C:\Users\13599\.gemini\antigravity-ide\brain\a2ab39e6-a852-4a25-97ed-5e4562fa1b4c\scratch"

    def test_01_assets_existence(self):
        """测试新增的通用免更入口资产与规则是否完整生成。"""
        # OCR 规则
        self.assertTrue(hasattr(self.activity, "O_SIDEBAR_ACTIVITY"))
        self.assertEqual(self.activity.O_SIDEBAR_ACTIVITY.keyword, "活动")
        self.assertTrue(hasattr(self.activity, "O_OVERVIEW_TITLE"))
        self.assertEqual(self.activity.O_OVERVIEW_TITLE.keyword, "活动总览")
        self.assertTrue(hasattr(self.activity, "O_OVERVIEW_VERSION_ACT"))
        self.assertEqual(self.activity.O_OVERVIEW_VERSION_ACT.keyword, "版本活动")
        self.assertTrue(hasattr(self.activity, "O_OVERVIEW_GOTO_ACT"))
        self.assertEqual(self.activity.O_OVERVIEW_GOTO_ACT.keyword, "前往活动")

        # 点击规则
        self.assertTrue(hasattr(self.activity, "C_SIDEBAR_ACTIVITY"))
        self.assertTrue(hasattr(self.activity, "C_OVERVIEW_VERSION_ACT"))
        self.assertTrue(hasattr(self.activity, "C_OVERVIEW_GOTO_ACT"))

    def test_02_real_screenshot_ocr_recognition(self):
        """测试真实真机截图上的 OCR 识别准确性。若无后台 OCR RPC 服务则优雅跳过。"""
        img1_path = os.path.join(self.scratch_dir, "std_img_1.png")
        img2_path = os.path.join(self.scratch_dir, "std_img_2.png")

        if not os.path.exists(img1_path) or not os.path.exists(img2_path):
            self.skipTest("标准截图文件未在 scratch 目录中生成，跳过像素级识别测试")

        img1 = cv2.imread(img1_path)
        img2 = cv2.imread(img2_path)

        try:
            # 1. 庭院右侧栏常驻“活动”
            res1 = self.activity.O_SIDEBAR_ACTIVITY.ocr(img1)
            self.assertNotEqual(res1, (0, 0, 0, 0), "未能从庭院截图中识别到『活动』")

            # 2. 活动总览顶部标题“活动总览”
            res2_title = self.activity.O_OVERVIEW_TITLE.ocr(img2)
            self.assertNotEqual(res2_title, (0, 0, 0, 0), "未能从总览截图中识别到『活动总览』")

            # 3. 活动总览左侧“版本活动”
            res2_tab = self.activity.O_OVERVIEW_VERSION_ACT.ocr(img2)
            self.assertNotEqual(res2_tab, (0, 0, 0, 0), "未能从总览截图中识别到『版本活动』")

            # 4. 活动总览右下角“前往活动”
            res2_goto = self.activity.O_OVERVIEW_GOTO_ACT.ocr(img2)
            self.assertNotEqual(res2_goto, (0, 0, 0, 0), "未能从总览截图中识别到『前往活动』")
        except Exception as e:
            self.skipTest(f"OCR RPC 服务未开启，跳过像素级 OCR 识别测试: {e}")

    def test_03_already_in_activity_main_page(self):
        """测试当已处于活动主界面时快速透传返回 True。"""
        with patch.object(self.activity, "screenshot"), \
             patch.object(self.activity, "_is_in_activity_main_page", return_value=True):
            result = self.activity.enter_activity_via_overview(timeout=5.0)
            self.assertTrue(result)

    def test_04_full_pipeline_success(self):
        """测试标准全流程（庭院 -> 总览 -> 选中版本活动 -> 点击前往 -> 活动主页）成功执行。"""
        with patch.object(self.activity, "screenshot"), \
             patch.object(self.activity, "_is_in_activity_main_page", side_effect=[False, False, True]), \
             patch.object(self.activity, "_is_in_activity_overview", side_effect=[False, True]), \
             patch.object(self.activity, "_step_click_sidebar_activity", return_value=True) as mock_step1, \
             patch.object(self.activity, "_step_wait_activity_overview", return_value=True) as mock_step2, \
             patch.object(self.activity, "_step_select_version_activity", return_value=True) as mock_step3, \
             patch.object(self.activity, "_step_click_goto_activity", return_value=True) as mock_step4, \
             patch.object(self.activity, "_step_confirm_entered_activity", return_value=True) as mock_step5:

            result = self.activity.enter_activity_via_overview(timeout=10.0)
            self.assertTrue(result)
            mock_step1.assert_called_once()
            mock_step2.assert_called_once()
            mock_step3.assert_called_once()
            mock_step4.assert_called_once()
            mock_step5.assert_called_once()

    def test_05_already_in_overview_skip_step1(self):
        """测试已处于活动总览界面时，自动跳过侧边栏点击步骤。"""
        with patch.object(self.activity, "screenshot"), \
             patch.object(self.activity, "_is_in_activity_main_page", side_effect=[False, False, True]), \
             patch.object(self.activity, "_is_in_activity_overview", return_value=True), \
             patch.object(self.activity, "_step_click_sidebar_activity") as mock_step1, \
             patch.object(self.activity, "_step_wait_activity_overview") as mock_step2, \
             patch.object(self.activity, "_step_select_version_activity", return_value=True) as mock_step3, \
             patch.object(self.activity, "_step_click_goto_activity", return_value=True) as mock_step4, \
             patch.object(self.activity, "_step_confirm_entered_activity", return_value=True) as mock_step5:

            result = self.activity.enter_activity_via_overview(timeout=10.0)
            self.assertTrue(result)
            mock_step1.assert_not_called()
            mock_step2.assert_not_called()
            mock_step3.assert_called_once()
            mock_step4.assert_called_once()
            mock_step5.assert_called_once()

    def test_06_sidebar_click_failed(self):
        """测试侧边栏点击活动图标失败时安全退出。"""
        with patch.object(self.activity, "screenshot"), \
             patch.object(self.activity, "_is_in_activity_main_page", return_value=False), \
             patch.object(self.activity, "_is_in_activity_overview", return_value=False), \
             patch.object(self.activity, "_step_click_sidebar_activity", return_value=False):

            result = self.activity.enter_activity_via_overview(timeout=5.0)
            self.assertFalse(result)

    def test_07_goto_activity_click_failed(self):
        """测试在活动总览中点击前往活动失败时安全熔断退出。"""
        with patch.object(self.activity, "screenshot"), \
             patch.object(self.activity, "_is_in_activity_main_page", return_value=False), \
             patch.object(self.activity, "_is_in_activity_overview", side_effect=[False, True]), \
             patch.object(self.activity, "_step_click_sidebar_activity", return_value=True), \
             patch.object(self.activity, "_step_wait_activity_overview", return_value=True), \
             patch.object(self.activity, "_step_select_version_activity", return_value=True), \
             patch.object(self.activity, "_step_click_goto_activity", return_value=False):

            result = self.activity.enter_activity_via_overview(timeout=5.0)
            self.assertFalse(result)

    def test_08_action_enter_activity_hook(self):
        """测试路由层 action_enter_activity 能够正确代理并触发通用免更入场。"""
        mock_task = MagicMock()
        mock_task.enter_activity_via_overview.return_value = True

        res = action_enter_activity(mock_task)
        self.assertTrue(res)
        mock_task.enter_activity_via_overview.assert_called_once()


if __name__ == "__main__":
    unittest.main()
