# This Python file uses the following encoding: utf-8
from __future__ import annotations

import random
import time
from datetime import datetime
from functools import cached_property
from typing import Callable, Optional

from module.atom.click import RuleClick
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr
from module.base.protect import random_sleep
from module.logger import logger
from tasks.Component.BaseActivity.assets import BaseActivityAssets
from tasks.Component.BaseActivity.exceptions import LimitCountOut, LimitTimeOut, TicketsNotEnough
from tasks.Component.BuyWindow.buy_window import BuyWindow
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.RightActivity import RightActivity
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.UsedTicketsCount.used_tickets_count import UsedTicketsCount
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import Page, page_main


class BaseActivity(GeneralBattle, RightActivity, SwitchSoul, UsedTicketsCount, BuyWindow, BaseActivityAssets):
    """通用活动爬塔基类组件。

    设计职责：
    1. 连通独立原子组件：
       - RightActivity（右侧活动侧边栏自检、翻页切换与智能寻点独立组件）
       - BuyWindow（购买弹窗识别与安全关闭独立组件，门票耗尽直切）
       - UsedTicketsCount（已使用门票计数独立组件，精准记录应用运行使用次数）
       - SwitchSoul（御魂切换独立组件）
       - GeneralBattle（通用战斗独立组件）
       - GameUi / Navigator（界面导航独立组件）
    2. 提供通用爬塔自动化流水线：
       - 多模式按序轮转 (pass -> ap -> ap100 -> boss)
       - 挑战前余票校验与应用限额检查
       - 智能阵容锁定与御魂自适应切换
       - 战斗进入与结果处理闭环
       - 超时、限额与防卡屏死锁熔断保护
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_climb_type: str = 'pass'
        self._switch_souled_map: dict[str, bool] = {}

    @property
    def current_climb_type(self) -> str:
        """当前正在执行的爬塔模式类型。"""
        return getattr(self, '_current_climb_type', 'pass')

    @current_climb_type.setter
    def current_climb_type(self, value: str):
        self._current_climb_type = str(value).strip()

    def before_run(self):
        """活动执行前的预处理钩子，子类可覆写扩展。"""
        pass

    @staticmethod
    def get_climb_type_display_name(climb_type: str) -> str:
        """将爬塔英文标识转换为友好的中文展示名称。"""
        mapping = {
            'pass': '门票爬塔',
            'ap': '体力爬塔',
            'ap100': '100体爬塔',
            'boss': '首领挑战',
        }
        return mapping.get(str(climb_type).lower(), str(climb_type))

    def get_climb_target_limit(self, climb_type: str) -> int:
        """获取指定爬塔类型的配置运行限额。"""
        conf_obj = getattr(self.config.model, 'activity_shikigami', None)
        if conf_obj and hasattr(conf_obj, 'general_climb'):
            return getattr(conf_obj.general_climb, f'{climb_type}_limit', 0)
        return 0

    def check_activity_timeout(self):
        """检查全局活动是否达到总运行时间限制。"""
        conf_obj = getattr(self.config.model, 'activity_shikigami', None)
        if not conf_obj or not hasattr(conf_obj, 'general_climb'):
            return
        limit_time_v = conf_obj.general_climb.limit_time_v
        if datetime.now() - self.start_time >= limit_time_v:
            logger.info(f"活动爬塔总运行时间达到上限 ({limit_time_v})")
            raise LimitTimeOut

    def check_activity_limit(self, climb_type: str):
        """检查当前模式的应用运行使用次数是否达到配置限额。"""
        target_limit = self.get_climb_target_limit(climb_type)
        if self.is_app_limit_reached(climb_type, target_limit):
            raise LimitCountOut

    def switch_soul_for_climb(self, climb_type: str, enter_button: RuleImage, check_image: RuleImage):
        """为当前爬塔模式执行御魂切换（同一模式单次会话只切换一次）。

        Args:
            climb_type: 爬塔类型
            enter_button: 进入阵容/记录界面的按钮规则
            check_image: 阵容记录界面识别标志
        """
        if self._switch_souled_map.get(climb_type, False):
            return

        conf_obj = getattr(self.config.model, 'activity_shikigami', None)
        if not conf_obj or not hasattr(conf_obj, 'switch_soul_config'):
            return

        conf = conf_obj.switch_soul_config
        enable_switch = getattr(conf, f"enable_switch_{climb_type}", False)
        enable_by_name = getattr(conf, f"enable_switch_{climb_type}_by_name", False)
        if not enable_switch and not enable_by_name:
            self._switch_souled_map[climb_type] = True
            return

        climb_name = self.get_climb_type_display_name(climb_type)
        logger.hr(f'开始切换御魂: {climb_name}', 2)
        conf.validate_switch_soul()
        self.ui_click(enter_button, stop=check_image, interval=1.2)
        if enable_by_name:
            name_val = getattr(conf, f"{climb_type}_group_team_name", "")
            group, team = name_val.split(",")
            self.run_switch_soul_by_name(group.strip(), team.strip())
        elif enable_switch:
            group_team = getattr(conf, f"{climb_type}_group_team")
            self.run_switch_soul(group_team)

        self._switch_souled_map[climb_type] = True

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """阵容锁定/解锁处理，子类根据各模式实际 UI 资产覆写或注入。"""
        pass

    def enter_battle_generic(
        self,
        fire_ocr: RuleOcr,
        confirm_image: RuleImage,
        confirm_small_image: RuleImage,
        no_tickets_image: Optional[RuleImage] = None,
        max_clicks: int = 5,
    ) -> bool:
        """通用的点击挑战进入战斗流程，具备超时与盲点熔断防护。

        Args:
            fire_ocr: 挑战 OCR 规则
            confirm_image: 大确认按钮规则
            confirm_small_image: 小确认按钮规则
            no_tickets_image: 门票不足/红色弹窗标志
            max_clicks: 最大连续点击挑战尝试次数

        Returns:
            bool: True 表示成功进入战斗，若次数耗尽或弹出无票弹窗则抛出 TicketsNotEnough
        """
        click_times = 0
        while True:
            self.screenshot()
            if self.is_in_battle(False):
                return True

            # 门票不足购买弹窗前置检测：若已弹出购买弹窗，绝不重试，直接关闭并切换
            if self.is_ticket_buy_window():
                self.handle_ticket_buy_window(self.current_climb_type)

            if click_times >= max_clicks:
                logger.warning(f"[{self.current_climb_type}] 点击挑战达到上限 [{max_clicks}] 次，可能无法进入战斗")
                raise TicketsNotEnough

            if no_tickets_image and self.appear(no_tickets_image, interval=1):
                logger.warning(f"[{self.current_climb_type}] 出现关闭/资源不足标志，判定门票耗尽")
                raise TicketsNotEnough

            if self.appear_then_click(confirm_small_image, interval=1) or \
               self.appear_then_click(confirm_image, interval=1):
                time.sleep(0.8)
                continue

            if self.ocr_appear_click(fire_ocr, interval=1.5):
                self.device.click_record_clear()
                click_times += 1
                if click_times == 1:
                    logger.info(f"[{self.current_climb_type}] 点击挑战，等待进入战斗...")
                else:
                    logger.warning(
                        f"[{self.current_climb_type}] 未检测到进入战斗，第 {click_times} 次重试点击挑战 (剩余尝试次数 [{max_clicks - click_times}])"
                    )

                # 进场过渡等待：轮询检测战斗是否就绪（最多等待 3s，每 0.5s 检查一次）
                for _ in range(6):
                    time.sleep(0.5)
                    self.screenshot()
                    if self.is_in_battle(False):
                        return True
                    # 优先检测是否由于门票不足弹出购买弹窗，一旦发现立刻阻断重试并直接切换模式
                    if self.is_ticket_buy_window():
                        self.handle_ticket_buy_window(self.current_climb_type)
                    if self.appear_then_click(confirm_small_image, interval=0.5) or \
                       self.appear_then_click(confirm_image, interval=0.5):
                        continue
                    if no_tickets_image and self.appear(no_tickets_image, interval=0.5):
                        logger.warning(f"[{self.current_climb_type}] 出现关闭/资源不足标志，判定门票耗尽")
                        raise TicketsNotEnough

                continue

    def execute_climb_round(
        self,
        climb_type: str,
        ticket_ocr: Optional[RuleOcr],
        battle_conf: GeneralBattleConfig,
        fire_ocr: RuleOcr,
        confirm_image: RuleImage,
        confirm_small_image: RuleImage,
        no_tickets_image: Optional[RuleImage] = None,
        soul_records_button: Optional[RuleImage] = None,
        soul_records_check: Optional[RuleImage] = None,
        random_sleep_enabled: bool = False,
    ):
        """执行单轮爬塔流程：余票检查 -> 换御魂 -> 点击进入 -> 通用战斗 -> 应用门票计数递增。"""
        # 0. 防卡屏检测：如果意外处于购买弹窗中，立即关闭并切换模式
        if self.is_ticket_buy_window():
            self.handle_ticket_buy_window(climb_type)

        # 1. 检查游戏内门票是否足够
        if not self.check_game_tickets_available(climb_type, ticket_ocr):
            logger.warning(f"[{climb_type}] 游戏内门票不足，退出该模式")
            raise TicketsNotEnough

        # 2. 检查应用运行使用次数是否已达限额
        target_limit = self.get_climb_target_limit(climb_type)
        if self.is_app_limit_reached(climb_type, target_limit):
            raise LimitCountOut

        # 3. 换御魂
        if soul_records_button and soul_records_check:
            self.switch_soul_for_climb(climb_type, soul_records_button, soul_records_check)

        # 4. 拟人化随机等待
        if random_sleep_enabled:
            random_sleep(probability=0.2)

        # 5. 点击挑战进入战斗
        if self.enter_battle_generic(
            fire_ocr=fire_ocr,
            confirm_image=confirm_image,
            confirm_small_image=confirm_small_image,
            no_tickets_image=no_tickets_image,
        ):
            # 6. 执行通用战斗并处理结算
            self.run_general_battle(battle_conf, battle_key=f"act_{climb_type}")
            # 7. 战斗完成，应用实际使用门票次数精确 +1
            self.record_ticket_used(climb_type, count=1, target_limit=target_limit)
            # 8. 校验是否达到目标限额
            if self.is_app_limit_reached(climb_type, target_limit):
                raise LimitCountOut