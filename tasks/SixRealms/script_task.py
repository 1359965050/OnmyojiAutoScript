# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from cached_property import cached_property



from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_soul_zones, page_shikigami_records
from module.logger import logger
from module.exception import TaskEnd


from time import sleep
from datetime import time, datetime, timedelta

from tasks.Sougenbi.assets import SougenbiAssets
from tasks.Sougenbi.config import SougenbiConfig, SougenbiClass

from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_six_gates
from tasks.SixRealms.assets import SixRealmsAssets
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from module.logger import logger
from tasks.SixRealms.oas_ocr import StoneOcr


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, SixRealmsAssets):
    O_OCR_MAP = StoneOcr(roi=(144, 227, 989, 376), area=(144, 227, 989, 376), mode="Full", method="Default", keyword="", name="ocr_map")

    def is_peacock_lobby(self) -> bool:
        res = self.O_CHECK_PEACOCK_LOBBY.detect_and_ocr(self.device.image, logDisplay=False)
        texts = [r.ocr_text for r in res]
        # 支持 '孔雀国' 和 '恋色障道' (包括 OCR 识别可能的偏差)
        return any(any(k in t for k in ["孔雀国", "恋色障道", "孔雀", "恋色", "障道"]) for t in texts)

    @property
    def _config(self):
        return self.config.model.six_realms

    def run(self):
        self.reinforce_refresh_count = 0
        self.power_level = 0
        self.skill_level = 0
        if self._config.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(self._config.switch_soul_config.switch_group_team)
        if self._config.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(self._config.switch_soul_config.group_name, self._config.switch_soul_config.team_name)
        self.screenshot()
        # 检测是否已经在运行中或者卡牌/强化/奖励弹窗界面，防止误退
        from module.atom.ocr import RuleOcr
        ocr_reward = RuleOcr(roi=(450, 100, 380, 100), area=(450, 100, 380, 100), mode="Single", method="Default", keyword="", name="ocr_reward_init")
        ocr_blank = RuleOcr(roi=(450, 640, 380, 60), area=(450, 640, 380, 60), mode="Single", method="Default", keyword="", name="ocr_blank_init")
        res_reward = ocr_reward.ocr(self.device.image)
        res_blank = ocr_blank.ocr(self.device.image)
        reward_str = "".join(res_reward) if isinstance(res_reward, list) else str(res_reward)
        blank_str = "".join(res_blank) if isinstance(res_blank, list) else str(res_blank)
        
        if "探索" in reward_str or "阴阳寮" in blank_str:
            logger.info("识别当前页面：首页")
            
        is_in_reward_popup = "获得" in reward_str or "奖励" in reward_str or "点击" in blank_str or "空白" in blank_str

        is_in_run = False
        if not (self.appear(self.I_MAIN_GOTO_EXPLORATION) or self.appear(self.I_CHECK_EXPLORATION)):
            is_in_run = (
                self.appear(page_six_gates.check_button) or
                self.is_peacock_lobby() or
                self.appear(self.I_BACK_EXIT) or
                self.appear(self.I_PREPARE_BATTLE) or
                self.appear(self.I_PREPARE_HIGHLIGHT) or
                self.appear(self.I_M_STORE) or
                self.appear(self.I_SELECT_0) or self.appear(self.I_SELECT_1) or 
                self.appear(self.I_SELECT_2) or self.appear(self.I_SELECT_3) or
                "之屿" in self.O_ISLAND_NAME.ocr(self.device.image) or
                is_in_reward_popup
            )
        if not is_in_run:
            self.ui_get_current_page()
            self.ui_goto(page_six_gates)

        while 1:
            self.screenshot()

            # 如果回到了大厅或者探索，表示六道任务已结束
            if self.appear(self.I_CHECK_EXPLORATION) or self.appear(self.I_CHECK_MAIN) or self.appear(self.I_MAIN_GOTO_EXPLORATION):
                logger.info("Six Realms run completed or exited")
                break

            # If we are in the battle preparation screen or in a battle, run general battle
            if self.is_in_prepare(False) or self.is_in_real_battle(False):
                logger.info("Detected battle preparation or active battle, executing general battle...")
                self.run_general_battle(config=self._config.general_battle_config)
                continue

            # 最终首领战后结算弹窗与结算界面处理
            if self.appear_then_click(self.I_BOSS_USE_DOUBLE, interval=2):
                logger.info("Clicked boss double reward option")
                sleep(1.5)
                continue
            if self.appear_then_click(self.I_BOSS_GET_EXP, interval=2):
                logger.info("Clicked boss get exp")
                sleep(1.5)
                continue
            if self.appear(self.I_BOSS_SHARE):
                logger.info("Detected boss share screen, clicking blank area at (100, 100) to dismiss...")
                self.device.click(x=100, y=100, control_name="Click_Share_Blank")
                sleep(1.5)
                continue
            if self.appear(self.I_BOSS_SHUTU):
                logger.info("Detected final boss shutu/rating settlement screen, clicking to return...")
                self.device.click(x=640, y=360, control_name="Click_Shutu_Blank")
                sleep(1.5)
                continue

            # 检查是否在“获得奖励/点击空白处关闭”界面
            from module.atom.ocr import RuleOcr
            ocr_reward = RuleOcr(roi=(450, 100, 380, 100), area=(450, 100, 380, 100), mode="Single", method="Default", keyword="", name="ocr_reward", fallback_detect=False)
            ocr_blank = RuleOcr(roi=(450, 640, 380, 60), area=(450, 640, 380, 60), mode="Single", method="Default", keyword="", name="ocr_blank", fallback_detect=False)
            res_reward = ocr_reward.ocr(self.device.image)
            res_blank = ocr_blank.ocr(self.device.image)
            reward_str = "".join(res_reward) if isinstance(res_reward, list) else str(res_reward)
            blank_str = "".join(res_blank) if isinstance(res_blank, list) else str(res_blank)
            if "获得" in reward_str or "奖励" in reward_str or "点击" in blank_str or "空白" in blank_str:
                logger.info(f"Found reward popup ('{res_reward}', '{res_blank}'), clicking blank area to close...")
                self.device.click(x=930, y=670, control_name="Click_Blank_Close")
                sleep(1.5)
                continue

            # 1. 先检查是否在战后4卡技能选择界面（移到此处以防止误判进入3卡子技能强化弹窗逻辑）
            if self.appear(self.I_SELECT_0) or self.appear(self.I_SELECT_1) or self.appear(self.I_SELECT_2) or self.appear(self.I_SELECT_3):
                logger.info("Found skill selection cards, selecting the skill (priority: rightmost)...")
                if self.appear_then_click(self.I_SELECT_3, interval=2):
                    continue
                if self.appear_then_click(self.I_SELECT_2, interval=2):
                    continue
                if self.appear_then_click(self.I_SELECT_1, interval=2):
                    continue
                if self.appear_then_click(self.I_SELECT_0, interval=2):
                    continue

            # 2. 战后三卡（强化级）子技能选择界面
            # 采用全屏绝对坐标 OCR 对截图进行识别，防止局部 OCR 的 ROI 偏移影响
            from module.atom.ocr import RuleOcr
            full_ocr = RuleOcr(roi=(0, 0, 1280, 720), area=(0, 0, 1280, 720), mode="Full", method="Default", keyword="", name="full_screen_ocr")
            ocr_results = full_ocr.detect_and_ocr(self.device.image, logDisplay=False)
            ocr_texts = [res.ocr_text for res in ocr_results]
            
            if any(t in ocr_texts for t in ["力量强化", "技巧强化", "魅力强化"]):
                logger.info("Inside sub-skill (dancing style reinforcement) selection popup")
                
                # 初始化三个绝对卡牌槽位数据
                slots = [
                    {"name": None, "level": 0, "btn": (292, 518)},
                    {"name": None, "level": 0, "btn": (647, 518)},
                    {"name": None, "level": 0, "btn": (1002, 518)}
                ]
                
                import re
                for res in ocr_results:
                    box = res.box
                    cx = int((box[0, 0] + box[2, 0]) / 2)
                    cy = int((box[0, 1] + box[2, 1]) / 2)
                    
                    slot_idx = None
                    if 100 <= cx <= 420:
                        slot_idx = 0
                    elif 420 < cx <= 840:
                        slot_idx = 1
                    elif 840 < cx <= 1180:
                        slot_idx = 2
                        
                    if slot_idx is not None:
                        text = res.ocr_text
                        if "力量" in text:
                            slots[slot_idx]["name"] = "力量强化"
                        elif "技巧" in text:
                            slots[slot_idx]["name"] = "技巧强化"
                        elif "魅力" in text:
                            slots[slot_idx]["name"] = "魅力强化"
                            
                        # 按钮检测：如果是“选择”且在按钮绝对高度范围内
                        if text == "选择" and 480 <= cy <= 560:
                            slots[slot_idx]["btn"] = (cx, cy)
                            
                # 精准识别三个卡牌对应的强化具体等级
                from module.atom.ocr import RuleOcr
                ocr_power_level = RuleOcr(roi=(250, 235, 19, 26), area=(250, 235, 19, 26), mode="Digit", method="Default", keyword="", name="level_power")
                ocr_skill_level = RuleOcr(roi=(608, 239, 16, 22), area=(608, 239, 16, 22), mode="Digit", method="Default", keyword="", name="level_skill")
                ocr_charm_level = RuleOcr(roi=(966, 238, 15, 21), area=(966, 238, 15, 21), mode="Digit", method="Default", keyword="", name="level_charm")

                val_power = ocr_power_level.ocr(self.device.image)
                val_skill = ocr_skill_level.ocr(self.device.image)
                val_charm = ocr_charm_level.ocr(self.device.image)

                def parse_int(v):
                    try:
                        return int(v) if v is not None else 0
                    except:
                        return 0

                slots[0]["level"] = parse_int(val_power)
                slots[1]["level"] = parse_int(val_skill)
                slots[2]["level"] = parse_int(val_charm)
                                    
                # 更新全局等级缓存
                for slot in slots:
                    if slot["name"] == "力量强化" and slot["level"] > 0:
                        self.power_level = slot["level"]
                    elif slot["name"] == "技巧强化" and slot["level"] > 0:
                        self.skill_level = slot["level"]

                logger.info(f"Sub-skill slots parsed: {slots}, global levels: power={self.power_level}, skill={self.skill_level}")
                
                # 寻找不同状态的槽位
                power_under_4 = None
                skill_under_4 = None
                power_between_4_and_10 = None
                skill_between_4_and_10 = None

                for slot in slots:
                    if slot["name"] == "力量强化":
                        if slot["level"] < 4:
                            power_under_4 = slot
                        elif slot["level"] < 10:
                            power_between_4_and_10 = slot
                    elif slot["name"] == "技巧强化":
                        if slot["level"] < 4:
                            skill_under_4 = slot
                        elif slot["level"] < 10:
                            skill_between_4_and_10 = slot
                
                # 优先点击低于 4 级的目标
                if power_under_4:
                    logger.info(f"Selecting '力量强化' at {power_under_4['btn']} (current level: {power_under_4['level']})")
                    self.device.click(x=power_under_4['btn'][0], y=power_under_4['btn'][1], control_name="Select_Power_Reinforce")
                    self.reinforce_refresh_count = 0
                    sleep(2)
                    continue
                elif skill_under_4:
                    logger.info(f"Selecting '技巧强化' at {skill_under_4['btn']} (current level: {skill_under_4['level']})")
                    self.device.click(x=skill_under_4['btn'][0], y=skill_under_4['btn'][1], control_name="Select_Skill_Reinforce")
                    self.reinforce_refresh_count = 0
                    sleep(2)
                    continue
                
                # 若需要刷新低于4级的目标且刷新次数未满
                need_refresh = False
                if self.power_level < 4 and not any(s["name"] == "力量强化" for s in slots):
                    need_refresh = True
                if self.skill_level < 4 and not any(s["name"] == "技巧强化" for s in slots):
                    need_refresh = True

                if need_refresh and self.reinforce_refresh_count < 3:
                    refresh_clicked = False
                    for res in ocr_results:
                        if "剩" in res.ocr_text or "次" in res.ocr_text:
                            box = res.box
                            rx = int((box[0, 0] + box[2, 0]) / 2)
                            ry = int((box[0, 1] + box[2, 1]) / 2) - 40
                            logger.info(f"Found refresh text '{res.ocr_text}', clicking refresh button at ({rx}, {ry})")
                            self.device.click(x=rx, y=ry, control_name="Refresh_Reinforce")
                            refresh_clicked = True
                            self.reinforce_refresh_count += 1
                            sleep(2)
                            break
                    
                    if not refresh_clicked:
                        logger.info("No refresh text detected, trying fallback refresh at (960, 510)...")
                        self.device.click(x=960, y=510, control_name="Refresh_Reinforce_Fallback")
                        self.reinforce_refresh_count += 1
                        sleep(2)
                    continue

                # 若都已达到 4 级或者刷新次数用尽，则直接选择 4~10 级之间的目标直接升级以省钱
                if power_between_4_and_10:
                    logger.info(f"Selecting '力量强化' at {power_between_4_and_10['btn']} (level: {power_between_4_and_10['level']})")
                    self.device.click(x=power_between_4_and_10['btn'][0], y=power_between_4_and_10['btn'][1], control_name="Select_Power_Reinforce_Save")
                    self.reinforce_refresh_count = 0
                    sleep(2)
                    continue
                elif skill_between_4_and_10:
                    logger.info(f"Selecting '技巧强化' at {skill_between_4_and_10['btn']} (level: {skill_between_4_and_10['level']})")
                    self.device.click(x=skill_between_4_and_10['btn'][0], y=skill_between_4_and_10['btn'][1], control_name="Select_Skill_Reinforce_Save")
                    self.reinforce_refresh_count = 0
                    sleep(2)
                    continue

                # 实在没有 4~10 级的目标（或他们都达到 10 级上限了），执行兜底选择
                logger.info("No preferred slots available or target skills maxed out. Executing fallback select...")
                fallback_slot = None
                for slot in slots:
                    if slot["name"] == "魅力强化" and slot["level"] < 10:
                        fallback_slot = slot
                        break
                if not fallback_slot:
                    for slot in slots:
                        if slot["name"] is not None:
                            fallback_slot = slot
                            break
                if not fallback_slot:
                    fallback_slot = slots[2]
                    
                logger.info(f"Fallback selection: clicking {fallback_slot['name']} at {fallback_slot['btn']}")
                self.device.click(x=fallback_slot['btn'][0], y=fallback_slot['btn'][1], control_name="Select_Reinforce_Fallback")
                self.reinforce_refresh_count = 0
                sleep(2)
                continue

            # 如果在六道入口大厅或初始技能选择界面，执行进入流程（且未进入关卡内）
            if (self.appear(page_six_gates.check_button) or self.is_peacock_lobby() or self.appear(self.O_SKILL_SELECT_LOBBY)) and not (self.appear(self.I_PREPARE_BATTLE) or self.appear(self.I_M_STORE)):
                self.run_six_realms()
                continue

            # 检测当前的关卡名 (如 鏖战之屿、混沌之屿 等)
            island_name = self.O_ISLAND_NAME.ocr(self.device.image)

            # 如果在战斗/事件岛屿 (鏖战之屿 / 绽放之屿 / 混沌之屿) 内部
            if "之屿" in island_name and ("战" in island_name or "绽" in island_name or "放" in island_name or "混" in island_name or "沌" in island_name):
                logger.info(f"Currently inside combat/event island: {island_name}")
                self.select_monster_and_fight()
                continue

            # 如果在其它非战斗岛屿 (如神秘之屿、宁息之屿/商店) 内部，自动退出
            if "之屿" in island_name and ("神" in island_name or "秘" in island_name or "息" in island_name or "宁" in island_name):
                logger.info(f"Currently inside non-combat island: {island_name}")
                # 0. 如果有“是否离开...之屿？”确认弹窗
                if any("离开" in t for t in ocr_texts) and any("确定" in t for t in ocr_texts):
                    logger.info("Leave confirm popup detected, clicking confirm button at (761, 437)...")
                    self.device.click(x=761, y=437, control_name="Leave_Confirm")
                    sleep(1.5)
                    continue

                # 如果是宁息之屿，直接点击右下角离开按钮 (1225, 640)
                if "宁" in island_name or "息" in island_name:
                    logger.info("Ningxi island detected, clicking bottom-right leave button at (1225, 640)...")
                    self.device.click(x=1225, y=640, control_name="Click_Ningxi_Leave")
                    sleep(1.5)
                    continue

                # 如果是神秘之屿，直接点击左上角返回按钮 (30, 39)
                if "神" in island_name or "秘" in island_name:
                    logger.info("Mysterious island detected, directly clicking top-left back button at (30, 39)...")
                    self.device.click(x=30, y=39, control_name="Click_Back_Arrow")
                    sleep(1.5)
                    continue

                # 1. 尝试点击宁息之屿商店退出
                if self.appear_then_click(self.I_STORE_EXIT, interval=2):
                    continue
                # 2. 尝试点击神秘之屿原有出口
                if self.appear_then_click(self.I_L103_EXIT, interval=2):
                    continue
                # 3. 兜底点击左上角返回按钮 (30, 39)
                logger.info("Clicking top-left back button at (30, 39) to exit island...")
                self.device.click(x=30, y=39, control_name="Click_Back_Arrow")
                sleep(1.5)
                continue

            # 如果是在岛屿选择界面 (O_ISLAND_NAME 为 "孔雀国" 或者是空白但看到了浮空岛)
            if island_name == "孔雀国" or "国" in island_name or (island_name == "" and (self.appear(self.I_ISLAND_AOZHAN) or self.appear(self.I_ISLAND_SHENMI) or self.appear(self.I_ISLAND_HUNDUN))):
                logger.info("On island selection screen")
                if self.select_island():
                    # 动态等待转场完成，最长等待 5 秒，检测周期为 0.2 秒
                    logger.info("Waiting for island selection transition...")
                    for _ in range(25):
                        sleep(0.2)
                        self.screenshot()
                        new_name = self.O_ISLAND_NAME.ocr(self.device.image)
                        
                        # 1. 成功进入任意之屿
                        if "之屿" in new_name:
                            logger.info(f"Entered island: {new_name}")
                            break
                            
                        # 2. 成功进入战斗准备、商店或者技能选择界面
                        if (
                            self.appear(self.I_PREPARE_BATTLE) or 
                            self.appear(self.I_M_STORE) or 
                            self.appear(self.I_SELECT_0) or 
                            self.appear(self.I_SELECT_1) or 
                            self.appear(self.I_SELECT_2) or 
                            self.appear(self.I_SELECT_3)
                        ):
                            logger.info("Transition to battle/store/card screen completed")
                            break
                            
                        # 3. 已经离开了岛屿选择界面（画面已渐变淡出，名称不再包含国且背景没有浮空岛）
                        is_still_selection = "国" in new_name or self.appear(self.I_ISLAND_AOZHAN) or self.appear(self.I_ISLAND_SHENMI) or self.appear(self.I_ISLAND_HUNDUN)
                        if not is_still_selection:
                            logger.info("Left selection screen, waiting for final screen...")
                            sleep(1.0)
                            break
                    continue

            # 兜底：如果卡在退出、跳过或某些弹窗上
            if self.appear_then_click(self.I_MSTART_CONFIRM, interval=2):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM, interval=2):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=2):
                continue

            sleep(1)

        self.set_next_run('SixRealms', success=True, finish=True)
        raise TaskEnd

    def run_six_realms(self):
        logger.hr('Peacock Kingdom Entry', 1)
        while 1:
            self.screenshot()
            
            # If we successfully entered the run (prepare battle or store, but NOT on the starting skill selection screen)
            if (self.appear(self.I_PREPARE_BATTLE) or self.appear(self.I_PREPARE_HIGHLIGHT) or self.appear(self.I_M_STORE)) and not self.appear(self.I_SKILL_SELECT_0):
                logger.info("Successfully entered Peacock Kingdom run")
                break
            
            # Or if we see the exit popup or shikigami selection confirmation
            if self.appear(self.I_EXIT_SIXREALMS) or self.appear(self.I_SELECT_SHIKIGAMI_AND_CONFIRM):
                logger.info("Successfully entered Peacock Kingdom run")
                break

            # 3卡战中技能选择界面（不同于大厅的初始技能选择）也代表已成功进入副本
            if self.appear(self.I_SELECT_1) or self.appear(self.I_SELECT_2) or self.appear(self.I_SELECT_3):
                logger.info("Detected in-run 3-card skill selection, entering main loop")
                break
            
            # 【优先级最高】60体力弹窗确认 —— 必须在 I_MSTART 之前检测！
            # 否则 I_MSTART 会透过弹窗背景匹配到，导致死循环点"开启"
            if self.appear_then_click(self.I_AP_CONFIRM, interval=2):
                logger.info("Confirmed 60 AP popup")
                sleep(2.0)
                continue
            if self.appear_then_click(self.I_MSTART_CONFIRM, interval=2):
                continue
            if self.appear_then_click(self.I_MSTART_CONFIRM2, interval=2):
                continue

            if self.appear_then_click(self.I_MSTART, interval=2):
                sleep(2.0)
                continue
            if self.appear_then_click(self.I_BOSS_FIRE, interval=2):
                logger.info("Clicked boss challenge button")
                sleep(2.0)
                continue
            if self.appear_then_click(self.I_MCONINUE, interval=2):
                sleep(2.0)
                continue

            # If we are on the Peacock Kingdom lobby screen, click the challenge button
            if self.is_peacock_lobby():
                logger.info("Inside Peacock Kingdom lobby screen, clicking challenge button...")
                self.device.click(x=1160, y=630, control_name="Peacock_Lobby_Challenge")
                sleep(2.0)
                continue

            # If we are on the starting skill selection lobby, click the first skill
            if self.appear(self.O_SKILL_SELECT_LOBBY):
                if self.appear(self.I_SELECT_0, interval=2):
                    x, y = self.I_SELECT_0.coord()
                    logger.info(f"Clicking card body above I_SELECT_0 at ({x}, {y - 100})")
                    self.device.click(x, y - 100, control_name="SELECT_0_CARD_BODY")
                    sleep(2.0)
                    continue

            # If we are on the initial skill selection screen, click the first skill
            if self.appear(self.I_SKILL_SELECT_0, interval=2):
                x, y = self.I_SKILL_SELECT_0.coord()
                logger.info(f"Clicking card body above I_SKILL_SELECT_0 at ({x}, {y - 100})")
                self.device.click(x, y - 100, control_name="SKILL_SELECT_0_CARD_BODY")
                sleep(2.0)
                continue
            if self.appear_then_click(self.I_UI_CONFIRM, interval=2):
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=2):
                continue
            if self.appear_then_click(self.I_MSKIP, interval=2):
                continue
            if self.appear_then_click(self.I_MSTART_UNCHECK, interval=2):
                continue
            
            if self.appear_then_click(self.I_MENTER, action=self.C_MENTER, interval=2):
                sleep(2.0)
                continue

    def select_island(self) -> bool:
        """
        选择普通岛屿：优先选择鏖战岛屿，次选混乱岛屿，其它岛屿作为兜底
        """
        logger.hr('Island Selection', 1)
        self.screenshot()

        # 1. 优先尝试模板匹配寻找“鏖战”
        if self.appear(self.I_ISLAND_AOZHAN):
            logger.info("Found Aozhan island via template matching, clicking...")
            self.click(self.I_ISLAND_AOZHAN)
            return True

        # 1.5 尝试模板匹配寻找“混沌”
        if self.appear(self.I_ISLAND_HUNDUN):
            logger.info("Found Hundun island via template matching, clicking...")
            self.click(self.I_ISLAND_HUNDUN)
            return True

        # 2. 如果模板匹配没有找到，使用 OCR 识别候选区域中的岛屿名称
        results = self.O_OCR_MAP.detect_and_ocr(self.device.image)
        candidates = []
        for res in results:
            text = res.ocr_text
            box = res.box

            # 计算绝对屏幕坐标（需要叠加 O_OCR_MAP 的 roi 偏移）
            x = box[0, 0] + self.O_OCR_MAP.roi[0]
            y = box[0, 1] + self.O_OCR_MAP.roi[1]
            w = box[1, 0] - box[0, 0]
            h = box[2, 1] - box[0, 1]

            # 目标点击点取中心点
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
                logger.info(f"Detected island candidate: {island_type} ('{text}') at {(cx, cy)}")

        # 按照优先级排序：鏖战 -> 混沌 -> 神秘 -> 宁息
        priority_map = {
            "鏖战": 1,
            "混沌": 2,
            "神秘": 3,
            "宁息": 4
        }

        if candidates:
            candidates.sort(key=lambda x: priority_map.get(x["type"], 99))
            best = candidates[0]
            logger.info(f"Selecting best island: {best['type']} at {best['center']} (detected as '{best['text']}')")
            self.device.click(x=best["center"][0], y=best["center"][1], control_name=f"Island_{best['type']}")
            return True

        # 3. 兜底尝试模板匹配“神秘”
        if self.appear(self.I_ISLAND_SHENMI):
            logger.info("Found Shenmi island via template matching, clicking...")
            self.click(self.I_ISLAND_SHENMI)
            return True

        # 4. 极致兜底：如果依然没有匹配到任何已知岛屿（由于岛屿在上下飘动、位置不固定且OCR可能漏字）
        # 采用三点轮询辅助，依次尝试点击左侧、右侧、中部浮空岛的常态中心位置，确保100%成功触发岛屿进入
        if not hasattr(self, "_fallback_island_index"):
            self._fallback_island_index = 0
        
        fallback_points = [
            (300, 530, "Left_Island_Fallback"),
            (720, 630, "Right_Island_Fallback"),
            (640, 480, "Center_Island_Fallback")
        ]
        
        fx, fy, name = fallback_points[self._fallback_island_index % 3]
        self._fallback_island_index += 1
        
        logger.info(f"No priority island detected. Using anchored helper click at ({fx}, {fy}) @ {name}...")
        self.device.click(x=fx, y=fy, control_name=name)
        sleep(0.5)
        return True

    def select_monster_and_fight(self) -> bool:
        """
        在鏖战之屿/混沌之屿中，默认选择右边的怪物并进行战斗
        """
        logger.hr('Monster Selection & Battle', 1)

        # 0. 获取全屏 OCR 结果以用于特例判断
        from module.atom.ocr import RuleOcr
        full_ocr = RuleOcr(roi=(0, 0, 1280, 720), area=(0, 0, 1280, 720), mode="Full", method="Default", keyword="", name="full_screen_ocr")
        ocr_results = full_ocr.detect_and_ocr(self.device.image, logDisplay=False)
        ocr_texts = [res.ocr_text for res in ocr_results]

        # 0.05 优先检测“是否离开...之屿？”确认弹窗
        if any("离开" in t for t in ocr_texts) and any("确定" in t for t in ocr_texts):
            logger.info("Leave confirm popup detected, clicking confirm button at (761, 437)...")
            self.device.click(x=761, y=437, control_name="Leave_Confirm")
            sleep(1.5)
            return True

        # 0.1 检测到幸运宝匣时直接选择离开（不开启以避免负面Debuff）
        is_chest_unopened = any("宝匣" in t or "宝画" in t or "幸运宝" in t for t in ocr_texts)
        if is_chest_unopened:
            leave_btn = None
            for res in ocr_results:
                if "离开" in res.ocr_text and res.box[0, 0] > 1100 and res.box[0, 1] > 600:
                    cx = int((res.box[0, 0] + res.box[2, 0]) / 2)
                    cy = int((res.box[0, 1] + res.box[2, 1]) / 2)
                    leave_btn = (cx, cy)
                    break
            if not leave_btn:
                leave_btn = (1180, 690)  # 兜底右下角离开按钮坐标
            logger.info(f"Lucky chest (幸运宝匣) unopened detected. Skipping chest and clicking leave button at {leave_btn}...")
            self.device.click(x=leave_btn[0], y=leave_btn[1], control_name="Skip_Chest_Leave")
            sleep(2)
            return True

        # 0.12 检测并处理宝匣已开启后剩下的“离开”按钮
        leave_btn = None
        for res in ocr_results:
            if "离开" in res.ocr_text and res.box[0, 0] > 1100 and res.box[0, 1] > 600:
                cx = int((res.box[0, 0] + res.box[2, 0]) / 2)
                cy = int((res.box[0, 1] + res.box[2, 1]) / 2)
                leave_btn = (cx, cy)
                break
        if leave_btn and not any(t in ocr_texts for t in ["不知火", "铃彦姬", "绽放", "挑战", "战"]):
            logger.info(f"Lucky chest opened and only leave button detected at {leave_btn}, clicking it...")
            self.device.click(x=leave_btn[0], y=leave_btn[1], control_name="Click_Leave_Button")
            sleep(2)
            return True

        # 0.13 检测混沌之屿精英对战分支
        island_name = self.O_ISLAND_NAME.ocr(self.device.image)
        if "混" in island_name or "沌" in island_name:
            from module.ocr.models import get_ocr_model
            model = get_ocr_model("ch")
            crop_elite = self.device.image[178:178+80, 595:595+80]
            res_elite = model.detect_and_ocr(crop_elite)
            elite_btn = None
            for r in res_elite:
                if r.score > 0.5 and ("精" in r.ocr_text or "英" in r.ocr_text):
                    cx = 595 + int((r.box[0, 0] + r.box[2, 0]) / 2)
                    cy = 178 + int((r.box[0, 1] + r.box[2, 1]) / 2)
                    elite_btn = (cx, cy)
                    break
            if elite_btn:
                logger.info(f"Elite badge detected at {elite_btn}, entering elite prep screen...")
                self.device.click(x=elite_btn[0], y=elite_btn[1], control_name="Click_Elite_Badge")
                sleep(1.5)

                # 等待挑战按钮并点击以开始对战
                for _ in range(5):
                    self.screenshot()
                    crop_chal = self.device.image[580:580+90, 1100:1100+150]
                    res_chal = model.detect_and_ocr(crop_chal)
                    challenge_btn = None
                    for r in res_chal:
                        if r.score > 0.5 and ("战" in r.ocr_text or "挑" in r.ocr_text):
                            cx = 1100 + int((r.box[0, 0] + r.box[2, 0]) / 2)
                            cy = 580 + int((r.box[0, 1] + r.box[2, 1]) / 2)
                            challenge_btn = (cx, cy)
                            break
                    if challenge_btn:
                        logger.info(f"Challenge button detected at {challenge_btn}, clicking to start battle...")
                        self.device.click(x=challenge_btn[0], y=challenge_btn[1], control_name="Click_Challenge")
                        sleep(1.5)
                        self.run_general_battle(config=self._config.general_battle_config)
                        break
                    sleep(1)
                return True

        # 0.15 优先检测是否为式神技能学习界面
        from module.atom.image import RuleImage
        rule_learn = RuleImage(roi_front=(1129, 588, 76, 94), roi_back=(1080, 550, 180, 150), method="Template matching", threshold=0.8, file="./tasks/SixRealms/gate1/gate1_learn.png")
        is_skill_learn = rule_learn.match(self.device.image) or any("绽放之舞" in t or "绽放舜" in t or "雀舞" in t or "暴击伤害" in t or "每造成" in t for t in ocr_texts)
        if is_skill_learn:
            logger.info("Jinnara skill learning page detected, clicking learn button at (1160, 630)...")
            self.device.click(x=1160, y=630, control_name="Click_Skill_Learn")
            sleep(1.5)
            # 点击后立即开始进行常规战斗挂机与自动结算
            logger.info("Entering general battle for Zhanfang Island...")
            self.run_general_battle(config=self._config.general_battle_config)
            logger.info("General battle finished")
            return True

        # 0.2 优先检测是否为绽放之屿选择紧那罗界面
        jinnara_slot = None
        for res in ocr_results:
            if "紧那罗" in res.ocr_text:
                box = res.box
                cx = int((box[0, 0] + box[2, 0]) / 2)
                cy = int((box[0, 1] + box[2, 1]) / 2)
                jinnara_slot = (cx, cy)
                break

        # 辅助判断：即使没找到“紧那罗”文字本身，如果找到“不知火”、“铃彦姬”，或者识别出岛屿名包含“绽”、“放”
        is_zhanfang = jinnara_slot is not None or any(t in ocr_texts for t in ["不知火", "铃彦姬", "绽放"]) or "绽" in self.O_ISLAND_NAME.ocr(self.device.image) or "放" in self.O_ISLAND_NAME.ocr(self.device.image)

        if is_zhanfang:
            if jinnara_slot:
                click_x = jinnara_slot[0] + 150
                click_y = jinnara_slot[1]
                logger.info(f"Detected '紧那罗' at {jinnara_slot}, clicking card area at ({click_x}, {click_y})...")
            else:
                # 盲点最左侧紧那罗立绘的固定绝对坐标中点
                click_x = 200
                click_y = 360
                logger.info(f"Zhanfang island (绽放之屿) detected but '紧那罗' text is missing, clicking fallback coordinate at ({click_x}, {click_y})...")
            self.device.click(x=click_x, y=click_y, control_name="Select_Jinnara")
            sleep(1.5)
            return True

        # 1. 尝试选择右边的怪物，直到 I_NPC_FIRE (挑战按钮) 出现
        for _ in range(3):
            self.screenshot()
            if self.appear(self.I_NPC_FIRE):
                logger.info("Challenge button is visible")
                break

            results = self.O_OCR_MAP.detect_and_ocr(self.device.image)
            candidates = []
            for res in results:
                box = res.box
                x = box[0, 0] + self.O_OCR_MAP.roi[0]
                y = box[0, 1] + self.O_OCR_MAP.roi[1]
                w = box[1, 0] - box[0, 0]
                h = box[2, 1] - box[0, 1]

                # 过滤可能属于怪物的垂直文字条 (位于关卡选择区与结算弹窗之外的中部区域)
                if 200 <= x <= 1000 and 250 <= y <= 550:
                    candidates.append({
                        "text": res.ocr_text,
                        "cx": int(x + w / 2),
                        "cy": int(y + h / 2)
                    })

            # 对检测出的字进行X轴坐标聚类分组
            groups = []
            for c in candidates:
                added = False
                for g in groups:
                    if abs(g["x_avg"] - c["cx"]) < 50:
                        g["items"].append(c)
                        g["x_avg"] = sum(item["cx"] for item in g["items"]) / len(g["items"])
                        # 选择Y坐标较大者（名字在更下方，有利于点击到主要位置）
                        if c["cy"] > g["click_y"]:
                            g["click_y"] = c["cy"]
                        added = True
                        break
                if not added:
                    groups.append({
                        "x_avg": c["cx"],
                        "click_y": c["cy"],
                        "items": [c]
                    })

            # 如果检测到分组，默认点击右侧的分组 (x_avg 最大)
            if groups:
                groups.sort(key=lambda g: g["x_avg"])
                target = groups[-1]
                cx, cy = int(target["x_avg"]), target["click_y"]
                logger.info(f"Dynamic OCR selecting right monster at ({cx}, {cy}), detected name items: {[item['text'] for item in target['items']]}")
                self.device.click(x=cx, y=cy, control_name="Select_Right_Monster")
            else:
                logger.info("No monster detected via OCR, clicking fallback right coordinate...")
                self.click(self.C_NPC_FIRE_RIGHT)

            sleep(1.5)

        # 2. 如果还是没出现挑战按钮，尝试点击 C_NPC_FIRE_CENTER (单体精英怪)
        if not self.appear(self.I_NPC_FIRE):
            logger.info("Right monster challenge button not visible, trying center monster...")
            self.click(self.C_NPC_FIRE_CENTER)
            sleep(1.5)

        # 3. 兜底尝试点击 C_NPC_FIRE_LEFT
        if not self.appear(self.I_NPC_FIRE):
            logger.info("Center monster not found, trying left monster...")
            self.click(self.C_NPC_FIRE_LEFT)
            sleep(1.5)

        # 4. 点击“点击挑战”按钮进入战斗
        if self.appear_then_click(self.I_NPC_FIRE, interval=1):
            logger.info("Clicked challenge button, entering general battle...")
            # 5. 调用 GeneralBattle 模块进行战斗与自动准备、结算
            self.run_general_battle(config=self._config.general_battle_config)
            logger.info("General battle finished")
            return True

        logger.warning("Failed to select monster and start battle")
        return False

    def battle_wait(self, random_click_swipt_enable: bool) -> bool:
        """
        六道之门定制的战斗等待：在常规战斗等待的基础上，加入对战后卡牌奖励选择界面的识别
        """
        import random
        self.device.stuck_record_add('BATTLE_STATUS_S')
        self.device.click_record_clear()
        logger.info("Start battle process (SixRealms custom)")
        win: bool = False
        while 1:
            self.screenshot()
            
            # 战后卡牌选择界面检测：出现卡牌选择按钮表示战斗已结束，赢了
            if (self.appear(self.I_SELECT_0) or self.appear(self.I_SELECT_1) or 
                self.appear(self.I_SELECT_2) or self.appear(self.I_SELECT_3)):
                logger.info("Detected card selection page during battle wait, battle finished (win)")
                win = True
                break

            # 最终首领结算检测：出现使用双倍/分享/获取经验/椒图结算表示首领战已结束，赢了
            if (self.appear(self.I_BOSS_USE_DOUBLE) or self.appear(self.I_BOSS_GET_EXP) or 
                self.appear(self.I_BOSS_SHARE) or self.appear(self.I_BOSS_SHUTU)):
                logger.info("Detected boss battle settlement page during battle wait, battle finished (win)")
                win = True
                break

            # 常规结算检测
            if self.appear(self.I_WIN, threshold=0.8) or self.appear(self.I_DE_WIN):
                logger.info("Battle result is win")
                if self.appear(self.I_DE_WIN):
                    self.ui_click_until_disappear(self.I_DE_WIN)
                win = True
                break

            if self.appear(self.I_FALSE, threshold=0.8):
                logger.info("Battle result is false")
                win = False
                break

            if self.appear(self.I_REWARD, threshold=0.6) or self.appear(self.I_REWARD_GOLD, threshold=0.8):
                win = True
                break

            if random_click_swipt_enable:
                self.random_click_swipt()
            else:
                sleep(0.5)

        # 再次确认战斗结果并关闭结算（由于可能直接跳到卡牌，所以在不是卡牌界面时才去点赢了的图标）
        logger.info("Reconfirm the results of the battle")
        while 1:
            self.screenshot()
            # 如果已经到了卡牌界面，不需要点赢了图标，直接返回
            if (self.appear(self.I_SELECT_0) or self.appear(self.I_SELECT_1) or 
                self.appear(self.I_SELECT_2) or self.appear(self.I_SELECT_3)):
                break
                
            if win:
                action_click = random.choice([self.C_WIN_1, self.C_WIN_2, self.C_WIN_3])
                if self.appear_then_click(self.I_WIN, action=action_click, interval=0.5):
                    continue
                if not self.appear(self.I_WIN):
                    break
            else:
                if self.appear_then_click(self.I_FALSE, threshold=0.6):
                    continue
                if not self.appear(self.I_FALSE, threshold=0.6):
                    return False

        # 如果需要获取奖励
        if not (self.appear(self.I_SELECT_0) or self.appear(self.I_SELECT_1) or 
                self.appear(self.I_SELECT_2) or self.appear(self.I_SELECT_3)):
            if self.wait_until_appear(self.I_REWARD, wait_time=5):
                logger.info("Get reward")
                while 1:
                    self.screenshot()
                    action_click = random.choice([self.C_REWARD_1, self.C_REWARD_2, self.C_REWARD_3])
                    if (self.appear_then_click(self.I_REWARD, action=action_click, interval=1.5) or
                        self.appear_then_click(self.I_REWARD_GOLD, action=action_click, interval=1.5)):
                        continue
                    if not self.appear(self.I_REWARD) and not self.appear(self.I_REWARD_GOLD):
                        break

        return win

if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()
