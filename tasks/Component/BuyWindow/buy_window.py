# This Python file uses the following encoding: utf-8
from __future__ import annotations

import time
from typing import Optional

from module.logger import logger
from tasks.base_task import BaseTask
from tasks.Component.BaseActivity.exceptions import TicketsNotEnough
from tasks.Component.BuyWindow.assets import BuyWindowAssets


class BuyWindow(BaseTask, BuyWindowAssets):
    """活动门票购买弹窗识别与处理通用功能组件。

    设计职责：
    1. 特征识别：
       - 精确匹配购买弹窗底部的固定货币单位图标：魂玉（紫金）与勾玉（红白）；
       - 克服弹窗内容、文案不固定的问题，实现跨活动无感通用适配。
    2. 安全关闭：
       - 点击弹窗外侧半透明遮罩安全区域，关闭购买弹窗，杜绝误购风险与界面遮挡。
    3. 模式直切：
       - 识别到购买弹窗即判定为门票耗尽，立即关闭弹窗并抛出 TicketsNotEnough，
         彻底阻断多次挑战点击重试，实现 0 重试秒切下一个模式。
    """

    def is_ticket_buy_window(self, threshold: Optional[float] = None) -> bool:
        """检测当前界面是否处于活动门票购买弹窗。

        Args:
            threshold: 自定义匹配阈值，默认为资产预设值 (0.8)

        Returns:
            bool: True 表示检测到购买弹窗，False 表示未检测到
        """
        # 1. 优先匹配底部左侧魂玉购买图标或右侧勾玉购买图标
        if threshold is not None:
            if self.appear(self.I_TICKET_BUY_RMB, threshold=threshold) or \
               self.appear(self.I_TICKET_BUY_JADE, threshold=threshold):
                return True
        else:
            if self.appear(self.I_TICKET_BUY_RMB) or self.appear(self.I_TICKET_BUY_JADE):
                return True

        return False

    def close_ticket_buy_window(self, max_retries: int = 5, interval: float = 0.8) -> bool:
        """安全关闭购买弹窗，确保不发生误触购买且界面恢复干净。

        Args:
            max_retries: 最大尝试关闭次数
            interval: 每次点击后的等待间隔时间（秒）

        Returns:
            bool: True 表示已确认弹窗成功关闭，False 表示仍未关闭
        """
        for retry in range(1, max_retries + 1):
            if not self.is_ticket_buy_window():
                logger.info("购买弹窗已成功关闭")
                return True

            logger.info(f"正在尝试关闭购买弹窗 (第 {retry}/{max_retries} 次)...")
            self.click(self.C_TICKET_BUY_CLOSE_SAFE)
            time.sleep(interval)
            self.screenshot()

        # 最终确认
        if not self.is_ticket_buy_window():
            logger.info("购买弹窗已成功关闭")
            return True

        logger.warning(f"尝试关闭购买弹窗达到上限 [{max_retries}] 次，弹窗可能仍存在")
        return False

    def handle_ticket_buy_window(self, climb_type: str = '') -> None:
        """检测到门票不足购买弹窗时的主动熔断处理：

        1. 打印明确告警日志；
        2. 安全关闭购买弹窗；
        3. 立即抛出 TicketsNotEnough，直接切换下一模式，绝不重试。

        Args:
            climb_type: 当前爬塔模式标识（如 'pass'、'ap'）
        """
        prefix = f"[{climb_type}] " if climb_type else ""
        logger.warning(f"{prefix}检测到活动门票购买弹窗（门票已不足），判定门票已耗尽，立即关闭弹窗并切换模式！")
        self.close_ticket_buy_window()
        raise TicketsNotEnough
