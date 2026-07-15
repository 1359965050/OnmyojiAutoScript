# This Python file uses the following encoding: utf-8
"""
通用确认/跳过弹窗 Stage

职责：
- 识别并点击六道之门中常见的确认、跳过按钮
- 作为兜底 Stage 放在调度器最后
"""
from module.logger import logger
from tasks.SixRealms.stages.base_stage import Stage


class CommonConfirmStage(Stage):
    """通用确认/跳过弹窗兜底处理。"""

    def recognize(self) -> bool:
        task = self.task
        return (
            task.appear(task.I_MSTART_CONFIRM) or
            task.appear(task.I_MSTART_CONFIRM2) or
            task.appear(task.I_MSKIP)
        )

    def act(self) -> bool:
        task = self.task
        logger.info("[CommonConfirm] Clicking common confirm/skip popup")
        if task.appear_then_click(task.I_MSTART_CONFIRM, interval=2):
            return True
        if task.appear_then_click(task.I_MSTART_CONFIRM2, interval=2):
            return True
        if task.appear_then_click(task.I_MSKIP, interval=2):
            return True
        return False
