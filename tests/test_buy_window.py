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

    def screenshot(self):
        return self.image


class TestBuyWindow(unittest.TestCase):
    """BuyWindow 通用组件单元测试。"""

    def setUp(self):
        self.activity = DummyActivity()

    def test_is_ticket_buy_window_positive(self):
        """测试检测到魂玉或勾玉购买图标时正确识别为购买弹窗。"""
        # 1. 魂玉图标出现
        with patch.object(BuyWindow, 'appear', side_effect=lambda img, **kwargs: img == BuyWindow.I_TICKET_BUY_RMB):
            self.assertTrue(self.activity.is_ticket_buy_window())

        # 2. 勾玉图标出现
        with patch.object(BuyWindow, 'appear', side_effect=lambda img, **kwargs: img == BuyWindow.I_TICKET_BUY_JADE):
            self.assertTrue(self.activity.is_ticket_buy_window())

        # 3. 两者均未出现
        with patch.object(BuyWindow, 'appear', return_value=False):
            self.assertFalse(self.activity.is_ticket_buy_window())

    def test_close_ticket_buy_window(self):
        """测试安全关闭弹窗逻辑：点击外部安全区域直到弹窗消失。"""
        states = [True, True, False]  # 第一次在弹窗，点一次还在，点第二次关闭

        def mock_is_window(*args, **kwargs):
            return states.pop(0) if states else False

        with patch.object(BuyWindow, 'is_ticket_buy_window', side_effect=mock_is_window), \
             patch.object(BuyWindow, 'click') as mock_click, \
             patch('time.sleep', return_value=None):
            result = self.activity.close_ticket_buy_window(max_retries=5)
            self.assertTrue(result)
            self.assertGreaterEqual(mock_click.call_count, 1)

    def test_handle_ticket_buy_window(self):
        """测试检测到购买弹窗后调用 handle_ticket_buy_window 立即关闭并抛出 TicketsNotEnough。"""
        with patch.object(BuyWindow, 'close_ticket_buy_window') as mock_close:
            with self.assertRaises(TicketsNotEnough):
                self.activity.handle_ticket_buy_window('pass')
            mock_close.assert_called_once()

    def test_enter_battle_generic_zero_retry_on_buy_window(self):
        """核心验证：点击挑战后若弹出购买弹窗，立即中断退出，绝不重试 3 次！"""
        fire_ocr = MagicMock(spec=RuleOcr)
        confirm_img = MagicMock(spec=RuleImage)
        confirm_small = MagicMock(spec=RuleImage)

        # 模拟执行流程：
        # 1. 最初不在战斗中
        # 2. 点击挑战 fire_ocr 成功
        # 3. 进场过渡等待中检测到了购买弹窗 is_ticket_buy_window() 为 True
        ocr_click_counts = []

        def mock_ocr_appear_click(*args, **kwargs):
            ocr_click_counts.append(1)
            return True

        with patch.object(self.activity, 'is_in_battle', return_value=False), \
             patch.object(self.activity, 'ocr_appear_click', side_effect=mock_ocr_appear_click), \
             patch.object(self.activity, 'appear_then_click', return_value=False), \
             patch.object(self.activity, 'appear', return_value=False), \
             patch.object(self.activity, 'close_ticket_buy_window') as mock_close, \
             patch('time.sleep', return_value=None):

            # 设置初始进入循环前 is_ticket_buy_window 为 False，点击挑战后为 True
            buy_window_query_count = []
            def mock_is_buy_window(*args, **kwargs):
                buy_window_query_count.append(1)
                # 第一次进入循环时还未点击挑战，为 False；点击挑战进入过渡轮询后为 True
                return len(buy_window_query_count) > 1

            with patch.object(self.activity, 'is_ticket_buy_window', side_effect=mock_is_buy_window):
                with self.assertRaises(TicketsNotEnough):
                    self.activity.enter_battle_generic(
                        fire_ocr=fire_ocr,
                        confirm_image=confirm_img,
                        confirm_small_image=confirm_small,
                        max_clicks=5
                    )

            # 验证仅点击了 1 次挑战，绝没有重试 3 次！
            self.assertEqual(len(ocr_click_counts), 1, "挑战点击次数应该为 1 次，严禁在出现购买弹窗时重试 3 次！")
            # 验证弹窗安全关闭被调用
            mock_close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
