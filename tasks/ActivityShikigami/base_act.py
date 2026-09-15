# This Python file uses the following encoding: utf-8
from __future__ import annotations

import time
from datetime import datetime
from functools import cached_property
from typing import Callable, Optional, cast

from module.atom.click import RuleClick
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr
from module.exception import TaskEnd
from module.logger import logger
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.config import ActivityShikigami, GeneralBattleConfig
import tasks.ActivityShikigami.page as pages
from tasks.Component.BaseActivity.base_activity import (
    BaseActivity,
    LimitCountOut,
    LimitTimeOut,
    TicketsNotEnough,
)


class BaseAct(BaseActivity, ActivityShikigamiAssets):
    """活动爬塔业务基类。

    继承通用活动组件 BaseActivity 与特定活动资产 ActivityShikigamiAssets，
    通过独立组件 UsedTicketsCount 实现应用运行使用次数的精准追踪与余票校验。
    """

    @cached_property
    def conf(self) -> ActivityShikigami:
        """获取当期活动爬塔配置模型。"""
        return self.config.model.activity_shikigami

    @property
    def climb_type(self) -> str:
        """当前正在执行的爬塔类型。"""
        return self.current_climb_type

    def get_climb_ticket_ocr(self, climb_type: str) -> Optional[RuleOcr]:
        """获取各爬塔类型对应的界面门票/体力 OCR 规则。"""
        match climb_type:
            case 'pass':
                return self.O_REMAIN_PASS
            case 'ap':
                return self.O_REMAIN_AP
            case 'ap100':
                return self.O_REMAIN_AP100
            case 'boss':
                return self.O_REMAIN_BOSS
            case _:
                return None

    def before_run(self):
        """活动执行前的页面钩子注册。"""
        super().before_run()
        page_battle_result = self.navigator.resolve_page(pages.page_battle_result)
        if page_battle_result and page_battle_result.recognizer:
            pages.page_battle_result = page_battle_result
            pages.page_battle_result.recognizer = pages.any_of(self.I_UI_BACK_RED, page_battle_result.recognizer)

    @property
    def act_page_handle_dict(self) -> dict[pages.Page, Callable]:
        """活动页面与对应处理器的映射字典。"""
        return {
            pages.page_act_pass: self._run_pass,
            pages.page_act_ap: self._run_ap,
            pages.page_act_ap100: self._run_ap100,
            pages.page_act_boss: self._run_boss,
            pages.page_battle_prepare: lambda: self.run_general_battle(
                getattr(self.conf, f'{self.climb_type}_battle_conf'),
                battle_key=f'act_{self.climb_type}'
            ),
            pages.page_battle: lambda: self.run_general_battle(
                getattr(self.conf, f'{self.climb_type}_battle_conf'),
                battle_key=f'act_{self.climb_type}'
            ),
            pages.page_reward: lambda: self.click(
                cast(RuleClick, pages.random_click(ltrb=(False, False, True, False))),
                interval=1.5
            ),
        }

    def run(self):
        """爬塔主执行流程：按配置顺序遍历各模式，连通独立组件自动执行。"""
        self.before_run()
        sequence = self.conf.general_climb.run_sequence_v
        logger.info(f"活动爬塔启用的模式顺序: {sequence}")

        try:
            for climb_type in sequence:
                self.current_climb_type = climb_type
                target_limit = self.get_climb_target_limit(climb_type)
                if target_limit <= 0:
                    logger.info(f"[{climb_type}] 配置限额为 {target_limit}，跳过此模式")
                    continue

                dest_page: Optional[pages.Page] = getattr(pages, f'page_act_{climb_type}', None)
                if not dest_page:
                    logger.warning(f"[{climb_type}] 目标页面未定义或不支持，跳过")
                    continue

                climb_name = self.get_climb_type_display_name(climb_type)
                logger.hr(f"开始执行爬塔模式: {climb_name} (目标限额: {target_limit})", 1)
                self.goto_page(dest_page)

                cur_battle_conf = getattr(self.conf, f'{climb_type}_battle_conf', None)
                if cur_battle_conf is None:
                    logger.warning(f"[{climb_type}] 未配置战斗参数，跳过")
                    continue

                self.lock_team(cur_battle_conf)
                unknown_page_count = 0

                try:
                    while True:
                        self.screenshot()
                        self.check_activity_timeout()
                        self.check_activity_limit(climb_type)

                        current_page = self.get_current_page()
                        if current_page is None:
                            unknown_page_count += 1
                            if unknown_page_count >= 30:
                                logger.warning(f"[{climb_type}] 连续处于未知页面，尝试重回目标页面")
                                self.goto_page(dest_page)
                                unknown_page_count = 0
                            time.sleep(0.5)
                            continue

                        unknown_page_count = 0
                        handle = self.act_page_handle_dict.get(current_page, None)
                        if handle is None:
                            self.goto_page(dest_page)
                            continue

                        handle()

                except LimitCountOut:
                    logger.info(
                        f"[{climb_type}] 应用已运行 {self.get_app_used_count(climb_type)} 次，"
                        f"达到配置目标上限 ({target_limit})，切换下一模式"
                    )
                    continue
                except TicketsNotEnough:
                    logger.info(f"[{climb_type}] 门票不足或游戏内无剩余次数，切换下一模式")
                    continue

        except LimitTimeOut:
            logger.info("活动爬塔总运行时间超时，准备退出")

        # 所有模式执行完毕后返回庭院
        self.goto_page(pages.page_main)
        if self.conf.general_climb.active_souls_clean:
            self.set_next_run(task='SoulsTidy', success=False, finish=False, target=datetime.now())
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd

    def _run_pass(self):
        self._run_common()

    def _run_ap(self):
        self._run_common()

    def _run_ap100(self):
        self._run_common()

    def _run_boss(self):
        self._run_common()

    def _run_common(self):
        """执行通用爬塔单轮：通过 BaseActivity 连通 UsedTicketsCount、SwitchSoul 与 GeneralBattle。"""
        cur_battle_conf = getattr(self.conf, f'{self.climb_type}_battle_conf')
        ticket_ocr = self.get_climb_ticket_ocr(self.climb_type)

        self.execute_climb_round(
            climb_type=self.climb_type,
            ticket_ocr=ticket_ocr,
            battle_conf=cur_battle_conf,
            fire_ocr=self.O_FIRE,
            confirm_image=self.I_UI_CONFIRM,
            confirm_small_image=self.I_UI_CONFIRM_SAMLL,
            no_tickets_image=self.I_UI_BACK_RED,
            soul_records_button=self.I_BATTLE_MAIN_TO_RECORDS,
            soul_records_check=self.I_CHECK_RECORDS,
            random_sleep_enabled=self.conf.general_climb.random_sleep,
        )

    def check_tickets_enough(self) -> bool:
        """检查当前爬塔门票是否足够（代理至独立门票组件）。"""
        ticket_ocr = self.get_climb_ticket_ocr(self.climb_type)
        return self.check_game_tickets_available(self.climb_type, ticket_ocr)

    def enter_battle(self) -> bool:
        """点击挑战进入战斗流程（代理至通用活动组件）。"""
        return self.enter_battle_generic(
            fire_ocr=self.O_FIRE,
            confirm_image=self.I_UI_CONFIRM,
            confirm_small_image=self.I_UI_CONFIRM_SAMLL,
            no_tickets_image=self.I_UI_BACK_RED,
        )

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """根据配置判断当前爬塔类型是否锁定阵容，并执行锁定或解锁。"""
        enable = battle_conf.lock_team_enable
        if enable:
            logger.info(f'Lock {self.climb_type} team')
            match self.climb_type:
                case 'ap' | 'boss':
                    self.ui_click(self.I_AP_UNLOCK, stop=self.I_AP_LOCK, interval=1.5)
                case _:
                    self.ui_click(self.I_UNLOCK, stop=self.I_LOCK, interval=1.5)
            return

        logger.info(f'Unlock {self.climb_type} team')
        match self.climb_type:
            case 'ap' | 'boss':
                self.ui_click(self.I_AP_LOCK, stop=self.I_AP_UNLOCK, interval=1.5)
            case _:
                self.ui_click(self.I_LOCK, stop=self.I_UNLOCK, interval=1.5)