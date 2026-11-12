# This Python file uses the following encoding: utf-8
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from module.atom.image import RuleImage
from module.base.timer import Timer
from tasks.AbyssShadows.config import Code
from tasks.AbyssShadows.script_task import ScriptTask as AbyssShadowsTask
from tasks.AreaBoss.script_task import ScriptTask as AreaBossTask
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.Costume.config import (
    BattleType,
    CostumeConfig,
    CourtyardAffairType,
    MainType,
    RealmType,
    ShikigamiType,
)
from tasks.Component.Costume.costume_base import CostumeBase
from tasks.DemonEncounter.script_task import ScriptTask as DemonEncounterTask
from tasks.Exploration.solo import Scene, SoloExploration
from tasks.GameUi.assets import GameUiAssets
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.RealmRaid.script_task import ScriptTask as RealmRaidTask
from tasks.RichMan.config import Shrine as ShrineConfig, SpecialRoom, ThousandThings as ThousandThingsConfig
from tasks.RichMan.mall.scales import Scales
from tasks.RichMan.mall.special import Special
from tasks.RichMan.shrine import Shrine
from tasks.RichMan.thousand_things import ThousandThings


class _AlwaysReachedTimer:
    def __init__(self, limit=0, count=0):
        self._limit = limit

    def start(self):
        return self

    def reset(self):
        return self

    def started(self):
        return True

    def current(self):
        return float(self._limit)

    def reached(self):
        return True


class TestBatch1Fixes(unittest.TestCase):
    def test_base_activity_main_page_rejects_overview_and_non_activity_screens(self):
        act = BaseActivity.__new__(BaseActivity)
        act.O_OVERVIEW_TITLE = MagicMock()

        def make_appear(active_assets):
            return lambda asset: asset in active_assets

        act.appear = make_appear({GlobalGameAssets.I_UI_BACK_YELLOW})
        act.ocr_appear = MagicMock(return_value=True)
        self.assertFalse(act._is_in_activity_main_page())

        act.ocr_appear = MagicMock(return_value=False)
        for non_act in (
            GameUiAssets.I_CHECK_MAIN,
            GameUiAssets.I_CHECK_EXPLORATION,
            GameUiAssets.I_CHECK_TOWN,
        ):
            act.appear = make_appear({GlobalGameAssets.I_UI_BACK_YELLOW, non_act})
            self.assertFalse(act._is_in_activity_main_page(), f"Should reject {non_act}")

        act.appear = make_appear({GlobalGameAssets.I_UI_BACK_YELLOW})
        self.assertTrue(act._is_in_activity_main_page())

    def test_base_activity_sidebar_toggle_reachable_before_fallback_click(self):
        act = BaseActivity.__new__(BaseActivity)
        act.I_TOGGLE_BUTTON = MagicMock(name="I_TOGGLE_BUTTON")
        act.O_SIDEBAR_ACTIVITY = MagicMock(name="O_SIDEBAR_ACTIVITY")
        act.C_SIDEBAR_ACTIVITY = MagicMock(name="C_SIDEBAR_ACTIVITY")
        act.ensure_sidebar_open = MagicMock(return_value=True)
        act.screenshot = MagicMock()
        act.ocr_appear_click = MagicMock(return_value=False)
        act.click = MagicMock(return_value=True)
        act.appear_then_click = MagicMock(return_value=True)

        calls = []
        state = {"toggled": False}

        def appear_side_effect(asset):
            if asset is GameUiAssets.I_ACT_LIST_EXPAND:
                return state["toggled"]
            if asset is act.I_TOGGLE_BUTTON:
                return not state["toggled"]
            return False

        def toggle_side_effect(*args, **kwargs):
            calls.append("toggle")
            state["toggled"] = True
            return True

        act.appear = MagicMock(side_effect=appear_side_effect)
        act.toggle_sidebar = MagicMock(side_effect=toggle_side_effect)

        with patch("time.sleep", return_value=None):
            ok = act._step_click_sidebar_activity(timeout=2.0)

        self.assertTrue(ok)
        self.assertEqual(calls, ["toggle"])
        act.click.assert_not_called()
        act.appear_then_click.assert_called_once_with(GameUiAssets.I_ACT_LIST_EXPAND, interval=1.0)

    def test_costume_config_preserves_valid_enum_and_falls_back_invalid(self):
        cfg_valid = CostumeConfig(costume_realm_type=RealmType.COSTUME_REALM_DEFAULT.value)
        self.assertEqual(cfg_valid.costume_realm_type, RealmType.COSTUME_REALM_DEFAULT)

        cfg_legacy = CostumeConfig(costume_realm_type="legacy_removed_realm")
        self.assertEqual(cfg_legacy.costume_realm_type, RealmType.COSTUME_REALM_DEFAULT)

    def test_costume_base_restores_default_skin_without_polluting_rule_image(self):
        orig_front = [10, 20, 30, 40]
        orig_back = (0, 0, 100, 100)
        rule = RuleImage(orig_front, orig_back, RuleImage.METHOD_TEMPLATE_MATCH, 0.85, "./default.png")
        host = CostumeBase()
        host.I_CHECK_MAIN = rule

        # 切换到非默认皮肤会原地修改规则对象并清空图像缓存
        host.check_costume_main(MainType.COSTUME_MAIN_1)
        self.assertNotEqual(rule.file, "./default.png")
        self.assertIsNone(rule._image)
        self.assertFalse(rule._mask_loaded)

        # 切回默认皮肤时完整恢复初始 ROI、threshold、method 和文件路径
        host.check_costume_main(MainType.COSTUME_MAIN)
        self.assertEqual(rule.file, "./default.png")
        self.assertEqual(rule.roi_front, orig_front)
        self.assertEqual(rule.roi_back, orig_back)
        self.assertEqual(rule.threshold, 0.85)
        self.assertEqual(rule.method, RuleImage.METHOD_TEMPLATE_MATCH)

    def test_exploration_solo_scene_and_wait_world_stable_timeout(self):
        solo = SoloExploration.__new__(SoloExploration)
        solo.I_CHECK_EXPLORATION = MagicMock()
        solo.I_E_SETTINGS_BUTTON = MagicMock()
        solo.I_E_AUTO_ROTATE_ON = MagicMock()
        solo.I_E_AUTO_ROTATE_OFF = MagicMock()
        solo.I_E_EXPLORATION_CLICK = MagicMock()
        solo.I_CREATE_ENSURE = MagicMock()
        solo.I_EXP_ARROW_LEFT = MagicMock()
        solo.I_EXP_ARROW_RIGHT = MagicMock()
        solo.screenshot = MagicMock()
        solo.is_in_prepare = MagicMock(return_value=False)
        solo.is_in_battle = MagicMock(return_value=False)
        solo.is_in_room = MagicMock(return_value=False)
        solo.appear = MagicMock(side_effect=lambda x: x is solo.I_CHECK_EXPLORATION)

        self.assertEqual(solo.get_current_scene(reuse_screenshot=True), Scene.WORLD)

        solo.appear_then_click = MagicMock(return_value=False)
        with patch("tasks.Exploration.solo.Timer", _AlwaysReachedTimer):
            self.assertFalse(solo.wait_world_stable(timeout=0.5))

    def test_bounded_loops_exit_cleanly_on_timeout_and_ocr_failures(self):
        # RichMan/Scales OCR 连续错误熔断
        scales = Scales.__new__(Scales)
        scales.device = SimpleNamespace(image=None)
        scales.I_SCA_OROCHI_SCALES = MagicMock()
        scales.O_SCA_NUMBER_OROCHI = MagicMock()
        scales.O_SCA_NUMBER_OROCHI.ocr = MagicMock(return_value=5)
        scales.O_SCA_RES_OROCHI = MagicMock()
        scales.O_SCA_RES_OROCHI.ocr = MagicMock(return_value=(10, 10, 999))
        scales.screenshot = MagicMock()
        scales.appear = MagicMock(return_value=True)
        scales._scales_orochi_new(10)
        self.assertEqual(scales.O_SCA_RES_OROCHI.ocr.call_count, 10)

        # RichMan/Special 超时保护
        sp = Special.__new__(Special)
        sp._enter_special = MagicMock(return_value=True)
        sp.screenshot = MagicMock()
        sp.appear = MagicMock(return_value=False)
        sp.swipe = MagicMock(return_value=False)
        sp.S_SP_DOWN = MagicMock()
        sp.I_SP_BUY_TOTEM = MagicMock()
        sp.I_SP_BUY_MEDIUM = MagicMock()
        sp.I_SP_BUY_LOW = MagicMock()
        sp.I_SP_SWIPE_CHECK = MagicMock()
        with patch("tasks.RichMan.mall.special.Timer", _AlwaysReachedTimer):
            sp.execute_special(SpecialRoom(enable=True))

        # RichMan/Shrine & ThousandThings 超时保护
        shrine = Shrine.__new__(Shrine)
        shrine.goto_page = MagicMock()
        with patch("tasks.RichMan.shrine.Timer", _AlwaysReachedTimer):
            shrine.execute_shrine(ShrineConfig(enable=True))

        tt = ThousandThings.__new__(ThousandThings)
        tt.goto_page = MagicMock()
        with patch("tasks.RichMan.thousand_things.Timer", _AlwaysReachedTimer):
            tt.execute_tt(ThousandThingsConfig(enable=True))

        # AreaBoss start_fight 超时返回 False
        ab = AreaBossTask.__new__(AreaBossTask)
        ab.check_can_run = MagicMock()
        ab.I_FIRE = MagicMock()
        ab.I_AB_CLOSE_RED = MagicMock()
        with patch("tasks.AreaBoss.script_task.Timer", _AlwaysReachedTimer):
            self.assertFalse(ab.start_fight())

        # DemonEncounter _box 超时退出
        de = DemonEncounterTask.__new__(DemonEncounterTask)
        de.config = SimpleNamespace(demon_encounter=SimpleNamespace(box_buy_config=SimpleNamespace(box_buy_sushi=False)))
        de.I_JADE_50 = MagicMock()
        with patch("tasks.DemonEncounter.script_task.Timer", _AlwaysReachedTimer):
            de._box(MagicMock())

        # RealmRaid check_refresh & fire_again 超时返回 False
        rr = RealmRaidTask.__new__(RealmRaidTask)
        rr.screenshot = MagicMock()
        rr.appear = MagicMock(return_value=True)
        rr.I_FRESH = MagicMock()
        rr.I_FRESH_ENSURE = MagicMock()
        rr.I_FIRE_AGAIN = MagicMock()
        rr.wait_until_appear = MagicMock()
        with patch("tasks.RealmRaid.script_task.Timer", _AlwaysReachedTimer):
            self.assertFalse(rr.check_refresh(screenshot=False))
            self.assertFalse(rr.fire_again())

        # AbyssShadows check_available & open_navigation 超时返回 False
        abyss = AbyssShadowsTask.__new__(AbyssShadowsTask)
        abyss.change_area = MagicMock(return_value=True)
        abyss.screenshot = MagicMock()
        abyss.I_CHECK_FINISH = MagicMock()
        abyss.I_ABYSS_MAP = MagicMock()
        abyss.I_ABYSS_NAVIGATION = MagicMock()
        abyss.I_ABYSS_FIRE = MagicMock()
        abyss.I_ABYSS_GOTO_ENEMY = MagicMock()
        with patch("tasks.AbyssShadows.script_task.Timer", _AlwaysReachedTimer):
            self.assertFalse(abyss.open_navigation())
            self.assertFalse(abyss.check_available(Code("A-1")))


if __name__ == "__main__":
    unittest.main()
