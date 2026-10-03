from module.logger import logger
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.base_act import BaseAct
import tasks.ActivityShikigami.page as pages
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import ExitMatcher


class NormalClimbAct(BaseAct):
    """普通爬塔活动"""

    def _exit_matcher(self) -> ExitMatcher | None:
        return pages.any_of(
            self.O_GENERIC_FIRE,
            getattr(self, 'I_ACT_FIRE', None),
        )

    def before_run(self):
        super().before_run()
        page_act = self.navigator.resolve_page(pages.page_act)
        page_act_pass = self.navigator.resolve_page(pages.page_act_pass)
        page_act_ap = self.navigator.resolve_page(pages.page_act_ap)
        page_act_map = self.navigator.resolve_page(pages.page_act_map)
        flag = getattr(self.conf.general_climb, 'special_act_map', True)

        if flag:
            # 体力/门票爬塔与特殊中转界面关联
            page_act_map.connect(
                page_act_ap,
                pages.action_map_goto_battle,
                key="page_act_map->page_act_ap",
            )
            page_act_map.connect(
                page_act_pass,
                pages.action_map_goto_battle,
                key="page_act_map->page_act_pass",
            )
            page_act_ap.connect(
                page_act_map,
                pages.GlobalGameAssets.I_UI_BACK_YELLOW,
                key="page_act_ap->page_act_map",
            )
            page_act_pass.connect(
                page_act_map,
                pages.GlobalGameAssets.I_UI_BACK_YELLOW,
                key="page_act_pass->page_act_map",
            )
        else:
            # 体力/门票爬塔与主界面关联
            page_act.connect(
                page_act_ap,
                pages.action_act_goto_battle,
                key="page_act->page_act_ap",
            )
            page_act.connect(
                page_act_pass,
                pages.action_act_goto_battle,
                key="page_act->page_act_pass",
            )
            page_act_ap.connect(
                page_act,
                pages.GlobalGameAssets.I_UI_BACK_YELLOW,
                key="page_act_ap->page_act",
            )
            page_act_pass.connect(
                page_act,
                pages.GlobalGameAssets.I_UI_BACK_YELLOW,
                key="page_act_pass->page_act",
            )

        # 自适应页面识别（双态亮度与寿司色彩判定）
        page_act_ap.recognizer = pages.any_of(self.is_climb_mode_ap)
        page_act_pass.recognizer = pages.any_of(self.is_climb_mode_pass)

        # 门票和体力互相切换（自适应胶囊区域，点击后等待 1.5s 动画完成）
        def do_switch_mode(task):
            getattr(task, 'toggle_climb_mode', lambda: False)(interval=1.5)
            return True

        page_act_pass.connect(page_act_ap, do_switch_mode, key="page_act_pass->page_act_ap")
        page_act_ap.connect(page_act_pass, do_switch_mode, key="page_act_ap->page_act_pass")

    def lock_team(self, battle_conf: GeneralBattleConfig):
        enable = battle_conf.lock_team_enable
        match self.climb_type:
            case 'boss':
                lock_rule = self.I_LOCK
                unlock_rule = self.I_UNLOCK
            case _:
                lock_rule = self.I_AP_LOCK
                unlock_rule = self.I_AP_UNLOCK
        if enable:
            logger.info(f'Lock {self.climb_type} team')
            self.ui_click(unlock_rule, stop=lock_rule, interval=1.5)
            return
        logger.info(f'Unlock {self.climb_type} team')
        self.ui_click(lock_rule, stop=unlock_rule, interval=1.5)
