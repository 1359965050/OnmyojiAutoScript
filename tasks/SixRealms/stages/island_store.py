# This Python file uses the following encoding: utf-8
"""
宁息之屿（商店）Stage

职责：
- 识别当前处于宁息之屿商店界面
- 直接点击离开按钮退出商店
"""
from time import sleep

from module.logger import logger
from tasks.SixRealms.stages.base_stage import Stage


class IslandStoreStage(Stage):
    """宁息之屿商店：直接离开，不购买。"""

    def recognize(self) -> bool:
        island_name = self.task.O_ISLAND_NAME.ocr(self.task.device.image)
        return "之屿" in island_name and ("宁" in island_name or "息" in island_name)

    def act(self) -> bool:
        task = self.task
        logger.info("[IslandStore] Ningxi store detected, leaving")

        # 离开确认弹窗
        from module.atom.ocr import RuleOcr
        full_ocr = RuleOcr(roi=(0, 0, 1280, 720), area=(0, 0, 1280, 720), mode="Full", method="Default", keyword="", name="full_screen_ocr")
        ocr_texts = [res.ocr_text for res in full_ocr.detect_and_ocr(task.device.image, logDisplay=False)]
        if any("离开" in t for t in ocr_texts) and any("确定" in t for t in ocr_texts):
            task.device.click(x=761, y=437, control_name="Leave_Confirm")
            sleep(1.5)
            return True

        # 直接点击右下角离开按钮
        task.device.click(x=1225, y=640, control_name="Click_Ningxi_Leave")
        sleep(1.5)
        return True
