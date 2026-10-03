from tasks.Component.RightActivity import RightActivity
from tasks.Component.BaseActivity.assets import BaseActivityAssets
from tasks.GameUi.page import Page, page_main, page_act_list
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.AbyssIllusion.assets import AbyssIllusionAssets


# 伊吹之擂主页面
page_act = Page(AbyssIllusionAssets.I_CHECK_ACT_MAIN, key='page_act', register=False)
page_act.add_enter_failure_hooks(RightActivity.sidebar_switch_hook)

# 活动总览页（寻径中转站）：以 OCR 标题『活动总览』作为识别条件，
# 比全局模板 I_CHECK_ACT_LIST 更抗版本/布局漂移，保障断点续跑可识别。
page_act_overview = Page(BaseActivityAssets.O_OVERVIEW_TITLE, key='page_act_overview', register=False)

# 狭间幻境挑战页面
page_abyss_illusion = Page(AbyssIllusionAssets.I_CHECK_ABYSS_ILLUSION_MAIN,
                            key='page_abyss_illusion', register=False)


def action_enter_ibuki(task) -> bool:
    """从庭院通过活动总览滑屏寻径进入伊吹之擂。"""
    if hasattr(task, "enter_ibuki_via_overview"):
        return task.enter_ibuki_via_overview()
    return False


def create_abyss_illusion_pages(navigator) -> dict[str, Page]:
    """创建狭间幻境相关页面并建立导航连接"""
    p_act = navigator.add_page(page_act)
    p_overview = navigator.add_page(page_act_overview)
    p_abyss = navigator.add_page(page_abyss_illusion)

    # 庭院 <-> 活动总览（经活动总览滑屏寻径进入伊吹之擂）
    session_main = navigator.resolve_page(page_main)
    session_main.connect(p_act, action_enter_ibuki, key="page_main->page_act")
    p_act.connect(session_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act->page_main")

    # 活动总览 -> 伊吹之擂（断点续跑：停留在活动总览时直接续跑，无需退回庭院）
    p_overview.connect(p_act, action_enter_ibuki, key="page_act_overview->page_act")
    p_overview.connect(session_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_overview->page_main")

    # 兼容全局模板版活动总览页 page_act_list：同样直连伊吹之擂
    # 注：page_act_list 为全局页面，resolve_page 返回的是本任务 session 的克隆，
    #     在此克隆上连接边不会影响其他任务的导航图。
    session_act_list = navigator.resolve_page(page_act_list)
    if session_act_list is not None:
        session_act_list.connect(p_act, action_enter_ibuki, key="page_act_list->page_act")

    # 活动总览 <-> 狭间幻境
    p_act.connect(p_abyss, AbyssIllusionAssets.I_TO_ABYSS_ILLUSION, key="page_act->page_abyss_illusion")
    p_abyss.connect(p_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_abyss_illusion->page_act")

    return {
        'page_act': p_act,
        'page_abyss_illusion': p_abyss,
    }
