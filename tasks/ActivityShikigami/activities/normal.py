from module.logger import logger
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.base_act import BaseAct
from tasks.ActivityShikigami.descriptor import EventDescriptor
import tasks.ActivityShikigami.page as pages
from tasks.Component.RightActivity.assets import RightActivityAssets
from tasks.GameUi.action import conditional_action
from tasks.GameUi.page import random_click
from tasks.GlobalGame.assets import GlobalGameAssets

# ============================================================
# 普通爬塔描述器
# ============================================================
NORMAL_CLIMB = EventDescriptor(
    event_id="normal",
    name="普通爬塔",
    entry_button=ActivityShikigamiAssets.I_MAIN_GOTO_ACT,
    main_page_check=ActivityShikigamiAssets.I_TO_BATTLE_MAIN,
    main_page_enter_failure_hooks=[
        RightActivityAssets.I_TOGGLE_BUTTON,
        conditional_action(GlobalGameAssets.I_UI_REWARD, random_click),
        GlobalGameAssets.I_UI_BACK_RED,
        ActivityShikigamiAssets.I_SKIP_BUTTON,
    ],
)
BaseAct.event_descriptors['normal'] = NORMAL_CLIMB


class NormalClimbAct(BaseAct):
    """普通爬塔活动"""

    def before_run(self):
        super().before_run()
        page_act = self.navigator.resolve_page(self.pages['page_act'])
        page_act_pass = self.navigator.resolve_page(self.pages['page_act_pass'])
        page_act_ap = self.navigator.resolve_page(self.pages['page_act_ap'])
        # 体力爬塔和主界面关联
        page_act.connect(page_act_ap, ActivityShikigamiAssets.I_TO_BATTLE_MAIN, key="page_act->page_act_ap")
        # 体力爬塔进入是门票则切换
        page_act_ap.add_enter_failure_hooks(pages.conditional_action(
            condition=ActivityShikigamiAssets.I_CLIMB_MODE_PASS, action=ActivityShikigamiAssets.I_CLIMB_MODE_SWITCH))
        # 门票爬塔和主界面关联
        page_act.connect(page_act_pass, ActivityShikigamiAssets.I_TO_BATTLE_MAIN, key="page_act->page_act_pass")
        # 门票爬塔进入是体力则切换
        page_act_pass.add_enter_failure_hooks(pages.conditional_action(
            condition=ActivityShikigamiAssets.I_CLIMB_MODE_AP, action=ActivityShikigamiAssets.I_CLIMB_MODE_SWITCH))
        # 门票和体力互相切换
        page_act_pass.connect(page_act_ap, ActivityShikigamiAssets.I_CLIMB_MODE_SWITCH, key="page_act_pass->page_act_ap")
        page_act_ap.connect(page_act_pass, ActivityShikigamiAssets.I_CLIMB_MODE_SWITCH, key="page_act_ap->page_act_pass")
