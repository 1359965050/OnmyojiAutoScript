import time

from datetime import datetime, timedelta
import random
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from cached_property import cached_property

from module.atom.image import RuleImage
from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger

from tasks.base_task import BaseTask
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.config import GeneralBattleConfig, ActivityShikigami
from tasks.ActivityShikigami.descriptor import EventDescriptor
from tasks.ActivityShikigami.page import create_event_pages
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GlobalGame.assets import GlobalGameAssets
import tasks.ActivityShikigami.page as pages
from typing import Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from tasks.GameUi.page_definition import Page


class LimitTimeOut(Exception):
    pass


class LimitCountOut(Exception):
    pass


class TicketsNotEnough(Exception):
    pass


class StateMachine(BaseTask):
    run_idx: int = 0  # 当前爬塔类型
    _count_map = None
    _pre_tickets_map = None
    switch_souled: dict[str, bool] = {}

    @cached_property
    def conf(self) -> ActivityShikigami:
        return self.config.model.activity_shikigami

    @property
    def climb_type(self) -> str:
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            return self.conf.general_climb.run_sequence_v[-1]
        return self.conf.general_climb.run_sequence_v[self.run_idx]

    @property
    def config_label(self) -> str:
        """返回用于获取战斗配置和御魂切换配置的 label，ap 与 pass 共用一套配置"""
        return 'pass' if self.climb_type == 'ap' else self.climb_type

    @property
    def count_map(self) -> dict[str, int]:
        """
        :return: key: climb type, value: run count
        """
        if not getattr(self, "_count_map", None):
            self._count_map = {climb_type: 0 for climb_type in self.conf.general_climb.run_sequence_v}
        return self._count_map

    @property
    def pre_tickets_map(self) -> dict[str, int]:
        """
        :return: key: climb type, value: pre tickets num
        """
        if not getattr(self, "_pre_tickets_map", None):
            self._pre_tickets_map = {climb_type: -1 for climb_type in self.conf.general_climb.run_sequence_v}
        return self._pre_tickets_map

    def update_status(self):
        """
        更新全局状态
        """

        def get_count() -> int:
            return self.count_map[self.climb_type]

        def get_limit() -> int:
            limit = getattr(self.conf.general_climb, f'{self.climb_type}_limit', 0)
            return 0 if not limit else limit

        # 超过运行时间
        if datetime.now() - self.start_time >= self.conf.general_climb.limit_time_v:
            logger.info(f"Climb type {self.climb_type} time out")
            raise LimitTimeOut
        # 次数达到限制
        if get_count() >= get_limit():
            logger.info(f"Climb type {self.climb_type} count limit reached")
            raise LimitCountOut

    def switch_next(self):
        """
        切换下一种爬塔类型
        :return: True 切换成功 or False
        """
        self.run_idx += 1
        if self.run_idx >= len(self.conf.general_climb.run_sequence_v):
            logger.info('All climbing activities have been completed')
            return False
        # 切换爬塔类型了, 恢复所有状态
        self.current_count = 0
        logger.hr(f'Climb switch to {self.climb_type}', 2)
        return True


class BaseAct(StateMachine, GameUi, GeneralBattle, SwitchSoul, ActivityShikigamiAssets):
    """爬塔活动基类"""

    # 注册的活动描述器字典（子类/外部在初始化前注册）
    event_descriptors: dict[str, EventDescriptor] = {}
    descriptor: Optional[EventDescriptor] = None
    pages: dict = {}
    default_event_id: str = 'normal'  # 子类可覆盖，指定默认使用的描述器ID

    def before_run(self):
        """加载描述器、创建页面并注册到导航器"""
        if self.descriptor is None:
            event_id = getattr(self.conf.general_climb, 'event_id', None) or self.default_event_id
            self.descriptor = self.event_descriptors.get(event_id)
        if self.descriptor and self.descriptor.entry_button:
            self.pages = create_event_pages(self.descriptor)
            nav = self.navigator

            # 1. 注册所有活动页面到导航器——获取会话副本
            p_act = nav.add_page(self.pages['page_act'])
            p_act_ap = nav.add_page(self.pages['page_act_ap'])
            p_act_pass = nav.add_page(self.pages['page_act_pass'])
            p_act_boss = nav.add_page(self.pages['page_act_boss'])

            # 2. 连接 page_main ↔ page_act（在会话副本上操作，保证导航器可见）
            from tasks.GameUi.page import page_main as gm_page_main
            session_main = nav.resolve_page(gm_page_main)
            session_main.connect(p_act, self.descriptor.entry_button, key="page_main->page_act")
            p_act.connect(session_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act->page_main")

            # 3. 连接活动主页面 ↔ 子模式页面（会话副本）
            p_act_ap.connect(p_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_ap->page_act")
            p_act_pass.connect(p_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_pass->page_act")
            p_act_boss.connect(p_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_boss->page_act")
            p_act.connect(p_act_ap, ActivityShikigamiAssets.I_TO_BATTLE_AP, key="page_act->page_act_ap")
            p_act.connect(p_act_boss, ActivityShikigamiAssets.I_TO_BATTLE_BOSS, key="page_act->page_act_boss")

            # 4. 调用描述器的额外页面注册钩子
            self.descriptor.setup_pages(self)

    @property
    def act_page_handle_dict(self) -> "dict[str, Callable]":
        """活动页面key和处理器的映射"""
        return {
            'page_act_pass': self._run_pass,
            'page_act_ap': self._run_ap,
            'page_act_boss': self._run_boss,
        }

    def run(self):
        self.before_run()
        for climb_type in self.conf.general_climb.run_sequence_v:
            logger.hr(f'Start run {self.climb_type}', 1)
            dest_page: "Optional[Page]" = self.pages.get(f'page_act_{climb_type}')
            if not dest_page:
                logger.warning(f'{climb_type} page is not supported')
                continue
            self.goto_page(dest_page)
            config_label = 'pass' if climb_type == 'ap' else climb_type
            cur_battle_conf = getattr(self.conf, f'{config_label}_battle_conf')
            if cur_battle_conf is None:
                logger.warning(f'{climb_type} battle config is not supported')
                continue
            self.lock_team(cur_battle_conf)
            try:
                while True:
                    self.screenshot()
                    self.update_status()
                    current_page = self.get_current_page()
                    if current_page is None:
                        time.sleep(0.5)
                        continue
                    handle = self.act_page_handle_dict.get(current_page.key, None)
                    if handle is None:
                        self.goto_page(dest_page)
                        continue
                    handle()
            except (LimitCountOut, LimitTimeOut, TicketsNotEnough):
                pass
            finally:
                self.switch_next()
        self.goto_page(self.pages.get('page_main', pages.page_main))
        self.set_next_run(task="ActivityShikigami", success=True)
        raise TaskEnd

    def _run_pass(self):
        self._run_common()

    def _run_ap(self):
        self._run_common()

    def _run_boss(self):
        self._run_common()

    def _run_common(self):
        if not self.check_tickets_enough():
            logger.warning(f'No tickets left, wait for next time')
            raise TicketsNotEnough
        self.switch_soul(self.I_BATTLE_MAIN_TO_RECORDS)
        if self.enter_battle():
            self.count_map[self.climb_type] += 1
            self.run_general_battle(getattr(self.conf, f'{self.config_label}_battle_conf'))

    def enter_battle(self):
        click_times, max_times = 0, random.randint(3, 5)
        while True:
            self.screenshot()
            if self.is_in_battle(False):
                return True
            if click_times >= max_times:
                logger.warning(f'{self.climb_type} cannot enter battle, click reach max times')
                raise TicketsNotEnough
            if self.appear(self.I_UI_BACK_RED, interval=1):
                logger.warning(
                    f'{self.climb_type} cannot enter battle, appear red close button, maybe not enough tickets')
                raise TicketsNotEnough
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1) or \
                    self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if self.ocr_appear_click(self.O_FIRE, interval=1.5):
                self.device.click_record_clear()
                click_times += 1
                logger.info(f'Try click fire, remain times[{max_times - click_times}]')
                continue

    def switch_soul(self, enter_button: RuleImage):
        if self.switch_souled.get(self.climb_type, False):
            return
        self.switch_souled[self.climb_type] = True
        conf = self.conf.switch_soul_config
        config_label = self.config_label
        enable_switch = getattr(conf, f"enable_switch_{config_label}", False)
        enable_by_name = getattr(conf, f"enable_switch_{config_label}_by_name", False)
        if not enable_switch and not enable_by_name:
            return
        logger.hr('Start switch soul', 2)
        conf.validate_switch_soul()
        self.ui_click(enter_button, stop=self.I_CHECK_RECORDS, interval=1)
        if enable_by_name:
            group, team = getattr(conf, f"{config_label}_group_team_name").split(",")
            self.run_switch_soul_by_name(group, team)
        elif enable_switch:
            group_team = getattr(conf, f"{config_label}_group_team")
            self.run_switch_soul(group_team)
        self.goto_page(self.pages.get(f"page_act_{self.climb_type}"))

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """
        根据配置判断当前爬塔类型是否锁定阵容, 并执行锁定或解锁
        """
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

    def check_tickets_enough(self) -> bool:
        """
        判断当前爬塔门票是否足够
        :return: True 可以运行 or False
        """
        logger.hr(f'Check {self.climb_type} tickets')
        self.screenshot()
        remain_times = 0
        if self.climb_type == 'pass':
            remain_times = self.O_REMAIN_PASS.ocr_digit(self.device.image)
        if self.climb_type == 'ap':
            remain_times = self.O_REMAIN_AP.ocr_digit(self.device.image)
        if self.climb_type == 'boss':
            cur, remain_times, total = self.O_REMAIN_BOSS.ocr_digit_counter(self.device.image)
        # 上一次识别的票的数量和这一次识别的数量差距大于1, 则认为票数量有误, 允许继续挑战
        if self.pre_tickets_map[self.climb_type] - remain_times > 1:
            self.pre_tickets_map[self.climb_type] -= 1
            return True
        self.pre_tickets_map[self.climb_type] = remain_times
        return remain_times > 0