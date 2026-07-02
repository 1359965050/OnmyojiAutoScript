from itertools import compress
import random
import traceback

from module.atom.click import RuleClick
from tasks.BondlingFairyland.assets import BondlingFairylandAssets
from tasks.GlobalGame.assets import GlobalGameAssets as GGA
from tasks.GameUi.action import conditional_action
from tasks.GameUi.assets import GameUiAssets as G
from tasks.GameUi.matcher import any_of
from tasks.GameUi.page_definition import Page as NewPage, PageRegistry
from tasks.KekkaiUtilize.assets import KekkaiUtilizeAssets
from tasks.Restart.assets import RestartAssets
from tasks.base_task import BaseTask as BT
from tasks.RyouToppa.assets import RyouToppaAssets


class Page(NewPage):

    def __init__(self, check_button, links=None, *, key=None, name=None,
                 category="global", priority=50, cost=1.0, register=True):
        if links is None:
            links = {}
        if key is None or name is None:
            (filename, line_number, function_name, text) = traceback.extract_stack()[-2]
            inferred = text[:text.find('=')].strip()
            key = key or inferred
            name = name or inferred
        super().__init__(
            check_button,
            key=key,
            name=name,
            category=category,
            priority=priority,
            cost=cost,
            register=register,
        )
        self.check_button = check_button
        self.links = links
        self.additional: list = None

    def link(self, button, destination):
        self.links[destination] = button
        self.connect(destination, button)

    def clone(self) -> "Page":
        page = Page(
            self.check_button,
            dict(self.links),
            key=self.key,
            name=self.name,
            category=self.category,
            priority=self.priority,
            cost=self.cost,
            register=False,
        )
        page.additional = list(self.additional) if self.additional else None
        page.on_enter_success = list(self.on_enter_success)
        page.on_enter_failure = list(self.on_enter_failure)
        page.on_leave_success = list(self.on_leave_success)
        page.on_leave_failure = list(self.on_leave_failure)
        return page


page_login = Page(G.I_CHECK_LOGIN_FORM)

page_main = Page([G.I_CHECK_MAIN, G.I_MAIN_GOTO_EXPLORATION])
page_main.additional = [G.I_AD_CLOSE_RED, G.I_BACK_FRIENDS, RestartAssets.I_CANCEL_BATTLE,
                        [RestartAssets.I_LOGIN_COURTYARD, RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA],
                        GGA.I_CHAT_CLOSE_BUTTON, G.I_CLOSE_CHAT_WINDOW]

page_summon = Page(G.I_CHECK_SUMMON)
page_summon.link(button=G.I_SUMMON_GOTO_MAIN, destination=page_main)
page_main.link(button=G.I_MAIN_GOTO_SUMMON, destination=page_summon)

page_exploration = Page(G.I_CHECK_EXPLORATION)
page_exploration.link(button=G.I_BACK_YOLLOW, destination=page_main)
page_main.link(button=G.I_MAIN_GOTO_EXPLORATION, destination=page_exploration)

page_town = Page(G.I_CHECK_TOWN)
page_town.link(button=G.I_TOWN_GOTO_MAIN, destination=page_main)
page_main.link(button=G.I_MAIN_GOTO_TOWN, destination=page_town)

page_awake_zones = Page(G.I_CHECK_AWAKE)
page_awake_zones.link(button=G.I_BACK_YOLLOW, destination=page_exploration)
page_exploration.link(button=G.I_EXPLORATION_GOTO_AWAKE_ZONE, destination=page_awake_zones)

page_soul_zones = Page(G.I_CHECK_SOUL_ZONES)
page_soul_zones.link(button=G.I_BACK_YOLLOW, destination=page_exploration)
page_exploration.link(button=G.I_EXPLORATION_GOTO_SOUL_ZONE, destination=page_soul_zones)

page_realm_raid = Page(G.I_CHECK_REALM_RAID)
page_realm_raid.link(button=G.I_REALM_RAID_GOTO_EXPLORATION, destination=page_exploration)
page_exploration.link(button=G.I_EXPLORATION_GOTO_REALM_RAID, destination=page_realm_raid)

page_kekkai_toppa = Page(G.I_KEKKAI_TOPPA)
page_kekkai_toppa.link(button=G.I_REALM_RAID_GOTO_EXPLORATION, destination=page_exploration)
page_realm_raid.link(button=RyouToppaAssets.I_RYOU_TOPPA, destination=page_kekkai_toppa)
page_kekkai_toppa.link(button=G.I_RYOUTOPPA_GOTO_REALMRAID, destination=page_realm_raid)

page_goryou_realm = Page(G.I_CHECK_GORYOU)
page_goryou_realm.link(button=G.I_BACK_YOLLOW, destination=page_exploration)
page_exploration.link(button=G.I_EXPLORATION_GOTO_GORYOU_REALM, destination=page_goryou_realm)

page_delegation = Page(G.I_CHECK_DELEGATION)
page_delegation.link(button=G.I_BACK_YOLLOW, destination=page_exploration)
page_exploration.link(button=G.I_EXPLORATION_GOTO_DELEGATION, destination=page_delegation)

page_secret_zones = Page(G.I_CHECK_SECRET_ZONES)
page_secret_zones.link(button=G.I_BACK_YOLLOW, destination=page_exploration)
page_exploration.link(button=G.I_EXPLORATION_GOTO_SECRET_ZONES, destination=page_secret_zones)

page_area_boss = Page(G.I_CHECK_AREA_BOSS)
page_area_boss.link(button=G.I_BACK_YOLLOW, destination=page_exploration)
page_exploration.link(button=G.I_EXPLORATION_GOTO_AREA_BOSS, destination=page_area_boss)

page_heian_kitan = Page(G.I_CHECK_HEIAN_KITAN)
page_heian_kitan.link(button=G.I_CHECK_HEIAN_KITAN, destination=page_exploration)
page_exploration.link(button=G.I_EXPLORATION_GOTO_HEIAN_KITAN, destination=page_heian_kitan)

page_six_gates = Page(G.O_CHECK_SIX_GATES)
page_six_gates.link(button=G.I_SIX_GATES_GOTO_EXPLORATION, destination=page_exploration)
page_exploration.link(button=G.O_EXPLORATION_GOTO_SIX_GATES, destination=page_six_gates)

page_bondling_fairyland = Page(BondlingFairylandAssets.I_BALL_AREA)
page_bondling_fairyland.link(button=G.I_BACK_YOLLOW, destination=page_exploration)
page_exploration.link(button=G.I_EXPLORATION_GOTO_BONDLING_FAIRYLAND, destination=page_bondling_fairyland)

page_hero_test = Page(G.I_CHECK_HERO_TEST)
page_hero_test.link(button=G.I_BACK_YOLLOW, destination=page_exploration)
page_exploration.link(button=G.I_EXPLORATION_GOTO_HERO_TEST, destination=page_hero_test)

page_demon_encounter = Page(G.I_CHECK_DEMON_ENCOUNTER)
page_demon_encounter.link(button=G.I_BACK_YOLLOW, destination=page_town)
page_town.link(button=G.I_TOWN_GOTO_DEMON_ENCOUNTER, destination=page_demon_encounter)

page_demon_encounter_realworld = Page(G.I_CHECK_DEMON_ENCOUNTER_REALWORLD)
page_demon_encounter_realworld.link(button=G.I_BACK_YOLLOW, destination=page_demon_encounter)
page_demon_encounter.link(button=G.I_DEMON_ENCOUNTER_REALWORLD_GOTO, destination=page_demon_encounter_realworld)

page_hunt = Page(G.I_CHECK_HUNT)
page_hunt.link(button=G.I_BACK_YOLLOW, destination=page_town)
page_town.link(button=G.I_TOWN_GOTO_HUNT, destination=page_hunt)

page_hunt_kirin = Page(G.I_CHECK_HUNT_KIRIN)
page_hunt_kirin.link(button=G.I_BACK_YOLLOW, destination=page_town)
page_town.link(button=G.I_TOWN_GOTO_HUNT, destination=page_hunt_kirin)

page_hyakkisen = Page(G.I_CHECK_HYAKKISEN)
page_hyakkisen.link(button=G.I_BACK_YOLLOW, destination=page_town)
page_town.link(button=G.I_TOWN_GOTO_HYAKKISEN, destination=page_hyakkisen)

page_hyakkiyakou = Page(G.I_CHECK_KYAKKIYAKOU)
page_hyakkiyakou.link(button=G.I_HYAKKIYAKOU_CLOSE, destination=page_town)
page_town.link(button=G.I_TOWN_GOTO_HYAKKIYAKOU, destination=page_hyakkiyakou)

page_shikigami_records = Page(G.I_CHECK_RECORDS)
page_shikigami_records.additional = [G.I_AD_DISAPPEAR, G.I_RECORDS_CLOSE, GGA.I_UI_CANCEL_SAMLL]
page_shikigami_records.add_enter_failure_hooks(conditional_action(condition=G.I_CHECK_MAIN,
                                                                  action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_shikigami_records.link(button=G.I_BACK_Y, destination=page_main)
page_main.link(button=G.I_MAIN_GOTO_SHIKIGAMI_RECORDS, destination=page_shikigami_records)

page_onmyodo = Page(G.I_CHECK_ONMYODO)
page_onmyodo.add_enter_failure_hooks(conditional_action(condition=G.I_CHECK_MAIN,
                                                        action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_onmyodo.link(button=G.I_BACK_Y, destination=page_main)
page_main.link(button=G.I_MAIN_GOTO_ONMYODO, destination=page_onmyodo)

page_friends = Page(G.I_CHECK_FRIENDS)
page_friends.add_enter_failure_hooks(conditional_action(condition=G.I_CHECK_MAIN,
                                                        action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_friends.link(button=G.I_BACK_Y, destination=page_main)
page_main.link(button=G.I_MAIN_GOTO_FRIENDS, destination=page_friends)

page_daily = Page(G.I_CHECK_DAILY)
page_daily.add_enter_failure_hooks(
    conditional_action(condition=G.I_CHECK_MAIN, action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA),
    conditional_action(condition=lambda task: not task.appear(G.I_CHECK_MAIN),
                       action=lambda task: task.ui_click(click=random_click(ltrb=(False, False, False, True)),
                                                         stop=GGA.I_UI_BACK_YELLOW)))
page_daily.link(button=G.I_BACK_Y, destination=page_main)
page_main.link(button=G.I_MAIN_GOTO_DAILY, destination=page_daily)

page_mall = Page(check_button=G.I_CHECK_MALL)
page_mall.additional = [G.I_AD_CLOSE_RED, GGA.I_UI_CANCEL_SAMLL, G.I_BACK_Y]
page_mall.add_enter_failure_hooks(conditional_action(condition=G.I_CHECK_MAIN,
                                                     action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_mall.link(button=G.I_BACK_YOLLOW, destination=page_main)
page_main.link(button=G.I_MAIN_GOTO_MALL, destination=page_mall)

page_guild = Page(G.I_CHECK_GUILD)
page_guild.additional = [KekkaiUtilizeAssets.I_PLANT_TREE_CLOSE, G.I_CLOSE_CHAT_WINDOW]
page_guild.add_enter_failure_hooks(conditional_action(condition=G.I_CHECK_MAIN,
                                                      action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_guild.link(button=G.I_BACK_Y, destination=page_main)
page_main.link(button=G.I_MAIN_GOTO_GUILD, destination=page_guild)

page_team = Page(G.I_CHECK_TEAM)
page_team.add_enter_failure_hooks(conditional_action(condition=G.I_CHECK_MAIN,
                                                     action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_team.link(button=G.I_BACK_Y, destination=page_main)
page_main.link(button=G.I_MAIN_GOTO_TEAM, destination=page_team)

page_collection = Page(G.I_CHECK_COLLECTION)
page_collection.additional = [GGA.I_UI_CANCEL_SAMLL]
page_collection.add_enter_failure_hooks(conditional_action(condition=G.I_CHECK_MAIN,
                                                           action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_collection.link(button=G.I_BACK_Y, destination=page_main)
page_main.link(button=G.I_MAIN_GOTO_COLLECTION, destination=page_collection)

page_travel = Page(G.I_CHECK_TRAVEL)
page_travel.add_enter_failure_hooks(conditional_action(condition=G.I_CHECK_MAIN,
                                                       action=RestartAssets.C_LOGIN_SCROLL_CLOSE_AREA))
page_travel.link(button=G.I_BACK_Y, destination=page_main)
page_main.link(button=G.I_MAIN_GOTO_TRAVEL, destination=page_travel)

from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Dokan.assets import DokanAssets

page_dokan = Page(DokanAssets.I_RYOU_DOKAN_CHECK)
page_dokan.additional = [GeneralBattleAssets.I_EXIT, DokanAssets.I_RYOU_DOKAN_EXIT_ENSURE, G.I_BACK_BLUE]
page_dokan.link(button=G.I_BACK_Y, destination=page_main)


def random_click(low: int = None, high: int = None, ltrb: tuple = (True, False, True, False)) -> RuleClick | list[RuleClick]:
    from tasks.Component.GeneralBattle.assets import GeneralBattleAssets as GBA
    click_area_list = [GBA.C_REWARD_1, GBA.C_REWARD_2, GBA.C_REWARD_3]
    click = random.choice(list(compress(click_area_list, ltrb)))
    click.name = "SAFE_RANDOM_CLICK"
    if low is None or high is None:
        return click
    return [click for _ in range(random.randint(low, high))]