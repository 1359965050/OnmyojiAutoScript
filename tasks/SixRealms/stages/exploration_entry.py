# This Python file uses the following encoding: utf-8
"""
探索页 → 六道之门总页 入口模块

职责：
- 在探索页识别六道之门入口并点击
- 与 page_six_gates 的页面识别逻辑彻底解耦
- 仅负责"进入"这一单一动作，不处理进入后的任何界面

识别策略（按优先级）：
1. 模板匹配识别入口图标
2. OCR 检测"六道之门"文字位置
3. 固定 ROI 兜底点击
"""
from time import sleep

from module.atom.ocr import RuleOcr
from module.logger import logger
from tasks.GameUi.assets import GameUiAssets as G


class ExplorationEntryStage:
    """从探索页进入六道之门总页的独立入口模块。"""

    # 兜底固定点击坐标（探索页底部功能栏"六道之门"图标中心）
    FALLBACK_CLICK_X = 930
    FALLBACK_CLICK_Y = 665

    def __init__(self, task):
        self.task = task

    def _match_score(self) -> float:
        """模板匹配分数。"""
        return G.I_EXPLORATION_GOTO_SIX_GATES.match(self.task.device.image)

    def is_entry_visible_by_image(self) -> bool:
        """当前截图中是否存在六道之门入口图标。"""
        score = self._match_score()
        logger.info(f"[ExplorationEntry] Image match score: {score:.3f} (threshold: {G.I_EXPLORATION_GOTO_SIX_GATES.threshold})")
        return self.task.appear(G.I_EXPLORATION_GOTO_SIX_GATES)

    def _find_entry_by_ocr(self):
        """
        通过分段 OCR 查找"六道之门"文字位置。
        把底部功能栏切成多个 slot，找到包含"六道"的 slot 后返回其中心坐标。
        :return: (x, y) 文字中心坐标，未找到返回 None
        """
        roi_y, roi_h = 580, 140
        slot_width = 128
        for i in range(10):
            x0 = i * slot_width
            x1 = min(x0 + slot_width, 1280)
            slot_ocr = RuleOcr(
                roi=(x0, roi_y, x1 - x0, roi_h),
                area=(x0, roi_y, x1 - x0, roi_h),
                mode="Full", method="Default", keyword="", name=f"exploration_entry_ocr_slot_{i}"
            )
            results = slot_ocr.detect_and_ocr(self.task.device.image, logDisplay=False)
            for res in results:
                text = res.ocr_text
                if "六道" in text or "道之门" in text:
                    box = res.box
                    cx = x0 + int((box[0, 0] + box[2, 0]) / 2)
                    cy = roi_y + int((box[0, 1] + box[2, 1]) / 2)
                    logger.info(f"[ExplorationEntry] OCR found entry text '{text}' in slot {i} at ({cx}, {cy})")
                    return cx, cy
        return None

    def _click_entry(self, x: int, y: int, control_name: str):
        """点击入口并等待转场。"""
        logger.info(f"[ExplorationEntry] Clicking entry at ({x}, {y}) [{control_name}]")
        self.task.device.click(x=x, y=y, control_name=control_name)

    def enter(self, max_attempts: int = 3, post_click_wait: float = 2.5) -> bool:
        """
        尝试从探索页点击进入六道之门。

        :param max_attempts: 最大识别点击尝试次数
        :param post_click_wait: 点击后等待转场动画的时间（秒）
        :return: 是否成功执行入口点击
        """
        logger.info("[ExplorationEntry] Start entering Six Gates from exploration")
        for attempt in range(1, max_attempts + 1):
            self.task.screenshot()

            # 1. 图片模板匹配
            if self.is_entry_visible_by_image():
                if self.task.appear_then_click(G.I_EXPLORATION_GOTO_SIX_GATES, interval=2):
                    logger.info(f"[ExplorationEntry] Clicked Six Gates entry by image (attempt {attempt})")
                    self.task.device.sleep(post_click_wait)
                    return True

            # 2. OCR 定位文字
            ocr_pos = self._find_entry_by_ocr()
            if ocr_pos:
                cx, cy = ocr_pos
                # 点击文字上方约 35 像素，对准图标中心
                click_x, click_y = cx, max(cy - 35, 620)
                self._click_entry(click_x, click_y, "Six_Gates_Entry_OCR")
                self.task.device.sleep(post_click_wait)
                return True

            logger.warning(f"[ExplorationEntry] Entry not recognized, attempt {attempt}/{max_attempts}")
            sleep(1)

        # 3. 固定 ROI 兜底点击
        logger.warning(f"[ExplorationEntry] Image & OCR both failed, using fallback click at ({self.FALLBACK_CLICK_X}, {self.FALLBACK_CLICK_Y})")
        self._click_entry(self.FALLBACK_CLICK_X, self.FALLBACK_CLICK_Y, "Six_Gates_Entry_Fallback")
        self.task.device.sleep(post_click_wait)
        return True
