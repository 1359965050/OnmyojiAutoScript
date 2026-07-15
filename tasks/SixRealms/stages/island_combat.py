# This Python file uses the following encoding: utf-8
"""
战斗岛屿 Stage（鏖战 / 混沌 / 绽放）

职责：
- 识别当前处于鏖战之屿、混沌之屿或绽放之屿等战斗/事件岛屿
- 处理选怪、精英怪、紧那罗选择、幸运宝匣、技能学习等分支
- 最终点击挑战按钮并调用通用战斗
"""
from time import sleep

from module.atom.image import RuleImage
from module.logger import logger
from module.ocr.models import get_ocr_model
from tasks.SixRealms.stages.base_stage import Stage


class IslandCombatStage(Stage):
    """鏖战/混沌/绽放等战斗岛屿内部处理。"""

    def recognize(self) -> bool:
        island_name = self.task.O_ISLAND_NAME.ocr(self.task.device.image)
        return (
            "之屿" in island_name and
            ("战" in island_name or "绽" in island_name or "放" in island_name or
             "混" in island_name or "沌" in island_name)
        )

    def act(self) -> bool:
        task = self.task
        logger.hr('Monster Selection & Battle', 1)

        from module.atom.ocr import RuleOcr
        full_ocr = RuleOcr(roi=(0, 0, 1280, 720), area=(0, 0, 1280, 720), mode="Full", method="Default", keyword="", name="full_screen_ocr")
        ocr_results = full_ocr.detect_and_ocr(task.device.image, logDisplay=False)
        ocr_texts = [res.ocr_text for res in ocr_results]

        # 0. 离开确认弹窗
        if any("离开" in t for t in ocr_texts) and any("确定" in t for t in ocr_texts):
            logger.info("[IslandCombat] Leave confirm popup, clicking confirm")
            task.device.click(x=761, y=437, control_name="Leave_Confirm")
            sleep(1.5)
            return True

        # 0.1 幸运宝匣未开启：直接离开
        if any("宝匣" in t or "宝画" in t or "幸运宝" in t for t in ocr_texts):
            leave_btn = None
            for res in ocr_results:
                if "离开" in res.ocr_text and res.box[0, 0] > 1100 and res.box[0, 1] > 600:
                    cx = int((res.box[0, 0] + res.box[2, 0]) / 2)
                    cy = int((res.box[0, 1] + res.box[2, 1]) / 2)
                    leave_btn = (cx, cy)
                    break
            if not leave_btn:
                leave_btn = (1180, 690)
            logger.info(f"[IslandCombat] Lucky chest detected, skipping and leaving at {leave_btn}")
            task.device.click(x=leave_btn[0], y=leave_btn[1], control_name="Skip_Chest_Leave")
            sleep(2)
            return True

        # 0.12 宝匣已开启只剩离开按钮
        leave_btn = None
        for res in ocr_results:
            if "离开" in res.ocr_text and res.box[0, 0] > 1100 and res.box[0, 1] > 600:
                cx = int((res.box[0, 0] + res.box[2, 0]) / 2)
                cy = int((res.box[0, 1] + res.box[2, 1]) / 2)
                leave_btn = (cx, cy)
                break
        if leave_btn and not any(t in ocr_texts for t in ["不知火", "铃彦姬", "绽放", "挑战", "战"]):
            logger.info(f"[IslandCombat] Chest opened, only leave button at {leave_btn}")
            task.device.click(x=leave_btn[0], y=leave_btn[1], control_name="Click_Leave_Button")
            sleep(2)
            return True

        # 0.13 混沌之屿精英分支
        island_name = task.O_ISLAND_NAME.ocr(task.device.image)
        if "混" in island_name or "沌" in island_name:
            if self._handle_chaos_elite(task):
                return True

        # 0.15 紧那罗技能学习界面
        rule_learn = RuleImage(
            roi_front=(1129, 588, 76, 94),
            roi_back=(1080, 550, 180, 150),
            method="Template matching",
            threshold=0.8,
            file="./tasks/SixRealms/gate1/gate1_learn.png"
        )
        is_skill_learn = rule_learn.match(task.device.image) or any(
            t in ocr_texts for t in ["绽放之舞", "绽放舜", "雀舞", "暴击伤害", "每造成"]
        )
        if is_skill_learn:
            logger.info("[IslandCombat] Jinnara skill learning page, clicking learn")
            task.device.click(x=1160, y=630, control_name="Click_Skill_Learn")
            sleep(1.5)
            task.run_general_battle(config=task._config.general_battle_config)
            return True

        # 0.2 绽放之屿选择紧那罗
        jinnara_slot = None
        for res in ocr_results:
            if "紧那罗" in res.ocr_text:
                box = res.box
                cx = int((box[0, 0] + box[2, 0]) / 2)
                cy = int((box[0, 1] + box[2, 1]) / 2)
                jinnara_slot = (cx, cy)
                break
        is_zhanfang = (
            jinnara_slot is not None or
            any(t in ocr_texts for t in ["不知火", "铃彦姬", "绽放"]) or
            "绽" in island_name or "放" in island_name
        )
        if is_zhanfang:
            if jinnara_slot:
                click_x = jinnara_slot[0] + 150
                click_y = jinnara_slot[1]
                logger.info(f"[IslandCombat] Selecting Jinnara at ({click_x}, {click_y})")
            else:
                click_x, click_y = 200, 360
                logger.info(f"[IslandCombat] Zhanfang fallback click at ({click_x}, {click_y})")
            task.device.click(x=click_x, y=click_y, control_name="Select_Jinnara")
            sleep(1.5)
            return True

        # 1. 尝试选择右边的怪物，直到 I_NPC_FIRE 出现
        for _ in range(3):
            task.screenshot()
            if task.appear(task.I_NPC_FIRE):
                logger.info("[IslandCombat] Challenge button visible")
                break

            results = task.O_OCR_MAP.detect_and_ocr(task.device.image)
            candidates = []
            for res in results:
                box = res.box
                x = box[0, 0] + task.O_OCR_MAP.roi[0]
                y = box[0, 1] + task.O_OCR_MAP.roi[1]
                w = box[1, 0] - box[0, 0]
                h = box[2, 1] - box[0, 1]
                if 200 <= x <= 1000 and 250 <= y <= 550:
                    candidates.append({
                        "text": res.ocr_text,
                        "cx": int(x + w / 2),
                        "cy": int(y + h / 2)
                    })

            groups = []
            for c in candidates:
                added = False
                for g in groups:
                    if abs(g["x_avg"] - c["cx"]) < 50:
                        g["items"].append(c)
                        g["x_avg"] = sum(item["cx"] for item in g["items"]) / len(g["items"])
                        if c["cy"] > g["click_y"]:
                            g["click_y"] = c["cy"]
                        added = True
                        break
                if not added:
                    groups.append({"x_avg": c["cx"], "click_y": c["cy"], "items": [c]})

            if groups:
                groups.sort(key=lambda g: g["x_avg"])
                target = groups[-1]
                cx, cy = int(target["x_avg"]), target["click_y"]
                logger.info(f"[IslandCombat] Selecting right monster at ({cx}, {cy})")
                task.device.click(x=cx, y=cy, control_name="Select_Right_Monster")
            else:
                logger.info("[IslandCombat] No monster via OCR, fallback right click")
                task.click(task.C_NPC_FIRE_RIGHT)
            sleep(1.5)

        if not task.appear(task.I_NPC_FIRE):
            logger.info("[IslandCombat] Right monster not found, trying center")
            task.click(task.C_NPC_FIRE_CENTER)
            sleep(1.5)

        if not task.appear(task.I_NPC_FIRE):
            logger.info("[IslandCombat] Center monster not found, trying left")
            task.click(task.C_NPC_FIRE_LEFT)
            sleep(1.5)

        if task.appear_then_click(task.I_NPC_FIRE, interval=1):
            logger.info("[IslandCombat] Entering general battle")
            task.run_general_battle(config=task._config.general_battle_config)
            return True

        logger.warning("[IslandCombat] Failed to select monster and start battle")
        return False

    def _handle_chaos_elite(self, task) -> bool:
        """处理混沌之屿精英怪分支，返回 True 表示已处理。"""
        model = get_ocr_model("ch")
        crop_elite = task.device.image[178:178 + 80, 595:595 + 80]
        res_elite = model.detect_and_ocr(crop_elite)
        elite_btn = None
        for r in res_elite:
            if r.score > 0.5 and ("精" in r.ocr_text or "英" in r.ocr_text):
                cx = 595 + int((r.box[0, 0] + r.box[2, 0]) / 2)
                cy = 178 + int((r.box[0, 1] + r.box[2, 1]) / 2)
                elite_btn = (cx, cy)
                break
        if not elite_btn:
            return False

        logger.info(f"[IslandCombat] Chaos elite badge at {elite_btn}")
        task.device.click(x=elite_btn[0], y=elite_btn[1], control_name="Click_Elite_Badge")
        sleep(1.5)

        for _ in range(5):
            task.screenshot()
            crop_chal = task.device.image[580:580 + 90, 1100:1100 + 150]
            res_chal = model.detect_and_ocr(crop_chal)
            challenge_btn = None
            for r in res_chal:
                if r.score > 0.5 and ("战" in r.ocr_text or "挑" in r.ocr_text):
                    cx = 1100 + int((r.box[0, 0] + r.box[2, 0]) / 2)
                    cy = 580 + int((r.box[0, 1] + r.box[2, 1]) / 2)
                    challenge_btn = (cx, cy)
                    break
            if challenge_btn:
                logger.info(f"[IslandCombat] Elite challenge button at {challenge_btn}")
                task.device.click(x=challenge_btn[0], y=challenge_btn[1], control_name="Click_Challenge")
                sleep(1.5)
                task.run_general_battle(config=task._config.general_battle_config)
                return True
            sleep(1)
        return False
