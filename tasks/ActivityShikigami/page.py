from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.ActivityShikigami.descriptor import EventDescriptor
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Component.RightActivity.assets import RightActivityAssets
from tasks.GameUi.action import conditional_action, sequence
from tasks.GameUi.matcher import any_of
from tasks.GameUi.page import Page, page_main, random_click
from tasks.GlobalGame.assets import GlobalGameAssets

# 爬塔活动主界面
page_act = Page(ActivityShikigamiAssets.I_TO_BATTLE_MAIN)
page_act.add_enter_failure_hooks(RightActivityAssets.I_TOGGLE_BUTTON,
                                 conditional_action(GlobalGameAssets.I_UI_REWARD, random_click),
                                 GlobalGameAssets.I_UI_BACK_RED, ActivityShikigamiAssets.I_SKIP_BUTTON)
page_act.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act->page_main")
page_main.connect(page_act, ActivityShikigamiAssets.I_MAIN_GOTO_ACT, key="page_main->page_act")
# 体力爬塔页面
page_act_ap = Page(ActivityShikigamiAssets.I_CLIMB_MODE_AP)
page_act_ap.connect(page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_ap->page_act")
page_act.connect(page_act_ap, ActivityShikigamiAssets.I_TO_BATTLE_AP, key="page_act->page_act_ap")
# 门票爬塔页面
page_act_pass = Page(ActivityShikigamiAssets.I_CLIMB_MODE_PASS)
page_act_pass.connect(page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_pass->page_act")
# BOSS爬塔页面
# 使用 boss 挑战按钮作为页面检测，不同活动的 boss 页布局可能变化，但右下角挑战按钮相对稳定
page_act_boss = Page(ActivityShikigamiAssets.I_AS_BOSS_FIRE)
page_act_boss.connect(page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_boss->page_act")
page_act.connect(page_act_boss, ActivityShikigamiAssets.I_TO_BATTLE_BOSS, key="page_act->page_act_boss")


def create_event_pages(desc: EventDescriptor) -> dict[str, Page]:
    """根据活动描述器创建该活动的页面定义（独立于全局页面，不污染全局）"""
    # 使用与模块级页面相同的 key，确保 act_page_handle_dict 的 key 与 get_current_page 返回一致

    # 活动主界面（使用描述器的入口检测图）
    p_act = Page(desc.main_page_check, key='page_act', register=False)
    if desc.main_page_enter_failure_hooks:
        for hook in desc.main_page_enter_failure_hooks:
            p_act.add_enter_failure_hooks(hook)

    # 子模式页面（使用通用资产）
    p_act_ap = Page(ActivityShikigamiAssets.I_CLIMB_MODE_AP, key='page_act_ap', register=False)
    p_act_pass = Page(ActivityShikigamiAssets.I_CLIMB_MODE_PASS, key='page_act_pass', register=False)
    p_act_boss = Page(ActivityShikigamiAssets.I_AS_BOSS_FIRE, key='page_act_boss', register=False)

    # 正向导航连接：活动主界面 → 子模式页面
    p_act.connect(p_act_ap, ActivityShikigamiAssets.I_TO_BATTLE_AP, key="page_act->page_act_ap")

    return {
        'page_act': p_act,
        'page_act_ap': p_act_ap,
        'page_act_pass': p_act_pass,
        'page_act_boss': p_act_boss,
    }
