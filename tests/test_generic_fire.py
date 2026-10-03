# This Python file uses the following encoding: utf-8
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.BaseActivity.exceptions import TicketsNotEnough
from tasks.Component.BuyWindow.buy_window import BuyWindow


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


class TestGenericFire(unittest.TestCase):
    """通用自适应挑战按钮识别单元测试。"""

    def setUp(self):
        self.activity = DummyActivity()

    def test_default_exit_matcher(self):
        """测试 BaseActivity 默认以 O_GENERIC_FIRE 作为战斗回房判定。"""
        exit_matcher = self.activity._exit_matcher()
        self.assertEqual(exit_matcher, self.activity.O_GENERIC_FIRE)
        self.assertEqual(self.activity.O_GENERIC_FIRE.keyword, "挑战")
        # 验证用户指定的 ROI (1073, 515, 199, 196)
        self.assertEqual(self.activity.O_GENERIC_FIRE.roi, [1073, 515, 199, 196])

    def test_find_fire_button_explicit_rule(self):
        """测试显式传入专用 fire_ocr 时优先命中。"""
        mock_custom_ocr = MagicMock(spec=RuleOcr)
        mock_custom_ocr.name = "custom_fire"
        mock_custom_ocr.coord.return_value = (1150, 620)

        with patch.object(self.activity, 'ocr_appear', return_value=True):
            coord = self.activity.find_fire_button(fire_ocr=mock_custom_ocr)
            self.assertEqual(coord, (1150, 620))

    def test_find_fire_button_generic_challenge(self):
        """测试未传入 fire_ocr 时自动使用 O_GENERIC_FIRE。"""
        with patch.object(self.activity, 'ocr_appear', side_effect=lambda rule: rule == self.activity.O_GENERIC_FIRE), \
             patch.object(self.activity.O_GENERIC_FIRE, 'coord', return_value=(1160, 610)):
            coord = self.activity.find_fire_button(fire_ocr=None)
            self.assertEqual(coord, (1160, 610))

    def test_find_fire_button_generic_start_fallback(self):
        """测试当'挑战'未命中时，自动回退到'开始'或'出击'。"""
        # 模拟 O_GENERIC_FIRE ("挑战") 未命中，但 O_GENERIC_FIRE_START ("开始") 命中
        def mock_appear(rule):
            return rule == self.activity.O_GENERIC_FIRE_START

        with patch.object(self.activity, 'ocr_appear', side_effect=mock_appear), \
             patch.object(self.activity.O_GENERIC_FIRE_START, 'coord', return_value=(1170, 615)):
            coord = self.activity.find_fire_button(fire_ocr=None)
            self.assertEqual(coord, (1170, 615))

    def test_click_fire_button_execution(self):
        """测试 click_fire_button 在无专用 fire_ocr 时成功点击通用规则。"""
        with patch.object(self.activity, 'ocr_appear_click', side_effect=lambda rule, **kw: rule == self.activity.O_GENERIC_FIRE):
            clicked = self.activity.click_fire_button(fire_ocr=None)
            self.assertTrue(clicked)

    def test_enter_battle_generic_without_any_images(self):
        """核心验证：enter_battle_generic 不传入任何图片或 OCR 参数时能正常工作进入战斗。"""
        in_battle_states = [False, True]  # 第一次不在战斗，进入过渡后在战斗中

        def mock_in_battle(*args, **kwargs):
            return in_battle_states.pop(0) if in_battle_states else True

        with patch.object(self.activity, 'is_in_battle', side_effect=mock_in_battle), \
             patch.object(self.activity, 'is_ticket_buy_window', return_value=False), \
             patch.object(self.activity, 'click_fire_button', return_value=True), \
             patch.object(self.activity, 'appear_then_click', return_value=False), \
             patch.object(self.activity, 'appear', return_value=False), \
             patch('time.sleep', return_value=None):

            result = self.activity.enter_battle_generic()
            self.assertTrue(result)

    def test_enter_battle_generic_zero_retry_on_buy_window(self):
        """核心验证：未传入参数时若弹出购买弹窗，依然 0 重试立即中断并抛出 TicketsNotEnough。"""
        with patch.object(self.activity, 'is_in_battle', return_value=False), \
             patch.object(self.activity, 'click_fire_button', return_value=True), \
             patch.object(self.activity, 'appear_then_click', return_value=False), \
             patch.object(self.activity, 'appear', return_value=False), \
             patch.object(self.activity, 'close_ticket_buy_window') as mock_close, \
             patch('time.sleep', return_value=None):

            buy_window_queries = []
            def mock_is_buy_window(*args, **kwargs):
                buy_window_queries.append(1)
                return len(buy_window_queries) > 1

            with patch.object(self.activity, 'is_ticket_buy_window', side_effect=mock_is_buy_window):
                with self.assertRaises(TicketsNotEnough):
                    self.activity.enter_battle_generic(max_clicks=5)

            mock_close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
