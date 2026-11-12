# This Python file uses the following encoding: utf-8
import re
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from module.atom.click import RuleClick
from module.atom.image import RuleImage
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralInvite.config_invite import InviteConfig
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.Login.service import LoginService
from tasks.Component.ReplaceShikigami.replace_shikigami import ReplaceShikigami
from tasks.Component.SwitchAccount.login_account import LoginAccount
from tasks.Delegation.script_task import ScriptTask as DelegationTask
from tasks.Dokan.script_task import ScriptTask as DokanTask
from tasks.Duel.script_task import ScriptTask as DuelTask
from tasks.ExperienceYoukai.script_task import ScriptTask as ExpYoukaiTask
from tasks.FloatParade.script_task import ScriptTask as FloatParadeTask
from tasks.GameUi.page import page_battle_result, page_main, page_reward
from tasks.GoldYoukai.script_task import ScriptTask as GoldYoukaiTask
from tasks.KekkaiActivation.script_task import ScriptTask as KekkaiActivationTask
from tasks.KekkaiUtilize.script_task import ScriptTask as KekkaiUtilizeTask
from tasks.KittyShop.script_task import ScriptTask as KittyShopTask
from tasks.Orochi.script_task import ScriptTask as OrochiTask
from tasks.OtherWorldTwilight.script_task import ScriptTask as OtherWorldTwilightTask
from tasks.RealmRaid.script_task import ScriptTask as RealmRaidTask
from tasks.RichMan.mall.consignment import Consignment
from tasks.Secret.script_task import ScriptTask as SecretTask
from tasks.SixRealms.peacock_kingdom.base_peacock_kingdom import BasePeacockKingdom
from tasks.Tako.script_task import ScriptTask as TakoTask


class TestComponentFixes(unittest.TestCase):
    def test_base_activity_switch_soul_exits_shikigami_records(self):
        act = BaseActivity.__new__(BaseActivity)
        act._switch_souled_map = {}
        switch_conf = SimpleNamespace(
            enable_switch_ap=True,
            enable_switch_ap_by_name=False,
            ap_group_team="1,2",
            validate_switch_soul=MagicMock(),
        )
        act.config = SimpleNamespace(
            model=SimpleNamespace(activity_shikigami=SimpleNamespace(switch_soul_config=switch_conf))
        )
        act.get_climb_type_display_name = MagicMock(return_value="体力")
        act.ui_click = MagicMock()
        act.run_switch_soul = MagicMock()
        act.exit_shikigami_records = MagicMock()

        enter_btn = MagicMock(spec=RuleImage)
        check_img = MagicMock(spec=RuleImage)
        act.switch_soul_for_climb("ap", enter_btn, check_img)

        act.run_switch_soul.assert_called_once_with("1,2")
        act.exit_shikigami_records.assert_called_once()
        self.assertTrue(act._switch_souled_map["ap"])

    def test_general_battle_switch_preset_team_handles_team_5(self):
        gb = GeneralBattle.__new__(GeneralBattle)
        gb.C_PRESET_GROUP_1 = MagicMock(roi_back=(10, 10, 10, 10))
        gb.I_PRESET_ENSURE = MagicMock()
        gb.appear = MagicMock(return_value=True)
        gb.screenshot = MagicMock()
        gb.device = SimpleNamespace(image=np.zeros((100, 100, 3), dtype=np.uint8))

        with patch("tasks.Component.GeneralBattle.general_battle.color_similar", return_value=False), \
             patch("time.sleep", return_value=None):
            # Must not raise AttributeError when preset_team=5
            gb.switch_preset_team(enable=True, preset_group=1, preset_team=5)

    def test_general_invite_returns_false_when_panel_open_fails(self):
        gi = GeneralInvite.__new__(GeneralInvite)
        gi._open_invite_panel_if_needed = MagicMock(return_value=False)
        conf = InviteConfig(friend_list="Alice")
        self.assertFalse(gi.invite_friends(conf, open_invite=True))

    def test_login_service_does_not_mutate_zidu_roi_in_place(self):
        img = RuleImage((500, 400, 50, 50), (0, 0, 1280, 720), "Template matching", 0.8, "dummy.png")
        svc = LoginService.__new__(LoginService)
        svc.I_HARVEST_ZIDU = img
        svc.I_CHECK_MAIN = MagicMock()
        svc.I_MAIN_GOTO_SHIKIGAMI_RECORDS = MagicMock()
        svc.I_UI_CONFIRM_SAMLL = MagicMock()
        svc.I_LOGIN_LOAD_DOWN = MagicMock()
        svc.I_WATCH_VIDEO_CANCEL = MagicMock()
        svc.I_LOGIN_RED_CLOSE = MagicMock()
        svc.I_LOGIN_YELLOW_CLOSE = MagicMock()
        svc.I_LOGIN_LOGIN_GOTO_BIND_PHONE = MagicMock()

        loop_count = 0

        def fake_appear(rule, interval=None):
            return rule is img

        def fake_click(target, interval=None):
            nonlocal loop_count
            loop_count += 1
            return True

        svc.appear = MagicMock(side_effect=fake_appear)
        svc.appear_then_click = MagicMock(return_value=False)
        svc.click = MagicMock(side_effect=fake_click)
        svc.screenshot = MagicMock()

        # Simulate two iterations where I_HARVEST_ZIDU appears then break when confirm_timer finishes
        # Direct call pattern: check roi_front remains invariant across appear + click
        x, y, w, h = img.roi_front
        close_click = RuleClick((max(0, x - 200), max(0, y - 200), w, h), (max(0, x - 200), max(0, y - 200), w, h))
        svc.click(close_click)
        self.assertEqual(img.roi_front, [500, 400, 50, 50])

    def test_jump2select_account_calls_screenshot_and_times_out(self):
        la = LoginAccount.__new__(LoginAccount)
        la.I_SA_NETEASE_GAME_LOGO = MagicMock()
        la.I_SA_ACCOUNT_LOGIN_BTN = MagicMock()
        la.I_SA_SWITCH_ACCOUNT_BTN = MagicMock()
        la.I_CHECK_LOGIN_FORM = MagicMock()
        la.screenshot = MagicMock()
        la.appear = MagicMock(return_value=False)
        la.appear_then_click = MagicMock(return_value=False)

        self.assertFalse(la.jump2SelectAccount(timeout=0.05))
        la.screenshot.assert_called()


class TestTaskFixes(unittest.TestCase):
    def test_kekkai_utilize_guild_lottery_skips_missing_assets(self):
        ku = KekkaiUtilizeTask.__new__(KekkaiUtilizeTask)
        ku.guild_lottery()  # Should return safely without AttributeError

    def test_orochi_run_wild_uses_fallback_fire_without_attribute_error(self):
        oro = OrochiTask.__new__(OrochiTask)
        oro.I_OROCHI_FIRE = MagicMock()
        oro.I_PET_PRESENT = MagicMock()
        oro.I_CHECK_TEAM = MagicMock()
        oro.I_GI_SURE = MagicMock()
        oro.I_MATCHING = MagicMock()
        oro.I_CHECK_EXPLORATION = MagicMock()
        oro.config = SimpleNamespace(
            orochi=SimpleNamespace(
                orochi_config=SimpleNamespace(layer=10),
                invite_config=SimpleNamespace(default_invite=False),
                general_battle_config=MagicMock(),
            )
        )
        oro.current_count = 0
        oro.limit_count = 1
        oro.start_time = datetime.now()
        oro.limit_time = timedelta(minutes=10)
        oro.is_in_battle = MagicMock(return_value=True)
        oro.screenshot = MagicMock()
        oro.check_and_invite = MagicMock(return_value=False)
        oro.appear_then_click = MagicMock(side_effect=lambda rule, **kw: rule is oro.I_OROCHI_FIRE)
        oro.appear = MagicMock(return_value=False)
        oro.is_in_room = MagicMock(return_value=True)
        oro.run_general_battle = MagicMock(side_effect=lambda **kw: setattr(oro, "current_count", 1))
        oro.exit_room = MagicMock(return_value=False)
        oro.exit_team = MagicMock(return_value=False)

        self.assertTrue(oro.run_wild())
        oro.run_general_battle.assert_called_once()

    def test_realm_raid_handlers_resolve_page_imports(self):
        rr = RealmRaidTask.__new__(RealmRaidTask)
        rr.I_FALSE = MagicMock()
        rr.I_GB_SKIN_CONFIRM = MagicMock()
        rr.C_RANDOM_TOP = MagicMock()
        rr.device = MagicMock()
        rr.appear = MagicMock(return_value=False)
        rr.appear_then_click = MagicMock(return_value=False)
        rr.click = MagicMock()
        ctx = SimpleNamespace(reward_no_battle_ts=123, is_win=False, last_page=None)
        cfg = SimpleNamespace(quick_exit=False)
        rr._handle_result(ctx, cfg)
        rr._handle_reward(ctx, cfg)
        self.assertEqual(rr.device.click_record_clear.call_count, 2)

    def test_consignment_calls_buy_more_with_int_quantity(self):
        con = Consignment.__new__(Consignment)
        con.I_CON_ENTER = MagicMock()
        con.I_CON_ENTER_CHECK = MagicMock()
        con.I_CON_TICKET = MagicMock()
        con.O_CON_NUMBER = MagicMock()
        con.O_CON_NUMBER.ocr.return_value = 3
        con._enter_consignment = MagicMock()
        con.ui_click = MagicMock()
        con.screenshot = MagicMock()
        con.mall_check_money = MagicMock(return_value=True)
        con.buy_more = MagicMock()
        con.buy_one = MagicMock()
        con.device = SimpleNamespace(image=np.zeros((10, 10, 3), dtype=np.uint8))

        with patch("time.sleep", return_value=None):
            con.execute_consignment(SimpleNamespace(enable=True, buy_sale_ticket=True))

        con.buy_one.assert_not_called()
        con.buy_more.assert_called_once_with(con.I_CON_TICKET, 3)

    def test_float_parade_get_mileage_clicks_until_disappear(self):
        fp = FloatParadeTask.__new__(FloatParadeTask)
        fp.I_ENTRY_MILEAGE = MagicMock()
        fp.I_CLAIM_MILEAGE = MagicMock()
        fp.I_UI_BACK_RED = MagicMock()
        fp.screenshot = MagicMock()
        fp.appear = MagicMock(return_value=True)
        fp.ui_click_until_disappear = MagicMock()
        fp.ui_get_reward = MagicMock()

        fp.get_mileage()
        fp.ui_click_until_disappear.assert_any_call(fp.I_ENTRY_MILEAGE, interval=1.9)

    def test_room_wait_loops_respect_timer_when_outside_room(self):
        for cls, zone_attr, cfg_attr in [
            (GoldYoukaiTask, "gold_youkai", "gold_youkai"),
            (ExpYoukaiTask, "experience_youkai", "experience_youkai"),
            (TakoTask, "tako", "tako_config"),
        ]:
            task = cls.__new__(cls)
            task.before_run = MagicMock()
            task.goto_page = MagicMock()
            task.check_zones = MagicMock()
            task.create_room = MagicMock(return_value=True)
            task.ensure_public = MagicMock()
            task.create_ensure = MagicMock()
            task.screenshot = MagicMock()
            task.is_in_room = MagicMock(return_value=False)  # Would previously hang forever!
            task.exit_room = MagicMock()
            task.exit_task = MagicMock(side_effect=StopIteration)
            task.gold_exit = MagicMock(side_effect=StopIteration)
            task.experience_exit = MagicMock(side_effect=StopIteration)
            task.start_time = datetime.now()
            task.I_ADD_5_1 = MagicMock()
            task.I_ADD_1 = MagicMock()
            sub_conf = SimpleNamespace(
                buff_gold_50_click=False,
                buff_gold_100_click=False,
                buff_exp_50_click=False,
                buff_exp_100_click=False,
                enable=False,
            )
            task_conf = SimpleNamespace(
                switch_soul=SimpleNamespace(enable=False, enable_switch_by_name=False),
                **{cfg_attr: sub_conf},
            )
            task.config = SimpleNamespace(**{zone_attr: task_conf})

            fake_timer = MagicMock()
            fake_timer.start.return_value = fake_timer
            fake_timer.reached.return_value = True
            with patch(f"{cls.__module__}.Timer", return_value=fake_timer):
                with self.assertRaises(StopIteration):
                    task.run()

    def test_delegation_check_reward_does_not_hang_when_icon_missing(self):
        dlg = DelegationTask.__new__(DelegationTask)
        dlg.I_REWARDS_GET = MagicMock()
        dlg.I_REWARDS_CHAT = MagicMock()
        dlg.I_CHAT_1 = MagicMock()
        dlg.I_CHAT_2 = MagicMock()
        dlg.I_REWARDS_DONE = MagicMock()
        dlg.I_REWARDS_FALSE = MagicMock()
        dlg.I_REWARDS_MIN = MagicMock()
        dlg.screenshot = MagicMock()
        dlg.appear_then_click = MagicMock(return_value=False)
        dlg.appear = MagicMock(return_value=False)  # Previously infinite loop!

        fake_timer = MagicMock()
        fake_timer.start.return_value = fake_timer
        fake_timer.reached.return_value = True
        with patch("tasks.Delegation.script_task.Timer", return_value=fake_timer):
            dlg.check_reward()

    def test_other_world_twilight_unknown_page_timer_recovers(self):
        owt = OtherWorldTwilightTask.__new__(OtherWorldTwilightTask)
        owt.I_OWT_LOCK = MagicMock()
        owt.I_OWT_UNLOCK = MagicMock()
        owt.I_OWT_FIRE = MagicMock()
        owt.start_time = datetime.now()
        owt.current_count = 0
        owt.conf = SimpleNamespace(
            general_battle_config=SimpleNamespace(lock_team_enable=False),
            other_world_twilight_config=SimpleNamespace(limit_count=10, limit_time_v=timedelta(hours=1)),
        )
        owt.check_lock = MagicMock()
        owt.screenshot = MagicMock()
        owt.get_current_page = MagicMock(return_value=page_main)

        def stop_on_goto(page):
            if page is page_main or getattr(page, "name", "") != "":
                pass
            if owt.goto_page.call_count >= 2:
                raise StopIteration

        owt.goto_page = MagicMock(side_effect=stop_on_goto)
        with patch("tasks.OtherWorldTwilight.script_task.Timer") as mock_timer_cls:
            t_inst = MagicMock()
            t_inst.started.side_effect = [False, True]
            t_inst.reached.return_value = True
            mock_timer_cls.return_value = t_inst
            with self.assertRaises(StopIteration):
                owt.run_alone()
            self.assertEqual(owt.goto_page.call_count, 2)

    def test_kitty_shop_and_peacock_kingdom_skip_missing_assets(self):
        ks = KittyShopTask.__new__(KittyShopTask)
        ks.I_START_FARMING = MagicMock()
        ks.I_GO1 = MagicMock()
        ks.I_UI_BACK_YELLOW = MagicMock()
        ks.I_CHECK_MAIN = MagicMock()
        ks.config = SimpleNamespace(model=SimpleNamespace(kitty_shop=SimpleNamespace(kitty_shop_config=SimpleNamespace(kitty_attempts=0))))
        ks.goto_page = MagicMock()
        ks.screenshot = MagicMock()
        ks.appear = MagicMock(return_value=True)
        ks.appear_then_click = MagicMock(return_value=False)
        ks.ui_click = MagicMock()
        ks.set_next_run = MagicMock()
        from module.exception import TaskEnd
        with self.assertRaises(TaskEnd):
            ks.run()

        pk = BasePeacockKingdom.__new__(BasePeacockKingdom)
        self.assertEqual(pk.get_pk_skill_select_ocr(["倾城之舞"]), (None, None))

    def test_duel_check_honor_requires_positive_total(self):
        duel = DuelTask.__new__(DuelTask)
        duel.I_DUEL_HONOR = MagicMock(roi_front=(10, 20, 30, 40))
        duel.O_D_HONOR = MagicMock()
        duel.O_D_HONOR.ocr.return_value = (0, 0, 0)
        duel.appear = MagicMock(return_value=True)
        duel.device = SimpleNamespace(image=np.zeros((100, 100, 3), dtype=np.uint8))
        self.assertFalse(duel.check_honor())

    def test_kekkai_activation_handles_none_ocr_time(self):
        ka = KekkaiActivationTask.__new__(KekkaiActivationTask)
        ka.screenshot = MagicMock()
        ka.check_card_status = MagicMock(return_value=True)
        ka.check_card_effect = MagicMock(return_value=True)
        ka.ocr_time = MagicMock(return_value=None)
        ka.set_next_run = MagicMock()
        ka.goto_page = MagicMock()
        with patch("time.sleep", return_value=None):
            self.assertFalse(ka.run_activation(SimpleNamespace(card_type="taiko")))
        ka.set_next_run.assert_called_once()

    def test_dokan_empty_bounty_list_ignore_score_does_not_raise_index_error(self):
        dk = DokanTask.__new__(DokanTask)
        dk.I_RIGHTPAD_POINT_BOUNTY = MagicMock(roi_back=(0, 0, 100, 100))
        dk.I_CENTER_POINT_PEOPLE_NUMBER = MagicMock(roi_back=(0, 0, 100, 100))
        dk.S_DOKAN_LIST_UP = MagicMock()
        dk.C_DOKAN_REFRESH = MagicMock()
        dk.I_REFRESH_ENSURE = MagicMock()
        dk.screenshot = MagicMock()
        dk.find_all_element = MagicMock(return_value=[])
        dk.swipe = MagicMock()
        dk.ui_click = MagicMock()
        dk.ui_click_until_disappear = MagicMock()
        dk.config = SimpleNamespace(
            dokan=SimpleNamespace(
                dokan_config=SimpleNamespace(find_dokan_refresh_count=0),
                attack_count_config=MagicMock(),
            )
        )
        with patch("time.sleep", return_value=None):
            self.assertFalse(dk.find_dokan())

    def test_replace_shikigami_none_stop_image_does_not_skip_selection(self):
        rs = ReplaceShikigami.__new__(ReplaceShikigami)
        for i in range(1, 8):
            setattr(rs, f"C_SHIKIGAMI_LEFT_{i}", MagicMock())
        rs.I_U_CONFIRM_SMALL = MagicMock()
        rs.I_U_CIRCLE_ALTERNATE = MagicMock()
        rs.I_U_CONFIRM_ALTERNATE = MagicMock()
        rs.screenshot = MagicMock()
        rs.appear_then_click = MagicMock(return_value=False)
        rs.click = MagicMock(return_value=True)
        rs.set_shikigami(shikigami_order=7, stop_image=None)
        rs.click.assert_called_once()

    def test_secret_does_not_abort_when_ocr_text_empty(self):
        sec = SecretTask.__new__(SecretTask)
        sec.before_run = MagicMock()
        sec.check_time = MagicMock()
        sec.goto_page = MagicMock()
        sec.ui_click = MagicMock()
        sec.screenshot = MagicMock()
        sec.I_SE_ENTER = MagicMock()
        sec.I_SE_FIRE = MagicMock()
        sec.I_SE_PLACEMENT = MagicMock()
        sec.I_SE_FINISHED_1 = MagicMock()
        sec.O_SE_TOTAL_TIME = MagicMock()
        sec.O_SE_TOTAL_TIME.ocr_single.return_value = ""
        sec.device = SimpleNamespace(image=np.zeros((100, 100, 3), dtype=np.uint8))
        sec.appear = MagicMock(side_effect=lambda rule, **kw: rule in (sec.I_SE_PLACEMENT, sec.I_SE_FIRE))
        sec.find_battle = MagicMock(return_value=None)
        sec.set_next_run = MagicMock()
        sec.config = SimpleNamespace(
            secret=SimpleNamespace(
                secret_config=SimpleNamespace(secret_gold_50=False, secret_gold_100=False, layer_9=True, layer_10=True),
                switch_soul=SimpleNamespace(enable=False, enable_switch_by_name=False),
            )
        )
        from module.exception import TaskEnd
        with patch("time.sleep", return_value=None):
            with self.assertRaises(TaskEnd):
                sec.run()
        self.assertEqual(sec.find_battle.call_count, 10)

    def test_dokan_switch_soul_by_name_works_without_extra_config_field(self):
        dk = DokanTask.__new__(DokanTask)
        dk.switch_member_soul_done = False
        dk.config = SimpleNamespace(
            dokan=SimpleNamespace(
                dokan_member_switch_soul=SimpleNamespace(
                    enable=False,
                    enable_switch_by_name=True,
                    switch_group_team="1,1",
                    group_name="寮",
                    team_name="道馆",
                ),
                dokan_owner_switch_soul=SimpleNamespace(
                    enable=False,
                    enable_switch_by_name=False,
                    switch_group_team="1,1",
                    group_name="",
                    team_name="",
                ),
            )
        )
        dk.goto_page = MagicMock()
        dk.run_switch_soul_by_name = MagicMock()
        dk.switch_soul_in_dokan("member")
        dk.run_switch_soul_by_name.assert_called_once_with("寮", "道馆")
        self.assertTrue(dk.switch_member_soul_done)


if __name__ == "__main__":
    unittest.main()
