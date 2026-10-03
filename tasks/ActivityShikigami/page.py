from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.Component.BaseActivity.assets import BaseActivityAssets
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Component.RightActivity import RightActivity, RightActivityAssets
from tasks.GameUi.action import conditional_action
from tasks.GameUi.default_pages import random_click
from tasks.GameUi.page import (Page, page_main, sequence, page_battle, page_battle_prepare, page_reward,
                               page_battle_result, any_of)
from tasks.GlobalGame.assets import GlobalGameAssets

# 爬塔活动主界面
def action_enter_activity(task) -> bool:
    """进入活动主界面的通用免更寻径动作：
    调用通用寻径流水线 enter_activity_via_overview（庭院侧边栏 -> 活动总览 -> 版本活动 -> 前往活动）。
    """
    if hasattr(task, "enter_activity_via_overview"):
        return task.enter_activity_via_overview()
    return False

def action_act_goto_battle(task) -> bool:
    """从活动主界面自适应进入战斗入口动作（自动寻找‘战斗’、‘出击’、‘挑战’等入口）。"""
    if hasattr(task, "find_and_click_act_battle"):
        return task.find_and_click_act_battle()
    return False

def action_map_goto_battle(task) -> bool:
    """从中转地图自适应进入具体爬塔房间动作（在推荐关卡区域自适应定位与安全点击）。"""
    if hasattr(task, "find_and_click_map_battle"):
        return task.find_and_click_map_battle()
    return False

# 活动主界面页面识别器（带前置快速过滤与互斥保护）
def check_page_act(task) -> bool:
    """活动主界面识别：
    1. 必须存在左上角黄色返回键，否则绝非活动主界面；
    2. 若已处于爬塔房间（双态胶囊判定为 pass/ap 或检测到阵容锁），互斥短路返回 False，避免多余 OCR；
    3. 优先检测配置的『战斗界面名称』（如“亘地回响”）；
    4. 若未配置或未搜到，通过 OCR 自适应检测主界面战斗入口。
    """
    if not task.appear(GlobalGameAssets.I_UI_BACK_YELLOW):
        return False
    if hasattr(task, "get_current_climb_mode") and task.get_current_climb_mode() in ("pass", "ap"):
        return False
    if task.appear(ActivityShikigamiAssets.I_LOCK) or task.appear(ActivityShikigamiAssets.I_UNLOCK):
        return False

    # 优先检测配置的『战斗界面名称』（如“亘地回响”）
    if hasattr(task, "find_configured_battle_name_box"):
        if task.find_configured_battle_name_box() is not None:
            return True

    return bool(
        task.ocr_appear(BaseActivityAssets.O_ACT_BATTLE_ENTRANCE)
        or task.ocr_appear(BaseActivityAssets.O_ACT_BATTLE_ENTRANCE_CHAR)
    )


# 特殊活动中转地图页面识别器（带前置快速过滤与互斥保护）
def check_page_act_map(task) -> bool:
    """中转地图页面识别：
    1. 必须存在左上角黄色返回键；
    2. 若已处于爬塔房间，互斥短路返回 False；
    3. 仅在地图界面时才通过 OCR 自适应检测左侧关卡卡片入口。
    """
    if not task.appear(GlobalGameAssets.I_UI_BACK_YELLOW):
        return False
    if hasattr(task, "get_current_climb_mode") and task.get_current_climb_mode() in ("pass", "ap"):
        return False
    if task.appear(ActivityShikigamiAssets.I_LOCK) or task.appear(ActivityShikigamiAssets.I_UNLOCK):
        return False
    return bool(
        task.ocr_appear(BaseActivityAssets.O_MAP_BATTLE_ENTRANCE)
        or task.ocr_appear(BaseActivityAssets.O_MAP_BATTLE_ENTRANCE_CHAR)
    )


# 活动主界面（自适应文字入口识别，优先级 40）
page_act = Page(check_page_act, priority=40)
page_act.add_enter_failure_hooks(RightActivity.sidebar_switch_hook,
                                 conditional_action(GlobalGameAssets.I_UI_REWARD, random_click),
                                 GlobalGameAssets.I_UI_BACK_RED, ActivityShikigamiAssets.I_SKIP_BUTTON)
page_act.connect(page_main, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act->page_main")
page_main.connect(page_act, action_enter_activity, key="page_main->page_act")

# 特殊活动中转地图页面（自适应识别左侧关卡卡片区域‘战斗’或‘战’，优先级 45）
page_act_map = Page(check_page_act_map, priority=45)
page_act_map.connect(page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_map->page_act")
page_act.connect(page_act_map, action_act_goto_battle, key="page_act->page_act_map")

# 体力爬塔页面（自适应双态亮度判定，优先级 70）
page_act_ap = Page(lambda task: getattr(task, "is_climb_mode_ap", lambda: False)(), priority=70)
page_act_ap.connect(page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_ap->page_act")

# 门票爬塔页面（自适应双态亮度判定，优先级 70）
page_act_pass = Page(lambda task: getattr(task, "is_climb_mode_pass", lambda: False)(), priority=70)
page_act_pass.connect(page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_pass->page_act")

# 100体爬塔页面
page_act_ap100 = Page(ActivityShikigamiAssets.I_CLIMB_MODE_AP100, priority=70)
page_act_ap100.add_enter_failure_hooks(GlobalGameAssets.I_UI_BACK_RED)

# BOSS爬塔页面
page_act_boss = Page(lambda task: getattr(task, "is_in_boss_page", lambda: False)(), priority=65)
page_act_boss.connect(page_act, GlobalGameAssets.I_UI_BACK_YELLOW, key="page_act_boss->page_act")
page_act.connect(page_act_boss, action_act_goto_battle, key="page_act->page_act_boss")
