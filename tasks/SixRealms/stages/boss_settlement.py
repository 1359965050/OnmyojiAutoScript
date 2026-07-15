# This Python file uses the following encoding: utf-8
"""
最终 BOSS 战后结算 Stage

职责：
- 识别 BOSS 战后的双倍/经验/分享/椒图结算界面
- 点击对应选项或空白处关闭
"""
from time import sleep

from module.logger import logger
from tasks.SixRealms.stages.base_stage import Stage


class BossSettlementStage(Stage):
    """最终 BOSS 战后结算界面处理。"""

    def recognize(self) -> bool:
        task = self.task
        return (
            task.appear(task.I_BOSS_USE_DOUBLE) or
            task.appear(task.I_BOSS_GET_EXP) or
            task.appear(task.I_BOSS_SHARE) or
            task.appear(task.I_BOSS_SHUTU)
        )

    def act(self) -> bool:
        task = self.task
        logger.info("[BossSettlement] Detected boss settlement screen")

        if task.appear_then_click(task.I_BOSS_USE_DOUBLE, interval=2):
            logger.info("[BossSettlement] Clicked boss double reward option")
            sleep(1.5)
            return True
        if task.appear_then_click(task.I_BOSS_GET_EXP, interval=2):
            logger.info("[BossSettlement] Clicked boss get exp")
            sleep(1.5)
            return True
        if task.appear(task.I_BOSS_SHARE):
            logger.info("[BossSettlement] Clicking blank area to dismiss share screen")
            task.device.click(x=100, y=100, control_name="Click_Share_Blank")
            sleep(1.5)
            return True
        if task.appear(task.I_BOSS_SHUTU):
            logger.info("[BossSettlement] Clicking blank area to dismiss shutu screen")
            task.device.click(x=640, y=360, control_name="Click_Shutu_Blank")
            sleep(1.5)
            return True
        return False
