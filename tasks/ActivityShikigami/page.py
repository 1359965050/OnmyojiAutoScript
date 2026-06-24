from tasks.ActivityShikigami.assets import ActivityShikigamiAssets as asa
from tasks.GameUi.page import Page, page_main
from tasks.GlobalGame.assets import GlobalGameAssets as gga
from tasks.GameUi.assets import GameUiAssets as G
from tasks.Component.RightActivity.assets import RightActivityAssets as RAA

page_climb_act = Page(asa.I_TO_BATTLE_MAIN)
page_climb_act.additional = [gga.I_UI_REWARD, asa.I_SKIP_BUTTON, asa.I_CONFIRM_SKIP, asa.I_RED_EXIT]
page_climb_act.link(button=G.I_BACK_Y, destination=page_main)
page_main.link(button=[asa.I_SHI, RAA.I_TOGGLE_BUTTON], destination=page_climb_act)

page_act = Page(asa.I_TO_BATTLE_MAIN)
page_act.additional = [gga.I_UI_REWARD, asa.I_SKIP_BUTTON, asa.I_CONFIRM_SKIP, asa.I_RED_EXIT]
page_act.link(button=G.I_BACK_Y, destination=page_main)
page_main.link(button=asa.I_MAIN_GOTO_ACT, destination=page_act)

page_act_ap = Page(asa.I_CLIMB_MODE_AP)
page_act_ap.link(button=G.I_BACK_Y, destination=page_act)

page_act_pass = Page(asa.I_CLIMB_MODE_PASS)
page_act_pass.link(button=G.I_BACK_Y, destination=page_act)

page_act_ap100 = Page(asa.I_CLIMB_MODE_AP100)

page_act_boss = Page(asa.I_CHECK_BATTLE_BOSS)
page_act_boss.link(button=G.I_BACK_Y, destination=page_act)
page_act.link(button=asa.I_TO_BATTLE_BOSS, destination=page_act_boss)