# This Python file uses the following encoding: utf-8
import unittest
from unittest.mock import MagicMock, patch

from tasks.Component.UsedTicketsCount.used_tickets_count import UsedTicketsCount


class TestUsedTicketsCount(unittest.TestCase):

    def setUp(self):
        # 隔离 BaseTask 中的皮肤和设备初始化
        self.patcher = patch('tasks.base_task.BaseTask.__init__', return_value=None)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_parse_fraction_tickets(self):
        """测试分数格式 (DigitCounter: 已用/总数) 的解析。"""
        # 标准分数
        cur, remain, total = UsedTicketsCount.parse_game_ticket_text("12/50")
        self.assertEqual(cur, 12)
        self.assertEqual(remain, 38)
        self.assertEqual(total, 50)

        # 刚开始 0 次已用
        cur, remain, total = UsedTicketsCount.parse_game_ticket_text("0/300")
        self.assertEqual(cur, 0)
        self.assertEqual(remain, 300)
        self.assertEqual(total, 300)

        # 门票打满
        cur, remain, total = UsedTicketsCount.parse_game_ticket_text("50/50")
        self.assertEqual(cur, 50)
        self.assertEqual(remain, 0)
        self.assertEqual(total, 50)

        # 带空格和全角斜杠
        cur, remain, total = UsedTicketsCount.parse_game_ticket_text(" 23 ／ 100 ")
        self.assertEqual(cur, 23)
        self.assertEqual(remain, 77)
        self.assertEqual(total, 100)

    def test_parse_digit_tickets(self):
        """测试纯数字格式 (Digit: 剩余票数) 的解析。"""
        cur, remain, total = UsedTicketsCount.parse_game_ticket_text("50")
        self.assertEqual(cur, 0)
        self.assertEqual(remain, 50)
        self.assertEqual(total, 50)

        cur, remain, total = UsedTicketsCount.parse_game_ticket_text("0")
        self.assertEqual(cur, 0)
        self.assertEqual(remain, 0)
        self.assertEqual(total, 0)

    def test_parse_invalid_text(self):
        """测试无效与异常文本的安全容错解析。"""
        cur, remain, total = UsedTicketsCount.parse_game_ticket_text("")
        self.assertEqual(remain, -1)

        cur, remain, total = UsedTicketsCount.parse_game_ticket_text("abc")
        self.assertEqual(remain, -1)

        cur, remain, total = UsedTicketsCount.parse_game_ticket_text(None)
        self.assertEqual(remain, -1)

    def test_app_used_count_isolated_from_manual(self):
        """测试用户需求的核心场景：应用使用计数仅记录本次应用运行的次数。

        用户需求：
        游戏界面显示门票总共使用了 23，但玩家手动使用了 5，应用运行使用了 18，
        则该已使用计数记录的必须是 18，而不是 23。
        """
        counter = UsedTicketsCount(None, None)

        # 初始状态，应用运行计数必须为 0
        self.assertEqual(counter.get_app_used_count('pass'), 0)

        # 模拟应用运行，执行了 18 次挑战
        for _ in range(18):
            counter.record_ticket_used('pass', count=1, target_limit=50)

        # 核心断言：应用使用计数必须严格为 18
        self.assertEqual(counter.get_app_used_count('pass'), 18)

        # 检查是否达到目标 50 次限额（18 < 50，尚未达到）
        self.assertFalse(counter.is_app_limit_reached('pass', target_limit=50))

        # 继续运行 32 次达到 50
        for _ in range(32):
            counter.record_ticket_used('pass', count=1, target_limit=50)

        self.assertEqual(counter.get_app_used_count('pass'), 50)
        # 达到目标限额 50
        self.assertTrue(counter.is_app_limit_reached('pass', target_limit=50))

    def test_reset_app_counter(self):
        """测试重置计数器。"""
        counter = UsedTicketsCount(None, None)

        counter.record_ticket_used('pass', count=10)
        counter.record_ticket_used('ap', count=20)
        self.assertEqual(counter.get_app_used_count('pass'), 10)
        self.assertEqual(counter.get_app_used_count('ap'), 20)

        # 重置单个
        counter.reset_app_counter('pass')
        self.assertEqual(counter.get_app_used_count('pass'), 0)
        self.assertEqual(counter.get_app_used_count('ap'), 20)

        # 重置全部
        counter.reset_app_counter()
        self.assertEqual(counter.get_app_used_count('ap'), 0)


if __name__ == '__main__':
    unittest.main()
