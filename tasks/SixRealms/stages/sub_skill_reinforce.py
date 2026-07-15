# This Python file uses the following encoding: utf-8
"""
战后 3 卡子技能强化 Stage

职责：
- 识别当前处于力量/技巧/魅力强化选择界面
- 优先选择力量/技巧 < 4 级，可刷新
- 其次选择 4~10 级之间的目标
- 最后兜底选择魅力强化或任意可用槽位
"""
from time import sleep

from module.atom.ocr import RuleOcr
from module.logger import logger
from tasks.SixRealms.stages.base_stage import Stage


class SubSkillReinforceStage(Stage):
    """战后 3 卡子技能强化选择。"""

    def __init__(self, task):
        super().__init__(task)
        self.refresh_count = 0
        self.power_level = 0
        self.skill_level = 0

    def recognize(self) -> bool:
        full_ocr = RuleOcr(roi=(0, 0, 1280, 720), area=(0, 0, 1280, 720), mode="Full", method="Default", keyword="", name="full_screen_ocr")
        ocr_texts = [res.ocr_text for res in full_ocr.detect_and_ocr(self.task.device.image, logDisplay=False)]
        return any(t in ocr_texts for t in ["力量强化", "技巧强化", "魅力强化"])

    def act(self) -> bool:
        task = self.task
        logger.info("[SubSkillReinforce] Inside sub-skill selection popup")

        full_ocr = RuleOcr(roi=(0, 0, 1280, 720), area=(0, 0, 1280, 720), mode="Full", method="Default", keyword="", name="full_screen_ocr")
        ocr_results = full_ocr.detect_and_ocr(task.device.image, logDisplay=False)
        ocr_texts = [res.ocr_text for res in ocr_results]

        slots = [
            {"name": None, "level": 0, "btn": (292, 518)},
            {"name": None, "level": 0, "btn": (647, 518)},
            {"name": None, "level": 0, "btn": (1002, 518)},
        ]

        for res in ocr_results:
            box = res.box
            cx = int((box[0, 0] + box[2, 0]) / 2)
            cy = int((box[0, 1] + box[2, 1]) / 2)
            slot_idx = None
            if 100 <= cx <= 420:
                slot_idx = 0
            elif 420 < cx <= 840:
                slot_idx = 1
            elif 840 <= cx <= 1180:
                slot_idx = 2

            if slot_idx is not None:
                text = res.ocr_text
                if "力量" in text:
                    slots[slot_idx]["name"] = "力量强化"
                elif "技巧" in text:
                    slots[slot_idx]["name"] = "技巧强化"
                elif "魅力" in text:
                    slots[slot_idx]["name"] = "魅力强化"
                if text == "选择" and 480 <= cy <= 560:
                    slots[slot_idx]["btn"] = (cx, cy)

        # 读取等级
        ocr_power_level = RuleOcr(roi=(250, 235, 19, 26), area=(250, 235, 19, 26), mode="Digit", method="Default", keyword="", name="level_power")
        ocr_skill_level = RuleOcr(roi=(608, 239, 16, 22), area=(608, 239, 16, 22), mode="Digit", method="Default", keyword="", name="level_skill")
        ocr_charm_level = RuleOcr(roi=(966, 238, 15, 21), area=(966, 238, 15, 21), mode="Digit", method="Default", keyword="", name="level_charm")

        slots[0]["level"] = self._parse_int(ocr_power_level.ocr(task.device.image))
        slots[1]["level"] = self._parse_int(ocr_skill_level.ocr(task.device.image))
        slots[2]["level"] = self._parse_int(ocr_charm_level.ocr(task.device.image))

        for slot in slots:
            if slot["name"] == "力量强化" and slot["level"] > 0:
                self.power_level = slot["level"]
            elif slot["name"] == "技巧强化" and slot["level"] > 0:
                self.skill_level = slot["level"]

        logger.info(f"[SubSkillReinforce] Slots: {slots}, power={self.power_level}, skill={self.skill_level}")

        power_under_4 = next((s for s in slots if s["name"] == "力量强化" and s["level"] < 4), None)
        skill_under_4 = next((s for s in slots if s["name"] == "技巧强化" and s["level"] < 4), None)
        power_between_4_and_10 = next((s for s in slots if s["name"] == "力量强化" and 4 <= s["level"] < 10), None)
        skill_between_4_and_10 = next((s for s in slots if s["name"] == "技巧强化" and 4 <= s["level"] < 10), None)

        if power_under_4:
            return self._click_slot(power_under_4, "Power")
        if skill_under_4:
            return self._click_slot(skill_under_4, "Skill")

        # 需要刷新
        need_refresh = (
            (self.power_level < 4 and not any(s["name"] == "力量强化" for s in slots)) or
            (self.skill_level < 4 and not any(s["name"] == "技巧强化" for s in slots))
        )
        if need_refresh and self.refresh_count < 3:
            if self._try_refresh(ocr_results):
                self.refresh_count += 1
                sleep(2)
                return True

        if power_between_4_and_10:
            return self._click_slot(power_between_4_and_10, "Power_Save")
        if skill_between_4_and_10:
            return self._click_slot(skill_between_4_and_10, "Skill_Save")

        # 兜底选择
        fallback_slot = None
        for s in slots:
            if s["name"] == "魅力强化" and s["level"] < 10:
                fallback_slot = s
                break
        if not fallback_slot:
            for s in slots:
                if s["name"] is not None:
                    fallback_slot = s
                    break
        if not fallback_slot:
            fallback_slot = slots[2]

        logger.info(f"[SubSkillReinforce] Fallback select {fallback_slot['name']} at {fallback_slot['btn']}")
        return self._click_slot(fallback_slot, "Fallback")

    def _click_slot(self, slot, control_prefix: str) -> bool:
        task = self.task
        x, y = slot["btn"]
        logger.info(f"[SubSkillReinforce] Selecting {slot['name']} at ({x}, {y})")
        task.device.click(x=x, y=y, control_name=f"Select_{control_prefix}_Reinforce")
        self.refresh_count = 0
        sleep(2)
        return True

    def _try_refresh(self, ocr_results) -> bool:
        for res in ocr_results:
            if "剩" in res.ocr_text or "次" in res.ocr_text:
                box = res.box
                rx = int((box[0, 0] + box[2, 0]) / 2)
                ry = int((box[0, 1] + box[2, 1]) / 2) - 40
                logger.info(f"[SubSkillReinforce] Refreshing at ({rx}, {ry})")
                self.task.device.click(x=rx, y=ry, control_name="Refresh_Reinforce")
                return True
        logger.info("[SubSkillReinforce] No refresh text, fallback click at (960, 510)")
        self.task.device.click(x=960, y=510, control_name="Refresh_Reinforce_Fallback")
        return True

    @staticmethod
    def _parse_int(v) -> int:
        try:
            return int(v) if v is not None else 0
        except Exception:
            return 0
