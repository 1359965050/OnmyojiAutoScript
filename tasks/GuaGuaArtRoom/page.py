from tasks.GameUi.page import Page, page_main
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.GuaGuaArtRoom.assets import GuaGuaArtRoomAssets


# 活动总览页（呱呱画室主页面）
page_act = Page(GuaGuaArtRoomAssets.I_CHECK_ACT_MAIN, key='page_act', register=False)

# 获取颜料子页面
page_paint_collection = Page(GuaGuaArtRoomAssets.I_CHECK_PAINT_COLLECTION,
                             key='page_paint_collection', register=False)


def create_gua_gua_pages(navigator) -> dict[str, Page]:
    """创建呱呱画室相关页面并建立导航连接

    使用 navigator 的会话副本操作，避免污染全局页面导航图。
    """
    p_act = navigator.add_page(page_act)
    p_paint = navigator.add_page(page_paint_collection)

    # 庭院 <-> 活动总览
    session_main = navigator.resolve_page(page_main)
    session_main.connect(p_act, GuaGuaArtRoomAssets.I_MAIN_GOTO_ACT, key="page_main->page_act")
    p_act.connect(session_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act->page_main")

    # 活动总览 <-> 获取颜料
    p_act.connect(p_paint, GuaGuaArtRoomAssets.I_TO_PAINT_COLLECTION, key="page_act->page_paint_collection")
    p_paint.connect(p_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_paint_collection->page_act")

    return {
        'page_act': p_act,
        'page_paint_collection': p_paint,
    }
