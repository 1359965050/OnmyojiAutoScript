import time

from module.atom.image import RuleImage
from module.exception import TaskEnd
from module.logger import logger
from tasks.SixRealms.peacock_kingdom.base_peacock_kingdom import BasePeacockKingdom
import tasks.SixRealms.peacock_kingdom.page as pages
from typing import Callable


class PeacockKingdom(BasePeacockKingdom):

    def _default_detect_categories(self) -> set[str]:
        categories = super()._default_detect_categories()
        categories.add("six_realms")
        categories.add("peacock_kingdom")
        return categories

    @property
    def pk_page_handle_dict(self) -> dict[pages.Page, Callable]:
        return {
            pages.page_peacock_kingdom: self.run_on_pk,
            pages.page_pk_prepare: self.run_on_pk_prepare,
            pages.page_pk_main: self.run_on_pk_main,
            pages.page_pk_shop_land: self.run_on_pk_store,
            pages.page_pk_mistery_land: self.run_on_pk_mistery,
            pages.page_pk_chaos_land: self.run_on_pk_chaos,
            pages.page_pk_bloom_land: self.run_on_pk_bloom,
            pages.page_pk_battle_land: self.run_on_pk_battle,
            pages.page_pk_challenge: self.run_on_pk_challenge,
            pages.page_pk_map: lambda: self.goto_page(pages.page_pk_main),
            pages.page_pk_exit: lambda: self.click(pages.random_click(ltrb=(True, False, False, False)), interval=1.2),
            pages.page_sr_prepare_exit: lambda: self.goto_page(pages.page_pk_prepare),
            pages.page_sr_open_store: lambda: self.goto_page(pages.page_pk_main),
            pages.page_battle_prepare: self.run_on_pk_challenge,
            pages.page_battle: self.run_on_pk_challenge,
            pages.page_battle_result: self.run_on_pk_challenge,
            pages.page_reward: lambda: self.click(pages.random_click(), interval=1.2),
        }

    def run(self):
        self.before_run()
        logger.hr('Peacock Kingdom', 1)
        while True:
            self.screenshot()
            current_page = self.get_current_page()
            if current_page is None:
                time.sleep(0.5)
                continue
            handle = self.pk_page_handle_dict.get(current_page, None)
            if handle is None:
                self.goto_page(pages.page_peacock_kingdom)
                continue
            try:
                handle()
            except TaskEnd:
                break
        logger.info('Peacock Kingdom task ended')
                
    def run_on_pk(self):
        """孔雀国界面"""
        if self.appear_then_click(self.I_PK_CONTINUE, interval=1):
            return
        if self.appear_then_click(self.I_PK_START, interval=1):
            return

    def run_on_pk_prepare(self):
        """进入孔雀国主界面前的准备界面（含初始祝福选择 + 初始技能选择 + 开启确认）"""
        # 1. 初始祝福选择界面（"精进我的一种舞技吧"）
        if self.appear_then_click(self.I_PK_START_FIRST_SKILL, interval=1.5):
            logger.info('Select blessing: 绽放之舞 (First Option)')
            return
        # 2. 初始技能选择界面（怪力乱神等）
        if self.appear(self.I_PK_SKILL_STRANGE_POWER):
            x, _ = self.I_PK_SKILL_STRANGE_POWER.front_center()
            logger.info(f'Click strange power select button at x={x}, y=585')
            self.device.click(x=x, y=585, control_name='strange_power_select')
            return
        # 3. "是否消耗60体力进入副本？"确认弹窗（必须优先处理，否则会被背景的开启按钮截胡）
        if self.appear_then_click(self.I_UI_CONFIRM, interval=1.5):
            logger.info('Click stamina UI CONFIRM')
            return
        # 4. 开启/确认按钮
        if self.appear_then_click(self.I_PK_START_CONFIRM, interval=1.5) or \
                self.appear_then_click(self.I_PK_START_CONFIRM2, interval=1.5):
            return

    def _filter_island(self, appeared_islands: list[RuleImage]) -> list[RuleImage]:
        return appeared_islands

    def run_on_pk_main(self):
        """孔雀国主界面 执行策略选岛屿"""
        if self.appear(self.I_PK_BOSS_PREPARE) and \
                self.enter_battle(self.I_PK_BOSS_FIRE, boss_unlock=self.I_PK_BOSS_UNLOCK, boss_lock=self.I_PK_BOSS_LOCK):
            logger.info('Start boss battle')
            self.run_general_battle(battle_key='boss', exit_matcher=pages.page_peacock_kingdom)
            raise TaskEnd
        # 优先级：绽放之屿 > 鏖战之屿(战斗) > 混沌之屿 > 宁息商店 > 神秘之屿
        islands = [self.I_PK_LAND_BLOOM, self.I_PK_LAND_FIRE, self.I_PK_LAND_CHAOS, self.I_PK_LAND_STORE,
                 self.I_PK_LAND_MYSTERY]
        self.choose_and_enter_island(islands)

    def run_on_pk_challenge(self):
        """孔雀国挑战界面"""
        if self.enter_battle(self.I_PK_BATTLE_FIRE):
            self.run_general_battle(battle_key="normal", exit_matcher=pages.page_pk_main)

    def run_on_pk_store(self):
        """宁息商店"""
        logger.hr('shop land')
        if self.skill_roaring_thunder >= 1:
            logger.info('Skill level is enough, skip shopping')
            self.goto_page(pages.page_pk_main)
            return
        self.coin_num, buy_times = self.buy_skill(self.I_PK_STORE_SKILL_THUNDER, 300, self.O_COIN_NUM,
                                                  self.I_PK_STORE_REFRESH, self.O_PK_STORE_REFRESH_TIME, 1)
        self.skill_roaring_thunder += buy_times
        logger.info(f'Skill level: {self.skill_roaring_thunder}')
        self.goto_page(pages.page_pk_main)

    def exit_island(self, exit_rule=None, fallback_pos=(1180, 650)):
        """极速岛屿退出机制：点击离开/返回按钮，弹窗渲染后极速点击(760, 465)确定返回主界面"""
        logger.info(f'Fast exit island to main page (fallback={fallback_pos})')
        for _ in range(3):
            self.screenshot()
            if self.get_current_page() == pages.page_pk_main:
                break
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1.0):
                continue
            if exit_rule and self.appear_then_click(exit_rule, interval=1.0):
                time.sleep(0.6)
                self.device.click(x=760, y=465, control_name='confirm_leave_island')
                time.sleep(1.0)
                continue
            self.device.click(x=fallback_pos[0], y=fallback_pos[1], control_name='exit_island_fallback')
            time.sleep(0.6)
            self.device.click(x=760, y=465, control_name='confirm_leave_island')
            time.sleep(1.0)
        self.goto_page(pages.page_pk_main)

    def run_on_pk_mistery(self):
        """神秘之屿 进入后直接退出"""
        logger.hr('mistery land')
        logger.info('Enter mystery land, exit immediately per user request')
        self.exit_island(exit_rule=self.I_UI_BACK_BLUE, fallback_pos=(33, 58))

    def run_on_pk_bloom(self):
        """绽放之屿 挑选最左侧紧那罗挑战"""
        logger.hr('bloom land')
        # 1. 点击最左侧式神(紧那罗)展开详情面板
        self.device.click(x=200, y=400, control_name='bloom_kinnara')
        time.sleep(1.0)

        # 2. 点击右下角“学习”按钮发起挑战
        logger.info('Click bloom learn button at x=1150, y=640')
        self.device.click(x=1150, y=640, control_name='bloom_learn')
        time.sleep(1.0)

        # 3. 直接进入通用战斗逻辑，直到战斗结束返回主地图
        logger.info('Start Kinnara battle in Bloom land')
        self.run_general_battle(battle_key="normal", exit_matcher=pages.page_pk_main)

    def run_on_pk_chaos(self):
        """混沌之屿 宝箱/精英"""
        logger.hr('chaos land')
        is_box: bool = self.appear(self.I_PK_CHAOS_BOX)
        if is_box:
            logger.info('Do not get box, fast exit chaos land')
            self.exit_island(exit_rule=self.I_PK_CHAOS_EXIT, fallback_pos=(1181, 655))
            return
        self.ui_click(self.C_NPC_FIRE_CENTER, self.I_PK_BATTLE_FIRE, interval=0.8)
        if self.enter_battle(self.I_PK_BATTLE_FIRE):
            logger.info('Start elite battle')
            self.run_general_battle(battle_key="elite", exit_matcher=pages.page_pk_main)

    def run_on_pk_battle(self):
        """鏖战之屿 普通怪"""
        logger.hr('fire land')
        self.ui_click(self.C_NPC_FIRE_RIGHT, self.I_PK_BATTLE_FIRE, interval=0.8)
        if self.enter_battle(self.I_PK_BATTLE_FIRE):
            logger.info('Start normal battle')
            self.run_general_battle(battle_key="normal", exit_matcher=pages.page_pk_main)
