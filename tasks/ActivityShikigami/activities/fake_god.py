from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.base_act import BaseAct
from tasks.ActivityShikigami.descriptor import EventDescriptor
from tasks.Component.RightActivity.assets import RightActivityAssets
from tasks.GameUi.action import conditional_action
from tasks.GameUi.page import Page, random_click
from tasks.GlobalGame.assets import GlobalGameAssets

# ============================================================
# 伪神活动描述器
# ============================================================
FAKE_GOD_CLIMB = EventDescriptor(
    event_id="fake_god",
    name="伪神活动",
    entry_button=ActivityShikigamiAssets.I_MAIN_GOTO_ACT,
    main_page_check=ActivityShikigamiAssets.I_TO_BATTLE_MAIN,
    main_page_enter_failure_hooks=[
        RightActivityAssets.I_TOGGLE_BUTTON,
        conditional_action(GlobalGameAssets.I_UI_REWARD, random_click),
        GlobalGameAssets.I_UI_BACK_RED,
        ActivityShikigamiAssets.I_SKIP_BUTTON,
    ],
)
BaseAct.event_descriptors['fake_god'] = FAKE_GOD_CLIMB


def _setup_fake_god_pages(act):
    """注册伪神活动特有的页面（暗黑页等）"""
    page_act = act.navigator.resolve_page(act.pages['page_act'])
    page_act_pass = act.navigator.resolve_page(act.pages['page_act_pass'])
    page_act_ap = act.navigator.resolve_page(act.pages['page_act_ap'])

    # 爬塔活动第2个页面
    page_act_2 = act.navigator.add_page(Page(ActivityShikigamiAssets.I_AS_CHECK_MAIN_2,
                                             category='activity_shikigami'))
    page_act_2.add_enter_success_hooks(GlobalGameAssets.I_UI_BACK_RED)
    page_act.connect(page_act_2, ActivityShikigamiAssets.I_TO_BATTLE_MAIN, key="page_act->page_act_2")
    page_act_2.connect(page_act, GlobalGameAssets.I_UI_BACK_CIRCLE, key="page_act_2->page_act")
    # 爬塔暗黑页面
    page_act_dark = act.navigator.add_page(Page(ActivityShikigamiAssets.I_AS_CLOSE_EYE,
                                                category='activity_shikigami', priority=75))
    page_act_dark.add_enter_failure_hooks(GlobalGameAssets.I_UI_BACK_RED)
    page_act_dark.add_enter_success_hooks(ActivityShikigamiAssets.I_AS_LOCATE)
    page_act_dark.connect(page_act, GlobalGameAssets.I_UI_BACK_CIRCLE, key="page_act_dark->page_act")
    page_act_2.connect(page_act_dark, ActivityShikigamiAssets.I_AS_OPEN_EYE, key="page_act_2->page_act_dark")
    # 门票和暗黑页面关联
    page_act_pass.connect(page_act_dark, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_pass->page_act_2")
    page_act_dark.connect(page_act_pass, ActivityShikigamiAssets.I_AS_TO_PASS, key="page_act_dark->page_act_pass")
    # 主界面和体力页面关联
    page_act.connect(page_act_ap, ActivityShikigamiAssets.I_TO_BATTLE_AP, key="page_act->page_act_ap")


# 注册回调
FAKE_GOD_CLIMB.on_setup_pages = _setup_fake_god_pages


class FakeGodAct(BaseAct):
    """伪神活动"""

    def before_run(self):
        super().before_run()
