# This Python file uses the following encoding: utf-8
"""
战后 4 卡技能选择 Stage

职责：
- 识别当前处于战后 4 卡技能选择界面
- 按优先级选择最右侧卡牌
"""
from module.logger import logger
from tasks.SixRealms.stages.base_stage import Stage


class SkillSelectStage(Stage):
    """战后 4 卡技能选择：优先最右。"""

    def recognize(self) -> bool:
        task = self.task
        return (
            task.appear(task.I_SELECT_0) or
            task.appear(task.I_SELECT_1) or
            task.appear(task.I_SELECT_2) or
            task.appear(task.I_SELECT_3)
        )

    def act(self) -> bool:
        logger.info("[SkillSelect] Found skill selection cards, selecting rightmost")
        task = self.task
        if task.appear_then_click(task.I_SELECT_3, interval=2):
            return True
        if task.appear_then_click(task.I_SELECT_2, interval=2):
            return True
        if task.appear_then_click(task.I_SELECT_1, interval=2):
            return True
        if task.appear_then_click(task.I_SELECT_0, interval=2):
            return True
        return False
