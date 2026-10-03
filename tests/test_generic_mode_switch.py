# This Python file uses the following encoding: utf-8
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

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

    def screenshot(self):
        return self.image

    def appear(self, *args, **kwargs):
        return True

    def ocr_appear(self, *args, **kwargs):
        return True


class TestGenericModeSwitch(unittest.TestCase):
    """体力/门票爬塔模式自适应切换单元测试。"""

    def setUp(self):
        self.activity = DummyActivity()

    def test_generic_mode_switch_asset_defined(self):
        """测试 BaseActivityAssets 正确生成了 C_GENERIC_MODE_SWITCH。"""
        click_rule = self.activity.C_GENERIC_MODE_SWITCH
        self.assertIsNotNone(click_rule)
        self.assertEqual(click_rule.roi_front, (1220, 545, 38, 30))
        self.assertEqual(click_rule.name, "generic_mode_switch")

    def test_get_current_climb_mode_ap_highlight(self):
        """测试当左半边（寿司）亮度显著高于右半边时，自适应判定为 'ap' 模式。"""
        # 创建全屏图并在 (845, 555, 145, 45) 内模拟左亮右暗
        img = np.zeros((720, 1280, 3), dtype=np.uint8)
        x, y, w, h = 845, 555, 145, 45
        mid = w // 2
        # 左半边高亮 (220)
        img[y:y+h, x:x+mid] = 220
        # 右半边暗淡 (60)
        img[y:y+h, x+mid:x+w] = 60

        mode = self.activity.get_current_climb_mode(image=img)
        self.assertEqual(mode, 'ap')
        self.activity.device.image = img
        self.assertTrue(self.activity.is_climb_mode_ap())
        self.assertFalse(self.activity.is_climb_mode_pass())

    def test_get_current_climb_mode_pass_highlight(self):
        """测试当右半边（门票）亮度显著高于左半边时，自适应判定为 'pass' 模式。"""
        img = np.zeros((720, 1280, 3), dtype=np.uint8)
        x, y, w, h = 845, 555, 145, 45
        mid = w // 2
        # 左半边暗淡 (60)
        img[y:y+h, x:x+mid] = 60
        # 右半边高亮 (220)
        img[y:y+h, x+mid:x+w] = 220

        mode = self.activity.get_current_climb_mode(image=img)
        self.assertEqual(mode, 'pass')
        self.activity.device.image = img
        self.assertTrue(self.activity.is_climb_mode_pass())
        self.assertFalse(self.activity.is_climb_mode_ap())

    def test_toggle_climb_mode_clicks_generic_pill(self):
        """测试 toggle_climb_mode 在无专有图标时点击 C_GENERIC_MODE_SWITCH。"""
        with patch.object(self.activity, 'click') as mock_click, \
             patch('time.sleep', return_value=None):
            result = self.activity.toggle_climb_mode()
            self.assertTrue(result)
            mock_click.assert_called_once_with(self.activity.C_GENERIC_MODE_SWITCH, interval=1.5)

    def test_ensure_climb_mode_already_in_target(self):
        """测试当当前模式已是目标模式时，无需点击切换直接返回 True。"""
        with patch.object(self.activity, 'get_current_climb_mode', return_value='ap'), \
             patch.object(self.activity, 'toggle_climb_mode') as mock_toggle:
            success = self.activity.ensure_climb_mode('ap')
            self.assertTrue(success)
            mock_toggle.assert_not_called()

    def test_ensure_climb_mode_switches_to_target(self):
        """测试当当前模式为 pass 而目标为 ap 时，自动调用切换并成功转为 ap。"""
        # 第一次查询为 pass，切换后变为 ap
        mode_states = ['pass', 'ap']

        def mock_get_mode(*args, **kwargs):
            return mode_states.pop(0) if mode_states else 'ap'

        with patch.object(self.activity, 'get_current_climb_mode', side_effect=mock_get_mode), \
             patch.object(self.activity, 'toggle_climb_mode') as mock_toggle, \
             patch('time.sleep', return_value=None):

            success = self.activity.ensure_climb_mode('ap', max_retries=3)
            self.assertTrue(success)
            mock_toggle.assert_called_once()


if __name__ == '__main__':
    unittest.main()
