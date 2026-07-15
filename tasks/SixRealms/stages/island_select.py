# This Python file uses the following encoding: utf-8
"""
浮空岛选择 Stage

职责：
- 识别当前处于孔雀国浮空岛选择界面
- 按优先级选择岛屿：鏖战 -> 混沌 -> 神秘 -> 宁息
- 返回 True 表示已执行选择点击
"""
from time import sleep

from module.logger import logger
from tasks.SixRealms.stages.base_stage import Stage


class IslandSelectStage(Stage):
    """浮空岛选择界面。"""

    # 岛屿名称 OCR 优先级
    ISLAND_PRIORITY = {"鏖战": 1, "混沌": 2, "神秘": 3, "宁息": 4}

    def recognize(self) -> bool:
        task = self.task
        island_name = task.O_ISLAND_NAME.ocr(task.device.image)
        if island_name != "孔雀国" and "国" not in island_name:
            return False
        # 排除孔雀国大厅：大厅右下角有"开启"按钮，浮空岛选择没有
        if task.appear(task.I_MSTART):
            return False
        from module.atom.ocr import RuleOcr
        start_ocr = RuleOcr(
            roi=(1000, 550, 280, 170),
            area=(1000, 550, 280, 170),
            mode="Full", method="Default", keyword="",
            name="island_select_start_check"
        )
        texts = [res.ocr_text for res in start_ocr.detect_and_ocr(task.device.image, logDisplay=False)]
        if any("开启" in t for t in texts):
            return False
        return True

    def act(self) -> bool:
        task = self.task
        logger.hr('Island Selection', 1)
        task.screenshot()

        # 使用全局 OCR 地图识别岛屿名称
        results = task.O_OCR_MAP.detect_and_ocr(task.device.image)
        candidates = []
        for res in results:
            text = res.ocr_text
            box = res.box
            x = box[0, 0] + task.O_OCR_MAP.roi[0]
            y = box[0, 1] + task.O_OCR_MAP.roi[1]
            w = box[1, 0] - box[0, 0]
            h = box[2, 1] - box[0, 1]
            cx = int(x + w / 2)
            cy = int(y + h / 2)

            island_type = None
            if "战" in text or "鏖" in text or "度" in text or "廉" in text:
                island_type = "鏖战"
            elif "混" in text or "沌" in text:
                island_type = "混沌"
            elif "神" in text or "秘" in text or "包" in text:
                island_type = "神秘"
            elif "宁" in text or "息" in text:
                island_type = "宁息"

            if island_type:
                candidates.append({
                    "type": island_type,
                    "center": (cx, cy),
                    "text": text,
                    "score": res.score
                })
                logger.info(f"[IslandSelect] Candidate: {island_type} ('{text}') at {(cx, cy)}")

        if candidates:
            candidates.sort(key=lambda x: self.ISLAND_PRIORITY.get(x["type"], 99))
            best = candidates[0]
            logger.info(f"[IslandSelect] Selecting best island: {best['type']} at {best['center']}")
            task.device.click(x=best["center"][0], y=best["center"][1], control_name=f"Island_{best['type']}")
            self._wait_transition()
            return True

        # 兜底：三点轮询点击
        if not hasattr(self, "_fallback_island_index"):
            self._fallback_island_index = 0
        fallback_points = [
            (300, 530, "Left_Island_Fallback"),
            (720, 630, "Right_Island_Fallback"),
            (640, 480, "Center_Island_Fallback"),
        ]
        fx, fy, name = fallback_points[self._fallback_island_index % 3]
        self._fallback_island_index += 1
        logger.info(f"[IslandSelect] No priority island detected, fallback click at ({fx}, {fy})")
        task.device.click(x=fx, y=fy, control_name=name)
        sleep(0.5)
        return True

    def _wait_transition(self):
        """选择岛屿后等待转场完成。"""
        logger.info("[IslandSelect] Waiting for island selection transition...")
        task = self.task
        for _ in range(25):
            sleep(0.2)
            task.screenshot()
            new_name = task.O_ISLAND_NAME.ocr(task.device.image)
            if "之屿" in new_name:
                logger.info(f"[IslandSelect] Entered island: {new_name}")
                break
            if (
                task.appear(task.I_PREPARE_BATTLE) or
                task.appear(task.I_M_STORE) or
                task.appear(task.I_SELECT_0) or
                task.appear(task.I_SELECT_1) or
                task.appear(task.I_SELECT_2) or
                task.appear(task.I_SELECT_3)
            ):
                logger.info("[IslandSelect] Transition to battle/store/card screen completed")
                break
            if "国" not in new_name and new_name != "孔雀国":
                logger.info("[IslandSelect] Left selection screen")
                sleep(1.0)
                break
