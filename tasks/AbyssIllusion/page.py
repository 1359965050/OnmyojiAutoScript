from tasks.GameUi.page import Page, page_main
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.AbyssIllusion.assets import AbyssIllusionAssets


# 活动总览页（伊吹之擂主页面）
page_act = Page(AbyssIllusionAssets.I_CHECK_ACT_MAIN, key='page_act', register=False)

# 狭间幻境挑战页面
page_abyss_illusion = Page(AbyssIllusionAssets.I_CHECK_ABYSS_ILLUSION_MAIN,
                            key='page_abyss_illusion', register=False)


def create_abyss_illusion_pages(navigator) -> dict[str, Page]:
    """创建狭间幻境相关页面并建立导航连接"""
    p_act = navigator.add_page(page_act)
    p_abyss = navigator.add_page(page_abyss_illusion)

    # 庭院 <-> 活动总览
    session_main = navigator.resolve_page(page_main)
    session_main.connect(p_act, AbyssIllusionAssets.I_MAIN_GOTO_ACT, key="page_main->page_act")
    p_act.connect(session_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act->page_main")

    # 活动总览 <-> 狭间幻境
    p_act.connect(p_abyss, AbyssIllusionAssets.I_TO_ABYSS_ILLUSION, key="page_act->page_abyss_illusion")
    p_abyss.connect(p_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_abyss_illusion->page_act")

    return {
        'page_act': p_act,
        'page_abyss_illusion': p_abyss,
    }
