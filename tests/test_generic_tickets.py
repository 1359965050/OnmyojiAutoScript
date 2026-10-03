# This Python file uses the following encoding: utf-8
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from module.atom.ocr import RuleOcr
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.UsedTicketsCount.used_tickets_count import UsedTicketsCount


class MockBoxedResult:
    """模拟 OCR 文本检测结果对象。"""
    def __init__(self, x: float, y: float, text: str, score: float = 0.95):
        self.box = np.array([[x, y], [x + 50, y], [x + 50, y + 20], [x, y + 20]])
        self.ocr_text = text
        self.score = score


class DummyActivity(BaseActivity):
    """测试用 Activity 哑对象，隔离实际设备依赖。"""

    def __init__(self):
        self.device = MagicMock()
        self._current_climb_type = 'pass'
        self._switch_souled_map = {}
        self.config = MagicMock()
        self.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.interval_timer = {}
        self._app_used_count = {}

    def screenshot(self):
        return self.image


class TestGenericTickets(unittest.TestCase):
    """顶栏门票全域自适应识别与多资源解析单元测试。"""

    def setUp(self):
        self.activity = DummyActivity()

    def test_generic_tickets_bar_asset_defined(self):
        """测试 BaseActivityAssets 正确生成了 O_GENERIC_TICKETS_BAR，且 ROI 符合用户指定的 (481, 6, 600, 55)。"""
        rule = self.activity.O_GENERIC_TICKETS_BAR
        self.assertIsNotNone(rule)
        self.assertEqual(rule.roi, [481, 6, 600, 55])
        self.assertEqual(rule.name, "GENERIC_TICKETS_BAR")

    def test_parse_top_bar_screenshot_scenario(self):
        """核心验证：测试用户真实截图场景下的多资源水平排序与分配。

        截图数据：
        - 黑色常规门票: 50 +
        - 金色五倍/Boss券: 0 +
        - 寿司体力: 3.5万 +
        """
        boxed_results = [
            MockBoxedResult(635, 20, "50"),
            MockBoxedResult(675, 20, "+"),
            MockBoxedResult(795, 20, "0"),
            MockBoxedResult(825, 20, "+"),
            MockBoxedResult(915, 20, "3.5万"),
            MockBoxedResult(975, 20, "+"),
        ]

        resources = UsedTicketsCount.parse_top_bar_resources(boxed_results)

        # 验证门票 (pass) 解析为 50
        self.assertEqual(resources.get('pass'), 50)
        # 验证五倍/Boss券解析为 0
        self.assertEqual(resources.get('boss'), 0)
        self.assertEqual(resources.get('ap100'), 0)
        self.assertEqual(resources.get('five'), 0)
        # 验证体力解析为 35000
        self.assertEqual(resources.get('ap'), 35000)

    def test_parse_top_bar_fraction_scenario(self):
        """测试其他活动下的分数型门票格式 (如 20/200)。"""
        boxed_results = [
            MockBoxedResult(550, 20, " 20 / 200 "),
        ]

        resources = UsedTicketsCount.parse_top_bar_resources(boxed_results)

        self.assertEqual(resources.get('pass'), 180)
        self.assertEqual(resources.get('cur_used'), 20)
        self.assertEqual(resources.get('total'), 200)

    def test_parse_top_bar_single_number_scenario(self):
        """测试单一纯数字门票场景 (如 100)。"""
        boxed_results = [
            MockBoxedResult(600, 20, "100"),
        ]

        resources = UsedTicketsCount.parse_top_bar_resources(boxed_results)
        self.assertEqual(resources.get('pass'), 100)

    def test_check_game_tickets_available_with_generic_bar_positive(self):
        """测试 check_game_tickets_available 在未传 ocr_rule 时使用通用顶栏规则且余票充足。"""
        boxed_results = [
            MockBoxedResult(635, 20, "50"),
            MockBoxedResult(795, 20, "0"),
        ]

        with patch.object(self.activity.O_GENERIC_TICKETS_BAR, 'detect_and_ocr', return_value=boxed_results):
            # 常规门票 pass 拥有 50 张，应返回 True
            available = self.activity.check_game_tickets_available('pass', ocr_rule=None)
            self.assertTrue(available)
            self.assertEqual(self.activity._game_remain_map.get('pass'), 50)

    def test_check_game_tickets_available_with_generic_bar_exhausted(self):
        """测试 check_game_tickets_available 在未传 ocr_rule 时检测到余票为 0 返回 False。"""
        boxed_results = [
            MockBoxedResult(635, 20, "0"),  # 常规门票已为 0
        ]

        with patch.object(self.activity.O_GENERIC_TICKETS_BAR, 'detect_and_ocr', return_value=boxed_results):
            available = self.activity.check_game_tickets_available('pass', ocr_rule=None)
            self.assertFalse(available)
            self.assertEqual(self.activity._game_remain_map.get('pass'), 0)

    def test_check_game_tickets_available_boss_zero_in_screenshot(self):
        """测试在截图场景中执行 boss 模式时，检测到五倍券为 0 判定无票。"""
        boxed_results = [
            MockBoxedResult(635, 20, "50"),  # pass: 50
            MockBoxedResult(795, 20, "0"),   # boss: 0
        ]

        with patch.object(self.activity.O_GENERIC_TICKETS_BAR, 'detect_and_ocr', return_value=boxed_results):
            # pass 模式为 50，有票
            self.assertTrue(self.activity.check_game_tickets_available('pass', ocr_rule=None))
            # boss 模式为 0，无票
            self.assertFalse(self.activity.check_game_tickets_available('boss', ocr_rule=None))

    def test_check_game_tickets_available_safe_fallback(self):
        """测试若顶栏未识别出任何数字 (-1)，容错放行 (返回 True)，由 BuyWindow 接管。"""
        with patch.object(self.activity.O_GENERIC_TICKETS_BAR, 'detect_and_ocr', return_value=[]):
            available = self.activity.check_game_tickets_available('pass', ocr_rule=None)
            self.assertTrue(available)


if __name__ == '__main__':
    unittest.main()
