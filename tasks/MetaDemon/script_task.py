# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from functools import cached_property
from time import sleep

from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import (
    BattleAction,
    BattleContext,
    GeneralBattle,
)
from tasks.Component.RightActivity.right_activity import RightActivity
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.matcher import any_of
from tasks.GameUi.page import page_battle_result, page_main, page_shikigami_records
from tasks.MetaDemon.assets import MetaDemonAssets
from tasks.MetaDemon.config import Strategy


class Star56(GameUi, MetaDemonAssets):

    @cached_property
    def cached_strategies(self) -> dict[str, list[int]]:
        return Strategy.parse_all(self.config.meta_demon.md_strategies)

    @cached_property
    def cached_default_group_team(self) -> list[int]:
        default_cfg = self.config.meta_demon.md_default_strategy
        return (
            Strategy.parse_group_team(default_cfg.md_preset_group_team_default_1)
            + Strategy.parse_group_team(default_cfg.md_preset_group_team_default_2)
        )

    def is_star56(self) -> bool:
        return not self.appear(self.I_STAR56_POS_1)

    def hp_threshold_low(self, image=None) -> bool:
        """血量小于阈值返回 True。"""
        return self.appear(self.I_STAR56_HP_THRESHOLD_F) and not self.appear(self.I_STAR56_HP_THRESHOLD_T)

    @classmethod
    def strategy2group_team(cls, strategies: dict[str, list[int]], detect_name: str) -> list[int] | None:
        """优先精确匹配，其次容忍 1 个字符误差。"""
        if not detect_name:
            return None
        for max_diff in range(2):
            for key_name, group_team in strategies.items():
                if len(key_name) != len(detect_name):
                    continue
                diff_count = sum(1 for c1, c2 in zip(key_name, detect_name) if c1 != c2)
                if diff_count <= max_diff < len(detect_name):
                    return group_team
        return None

    def get_group_team(self, detect_name: str) -> list[int]:
        matched = self.strategy2group_team(self.cached_strategies, detect_name)
        return matched if matched else self.cached_default_group_team


class ScriptTask(RightActivity, GeneralBattle, SwitchSoul, Star56):

    def _register_custom_pages(self) -> None:
        result_page = self.navigator.resolve_page(page_battle_result)
        result_page.recognizer = any_of(
            self.I_MD_WIN,
            self.I_MD_BATTLE_FAILURE,
            result_page.recognizer,
        )

    def _handle_in_battle(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        if self.is_in_real_battle(False):
            self.boss_mark()
        return super()._handle_in_battle(context, config)

    def _handle_result(self, context: BattleContext, config: GeneralBattleConfig) -> BattleAction:
        context.reward_no_battle_ts = None
        if self.appear(self.I_MD_WIN):
            logger.info('MetaDemon battle win')
            context.is_win = True
            if context.last_page != page_battle_result:
                self.device.click_record_clear()
            self.click(self.I_MD_WIN, interval=0.8)
            return BattleAction.CONTINUE
        if self.appear(self.I_MD_BATTLE_FAILURE):
            logger.warning('MetaDemon battle failed')
            context.is_win = False
            if context.last_page != page_battle_result:
                self.device.click_record_clear()
            self.click(self.I_MD_BATTLE_FAILURE, interval=0.8)
            return BattleAction.CONTINUE
        return super()._handle_result(context, config)

    def run(self):
        logger.hr('超鬼王活动')
        switch_cfg = self.config.meta_demon.switch_soul
        if switch_cfg.enable:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul(switch_cfg.switch_group_team)

        if switch_cfg.enable_switch_by_name:
            self.goto_page(page_shikigami_records)
            self.run_switch_soul_by_name(switch_cfg.group_name, switch_cfg.team_name)

        self.enter(self.I_RIGHT_ENTER)
        enter_timer = Timer(30).start()
        entered = False
        while not enter_timer.reached():
            self.screenshot()
            if self.appear(self.I_FIND_DEMON) or self.appear(self.I_BATTLE_DEMON):
                entered = True
                break
            if self.ui_reward_appear_click():
                continue
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1.5):
                continue
            if self.appear_then_click(self.I_ENTER_ENSURE, interval=1):
                continue
            if self.appear_then_click(self.I_ENTER2, interval=1):
                continue

        if not entered:
            logger.warning('MetaDemon enter activity timeout, returning to main')
            self.goto_page(page_main)
            self.set_next_run(task='MetaDemon', success=False)
            raise TaskEnd

        md_cfg = self.config.meta_demon.meta_demon_config
        if md_cfg.meta_crafting_card:
            self.crafting()

        boss_timer = Timer(50).start()
        first_battle_for_easy_boss = True
        while True:
            battle_processing = False
            is_hard_boss = False  # 五星或者六星
            self.screenshot()

            if boss_timer.reached():
                logger.info('MetaDemon wait timeout, exit')
                break
            if not (self.appear(self.I_FIND_DEMON) or self.appear(self.I_BATTLE_DEMON)):
                continue

            # 疲劳达到阈值时优先召唤鬼王（开关控制，判定先于协战鬼王）
            if md_cfg.md_fatigue_summon_first:
                fatigue = self.current_exhaustion()
                if 61 <= fatigue <= 100 and self.appear(self.I_BOSS_EMPTY):
                    logger.info('Fatigue >= 61, summon demon first')
                    if self.find_demon():
                        boss_timer.reset()
                        continue

            # 1. 先检查自己是否有未击败/已公开的鬼王
            if (
                not self.appear(self.I_BOSS_EMPTY)
                and (self.appear(self.I_BOSS_CONVENE) or self.appear(self.I_BOOS_PUBLIC))
            ):
                logger.info('Try to battle boss from self')
                self.click(self.I_BOSS_EMPTY, interval=1.5)
                battle_processing = True
                if self.is_star56():
                    is_hard_boss = True

            # 2. 检查他人共享鬼王
            if not battle_processing and md_cfg.auto_shared_boss:
                if not self.appear(self.I_BOSS_EMPTY_1) and self.ocr_appear(self.O_BOSS_EMPTY_1):
                    logger.info('Try to battle boss 1 from others')
                    self.click(self.I_BOSS_EMPTY_1, interval=1.5)
                    self.ui_click(self.I_BOSS_EMPTY_1, stop=self.I_BATTLE_DEMON, interval=1.5, timeout=8)
                    battle_processing = True
                    is_hard_boss = True
                elif not self.appear(self.I_BOSS_EMPTY_2):
                    logger.info('Try to battle boss 2 from others')
                    self.click(self.I_BOSS_EMPTY_2, interval=1.5)
                    self.ui_click(self.I_BOSS_EMPTY_1, stop=self.I_BATTLE_DEMON, interval=1.5, timeout=8)
                    battle_processing = True
                    is_hard_boss = True

            # 3. 检查疲劳值
            current_exhaustion = self.current_exhaustion()
            if current_exhaustion > 100:
                if md_cfg.auto_tea:
                    logger.info('Exhaustion is full, buy tea')
                    boss_timer.reset()
                    self.buy_tea()
                else:
                    logger.info('Exhaustion is full, exit')
                    break

            # 4. 5/6 星策略阵容匹配与普通鬼王默认阵容
            target_group_team: list[int | None] = [None, None]
            if is_hard_boss:
                logger.info('Hard boss')
                if md_cfg.md_use_strategy:
                    detect_full_name = self.O_MD_FULL_NAME.ocr_single(self.device.image) or ''
                    logger.info(f'detect_full_name: {detect_full_name}')
                    group_team = self.get_group_team(detect_full_name)
                    if self.hp_threshold_low(self.device.image):
                        logger.info('Hp threshold low')
                        target_group_team = group_team[2:4]
                    else:
                        logger.info('Hp threshold high')
                        target_group_team = group_team[0:2]
            elif md_cfg.md_use_strategy and first_battle_for_easy_boss:
                logger.info('Normal boss first battle use default group team')
                target_group_team = self.cached_default_group_team[0:2]

            if battle_processing and self.appear(self.I_BATTLE_DEMON):
                logger.info(f'preset group team: {target_group_team}')
                self.battle_boss(target_group_team[0], target_group_team[1])
                if first_battle_for_easy_boss:
                    first_battle_for_easy_boss = False
                if is_hard_boss:
                    first_battle_for_easy_boss = True
                boss_timer.reset()
                continue

            # 5. 疲劳未满且当前无鬼王时主动召唤
            if current_exhaustion < 90 and self.find_demon():
                boss_timer.reset()
                continue

        # 退出活动并返回庭院主页
        logger.hr('退出超鬼王', 2)
        self.goto_page(page_main)
        self.set_next_run(task='MetaDemon', success=True)
        raise TaskEnd

    def current_exhaustion(self) -> int:
        self.screenshot()
        cu, _, _ = self.O_MD_EXHAUSTION.ocr(self.device.image)
        if isinstance(cu, int):
            return cu
        return int(cu) if isinstance(cu, str) and cu.isdigit() else 0

    def buy_tea(self):
        pass

    def crafting(self):
        """把一星门票合成为二星。"""
        logger.hr('合成一星鬼王门票', 2)
        if not self.ui_click(self.I_CRAFTING_1, self.I_CRAFTING_START, interval=1.5, timeout=8):
            logger.warning('Open crafting dialog timeout, skip crafting')
            return
        timer = Timer(3).start()
        total_timer = Timer(30).start()
        count = 0
        while not total_timer.reached():
            self.screenshot()
            if self.ui_reward_appear_click():
                timer.reset()
                continue
            if timer.reached() or count > 3:
                break
            if not self.ocr_appear(self.O_CRAFTING_CARD_1):
                break
            if self.appear(self.I_CRAFTING_EMPTY) or self.appear(self.I_CRAFTING_EMPTY_NEW):
                if self.appear_then_click(self.I_CRAFTING_CARD_STAR_1, interval=1):
                    continue
            else:
                self.appear_then_click(self.I_CRAFTING_START, interval=3)
                count += 1
                timer.reset()
                continue
        logger.info('Finish star crafting')
        self.ui_click_until_disappear(self.I_UI_BACK_RED, interval=1, timeout=8)
        sleep(0.5)

    def find_demon(self) -> bool:
        """召唤超鬼王，若召唤到 5/6 星则推送通知。"""
        logger.hr('召唤超鬼王', 2)
        find_timer = Timer(20).start()
        found = False
        while not find_timer.reached():
            self.screenshot()
            if self.appear(self.I_BATTLE_DEMON) and not self.appear(self.I_BOSS_EMPTY):
                found = True
                break
            if self.appear_then_click(self.I_FIND_DEMON, interval=3.5):
                continue
        if not found:
            logger.warning('Find demon timeout')
            return False

        self.screenshot()
        if self.is_star56():
            logger.info('Star 5 or 6 demon found')
            detect_full_name = ''
            ocr_timer = Timer(5).start()
            while not ocr_timer.reached():
                sleep(0.4)
                self.screenshot()
                detect_full_name = self.O_MD_FULL_NAME.ocr_single(self.device.image) or ''
                if detect_full_name:
                    break
            logger.info(f'召唤到高星鬼王: {detect_full_name or "未知"}')
            self.config.notifier.push(
                content=f'召唤到高星鬼王: {detect_full_name or "未知"}',
                title='超鬼王',
            )
        return True

    def battle_boss(self, group: int | None = None, team: int | None = None) -> bool:
        """使用通用战斗状态机挑战当前超鬼王。"""
        logger.hr('挑战超鬼王', 2)
        # 进战前确保解除队伍锁定，避免无法切换策略预设
        self.ui_click(self.I_TEAM_LOCK, self.I_TEAM_UNLOCK, interval=1.5, timeout=5)
        self.ui_click_until_disappear(self.I_BATTLE_DEMON, interval=1.8, timeout=10)

        battle_config = GeneralBattleConfig()
        battle_config.lock_team_enable = False
        battle_key = 'metademon_default'
        if group is not None and team is not None:
            battle_config.preset_enable = True
            battle_config.preset_group = group
            battle_config.preset_team = team
            # 每只 5/6 星推荐阵容不同，用唯一 battle_key 触发每场切预设
            battle_key = f'metademon_{group}_{team}_{self.current_count}'

        self.boss_mark_reset()
        win = self.run_general_battle(
            config=battle_config,
            battle_key=battle_key,
            exit_matcher=any_of(self.I_CRAFTING_1, self.I_FIND_DEMON, self.I_BATTLE_DEMON),
        )
        logger.info(f'Battle boss win: {win}, current count: {self.current_count}')
        return win


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.run()
