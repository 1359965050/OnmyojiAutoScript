# This Python file uses the following encoding: utf-8
"""
通用奖励弹窗 Stage

职责：
- 识别"获得奖励"、"点击空白处关闭"等通用弹窗
- 点击空白处关闭
"""
from time import sleep

from module.atom.ocr import RuleOcr
from module.logger import logger
from tasks.SixRealms.stages.base_stage import Stage


class RewardPopupStage(Stage):
    """通用奖励/点击空白处关闭弹窗。"""

    def __init__(self, task):
        super().__init__(task)
        self.ocr_reward = RuleOcr(
            roi=(450, 100, 380, 100), area=(450, 100, 380, 100),
            mode="Single", method="Default", keyword="", name="ocr_reward", fallback_detect=False
        )
        self.ocr_blank = RuleOcr(
            roi=(450, 640, 380, 60), area=(450, 640, 380, 60),
            mode="Single", method="Default", keyword="", name="ocr_blank", fallback_detect=False
        )

    def recognize(self) -> bool:
        res_reward = self.ocr_reward.ocr(self.task.device.image)
        res_blank = self.ocr_blank.ocr(self.task.device.image)
        reward_str = "".join(res_reward) if isinstance(res_reward, list) else str(res_reward)
        blank_str = "".join(res_blank) if isinstance(res_blank, list) else str(res_blank)
        return (
            "获得" in reward_str or "奖励" in reward_str or
            "点击" in blank_str or "空白" in blank_str
        )

    def act(self) -> bool:
        logger.info("[RewardPopup] Found reward/blank popup, clicking blank area")
        self.task.device.click(x=930, y=670, control_name="Click_Blank_Close")
        sleep(1.5)
        return True
