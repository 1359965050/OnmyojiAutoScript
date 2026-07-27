from module.atom.image import RuleImage
from module.logger import logger
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import GeneralBattle, BattleContext, BattleAction
from tasks.SixRealms.common import SixRealmsCommon
import tasks.SixRealms.peacock_kingdom.page as pages
from typing import List, Optional


class BasePeacockKingdom(GeneralBattle, SixRealmsCommon):
    coin_num: int = 0
    skill_roaring_thunder: int = 0
    skill_qingcheng: int = 0
    skill_liuyu: int = 0
    skill_power_level: int = 0

    def get_pk_skill_select_ocr(self, priority_names: List[str]) -> tuple[Optional[int], Optional[str]]:
        """
        使用OCR读取技能名称，返回 (匹配到的最高优先级技能的中心X坐标, 技能名称)
        """
        for name in priority_names:
            x, y, w, h = self.O_PK_SKILL_NAME.ocr_full(self.device.image, keyword=name)
            if w > 0:
                logger.info(f'OCR Recognize skill: {name} at x={x}')
                return x + w // 2, name
        return None, None

    def get_pk_skill_select(self, skill_rule_list: List[RuleImage]) -> tuple[Optional[RuleImage], Optional[RuleImage]]:
        """
        获取孔雀国技能对应的选择按钮及对应规则
        :param skill_rule_list: 技能列表
        :return: (选择按钮, 对应的技能规则)
        """
        if not skill_rule_list:
            return None, None
        for skill_rule in skill_rule_list:
            if not self.appear(skill_rule):
                continue
            logger.info(f'Recognize skill: {skill_rule.name}')
            x, y = skill_rule.front_center()
            btn = None
            if 240 < x < 340:
                btn = self.I_PK_SELECT_0
            elif 590 <= x < 690:
                btn = self.I_PK_SELECT_1
            elif 950 <= x < 1050:
                btn = self.I_PK_SELECT_2
            elif 420 <= x < 520:
                btn = self.I_PK_SELECT_3
            elif 775 <= x < 875:
                btn = self.I_PK_SELECT_4
            if btn:
                return btn, skill_rule
            break
        return None, None

    def before_run(self):
        self.coin_num = 0
        self.skill_roaring_thunder = 0
        self.skill_qingcheng = 0
        self.skill_liuyu = 0
        self.skill_power_level = 0
        pages.page_battle = self.navigator.resolve_page(pages.page_battle)
        pages.page_battle.recognizer = pages.any_of(self.I_BOSS_SKIP, pages.page_battle.recognizer)
        pages.page_battle_result = self.navigator.resolve_page(pages.page_battle_result)
        pages.page_battle_result.recognizer = pages.any_of(self.I_BOSS_BATTLE_AGAIN, self.I_BOSS_BATTLE_GIVEUP,
                                                           self.I_PK_SELECT_0, self.I_PK_SELECT_3,
                                                           self.I_PK_SKILL_REFRESH, self.I_UI_CONFIRM_SAMLL,
                                                           pages.page_battle_result.recognizer)
        pages.page_reward = self.navigator.resolve_page(pages.page_reward)
        pages.page_reward.recognizer = pages.any_of(self.I_COIN, self.I_SR_DOUBLE_REWARD_USE, self.I_BOSS_GET_EXP,
                                                    self.I_KP_BOSS_SHARE, self.I_BOSS_SHUTU, self.I_MS_SKILL_UNLOCK,
                                                    pages.page_reward.recognizer)

    def _handle_in_battle(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        if self.appear(self.I_PK_BATTLE_THUNDER):
            self.skill_roaring_thunder = 1  # 战斗中出现了六道轰雷, 标记已获取
        return super()._handle_in_battle(context, config)

    def _handle_result(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        context.reward_no_battle_ts = None
        # 打输了, 直接放弃
        if self.appear(self.I_BOSS_BATTLE_GIVEUP):
            context.is_win = False
            self.click(self.I_BOSS_BATTLE_GIVEUP, interval=0.8)
            return BattleAction.CONTINUE
        # 放弃之后的2次弹窗确认
        if self.appear(self.I_UI_CONFIRM_SAMLL):
            self.click(self.I_UI_CONFIRM_SAMLL, interval=0.8)
            return BattleAction.CONTINUE
        # 力量或魅力强化
        if self.appear(self.I_PK_SELECT_0, interval=1.5) or self.appear(self.I_PK_SELECT_3, interval=1.5):
            context.is_win = True
            if self.skill_power_level < 8:
                priority_list = [self.I_PK_SKILL_POWER, self.I_PK_SKILL_CHARM]
            else:
                logger.info(f'Power enhancement level reached limit ({self.skill_power_level}/8), priority switch to Charm')
                priority_list = [self.I_PK_SKILL_CHARM, self.I_PK_SKILL_POWER]

            select_btn, matched_skill = self.get_pk_skill_select(priority_list)

            # 兜底：若优先列表均未识别到，则选择出现的第一个选择按钮
            if not select_btn:
                for btn in [self.I_PK_SELECT_0, self.I_PK_SELECT_3, self.I_PK_SELECT_1, self.I_PK_SELECT_2, self.I_PK_SELECT_4]:
                    if self.appear(btn):
                        select_btn = btn
                        break

            if select_btn:
                if self.appear_then_click(select_btn, interval=1):
                    if matched_skill == self.I_PK_SKILL_POWER:
                        self.skill_power_level += 1
                        logger.info(f'Skill power level updated: {self.skill_power_level}/8')
            return BattleAction.CONTINUE
        # 选择技能
        if self.appear(self.I_SELECT_3, interval=1.5) and self.appear(self.I_PK_SKILL_REFRESH):
            # 留出时间让弹出的技能和图标动画渲染完毕
            self.device.sleep(1.5)
            context.is_win = True
            self.coin_num = self.get_coin_num(self.O_COIN_NUM)
            
            select_btn = None
            matched_skill = None
            matched_name = None

            # 1. 优先使用 OCR 读取文字
            ocr_names = []
            if self.skill_qingcheng == 0: ocr_names.append("倾城之舞")
            if self.skill_liuyu == 0: ocr_names.append("流羽剑术")
            if self.skill_roaring_thunder == 0: ocr_names.append("轰雷") # "六道·轰雷"
            
            target_x, matched_name = self.get_pk_skill_select_ocr(ocr_names)
            if target_x:
                # 既然 OCR 已经锁定了 X 坐标，直接点击下方的按钮即可，跳过图像匹配！
                logger.info(f'OCR located skill {matched_name} at X={target_x}, clicking directly.')
                self.device.click(target_x, 601, control_name='pk_skill_select')
                self.device.sleep(1.0)
                # 模拟 appear_then_click 成功的逻辑流
                if matched_name == "倾城之舞":
                    self.skill_qingcheng = 1
                    logger.info('Selected skill: 倾城之舞')
                elif matched_name == "流羽剑术":
                    self.skill_liuyu = 1
                    logger.info('Selected skill: 流羽剑术')
                elif matched_name == "轰雷":
                    self.skill_roaring_thunder = 1
                    logger.info('Selected skill: 六道轰雷')
                return BattleAction.CONTINUE

            # 2. 如果 OCR 没找到，降级使用图标图像匹配
            if not select_btn:
                skill_rules = []
                if self.skill_qingcheng == 0: skill_rules.append(self.I_PK_SKILL_QINGCHENG)
                if self.skill_liuyu == 0: skill_rules.append(self.I_PK_SKILL_LIUYU)
                if self.skill_roaring_thunder == 0: skill_rules.append(self.I_PK_SKILL_ROARING_THUNDER)
                    
                select_btn, matched_skill = self.get_pk_skill_select(skill_rules)
            
            # 3. 兜底策略
            if not select_btn:
                select_btn = self.I_SELECT_3
                
            if self.appear_then_click(select_btn, interval=1):
                if matched_skill == self.I_PK_SKILL_QINGCHENG:
                    self.skill_qingcheng = 1
                    logger.info('Selected skill: 倾城之舞')
                elif matched_skill == self.I_PK_SKILL_LIUYU:
                    self.skill_liuyu = 1
                    logger.info('Selected skill: 流羽剑术')
                elif matched_skill == self.I_PK_SKILL_ROARING_THUNDER:
                    self.skill_roaring_thunder = 1
                    logger.info('Selected skill: 六道轰雷')
        return BattleAction.CONTINUE

    def _handle_reward(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        context.reward_no_battle_ts = None
        if self.appear(self.I_BOSS_SHUTU):  # 极表示boss战赢了
            context.is_win = True
        if context.is_win and self.appear_then_click(self.I_SR_DOUBLE_REWARD_USE, interval=1.5):
            return BattleAction.CONTINUE
        if not context.is_win and self.appear_then_click(self.I_SR_DOUBLE_REWARD_CANCEL, interval=1.5):
            return BattleAction.CONTINUE
        if self.appear(self.I_SR_CHECK_BUY_BOX): # 是否前往购买万相赐福
            if self.appear_then_click(self.I_SR_NOT_TIP, interval=1.5) and self.appear_then_click(self.I_UI_CANCEL):
                return BattleAction.CONTINUE
        if self.appear(self.I_COIN, interval=2):
            self.coin_num += self.get_coin_num(self.I_COIN)
            logger.info(f'Current coin: {self.coin_num}')
        self.click(pages.random_click(), interval=1.2)
        if context.last_page != pages.page_reward:
            self.device.click_record_clear()
        return BattleAction.CONTINUE