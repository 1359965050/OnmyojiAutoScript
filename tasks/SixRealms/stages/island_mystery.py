# This Python file uses the following encoding: utf-8
"""
神秘之屿 Stage

职责：
- 识别当前处于神秘之屿界面
- 点击返回按钮或出口退出
"""
from time import sleep

from module.logger import logger
from tasks.SixRealms.stages.base_stage import Stage


class IslandMysteryStage(Stage):
    """神秘之屿：直接退出。"""

    def recognize(self) -> bool:
        island_name = self.task.O_ISLAND_NAME.ocr(self.task.device.image)
        return "之屿" in island_name and ("神" in island_name or "秘" in island_name)

    def act(self) -> bool:
        task = self.task
        logger.info("[IslandMystery] Shenmi island detected, leaving")

        # 离开确认弹窗
        from module.atom.ocr import RuleOcr
        full_ocr = RuleOcr(roi=(0, 0, 1280, 720), area=(0, 0, 1280, 720), mode="Full", method="Default", keyword="", name="full_screen_ocr")
        ocr_texts = [res.ocr_text for res in full_ocr.detect_and_ocr(task.device.image, logDisplay=False)]
        if any("离开" in t for t in ocr_texts) and any("确定" in t for t in ocr_texts):
            task.device.click(x=761, y=437, control_name="Leave_Confirm")
            sleep(1.5)
            return True

        if task.appear_then_click(task.I_L103_EXIT, interval=2):
            return True

        # 兜底左上角返回
        task.device.click(x=30, y=39, control_name="Click_Back_Arrow")
        sleep(1.5)
        return True
