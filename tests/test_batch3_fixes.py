# This Python file uses the following encoding: utf-8
from __future__ import annotations

import json
import pathlib
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from module.atom.click import RuleClick
from module.atom.image import RuleImage
from module.exception import GameStuckError, TaskEnd
from module.server.log_stats import LogStatsParser
from tasks.AutoCheckinBigGod.manual_claim import ManualClaimMixin
from tasks.AutoCheckinBigGod.script_task import ScriptTask as AutoCheckinScriptTask
from tasks.BondlingFairyland.script_task import ScriptTask as BondlingTask
from tasks.Chess.script_task import ScriptTask as ChessTask
from tasks.CollectiveMissions.script_task import ScriptTask as CollectiveMissionsTask
from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.BaseActivity.exceptions import LimitCountOut, LimitTimeOut, TicketsNotEnough
from tasks.Component.Buy.buy import Buy
from tasks.Component.BuyWindow.buy_window import BuyWindow
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralBuff.general_buff import GeneralBuff
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.Component.ReplaceShikigami.replace_shikigami import ReplaceShikigami
from tasks.Component.Summon.summon import Summon
from tasks.Component.SwitchAccount.login_account import LoginAccount
from tasks.Component.SwitchAccount.switch_account_config import AccountInfo
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.DemonRetreat.script_task import ScriptTask as DemonRetreatTask
from tasks.Dokan.script_task import ScriptTask as DokanTask
from tasks.Duel.script_task import ScriptTask as DuelTask
from tasks.MartialTournament import script_task as mt_mod
from tasks.MetaDemon.script_task import ScriptTask as MetaDemonTask
from tasks.TrueOrochi.script_task import ScriptTask as TrueOrochiTask


class _ReachedTimer:
    """Deterministic fake Timer that reaches on first check after start()."""

    def __init__(self, *args, **kwargs):
        self._started = False
        self._checks = 0

    def start(self):
        self._started = True
        return self

    def started(self):
        return self._started

    def reset(self):
        self._started = True
        self._checks = 0
        return self

    def reached(self):
        self._checks += 1
        return True

    def reached_and_reset(self):
        return True


def _make_base_stub(cls):
    obj = cls.__new__(cls)
    obj.device = SimpleNamespace(
        image=None,
        image_frame_id=1,
        click_record_clear=MagicMock(),
        stuck_record_clear=MagicMock(),
        stuck_record_add=MagicMock(),
        click=MagicMock(),
        swipe=MagicMock(),
    )
    obj.config = MagicMock()
    obj.screenshot = MagicMock()
    obj.appear = MagicMock(return_value=False)
    obj.appear_then_click = MagicMock(return_value=False)
    obj.click = MagicMock(return_value=False)
    obj.swipe = MagicMock()
    obj.wait_until_appear = MagicMock(return_value=False)
    obj.wait_until_disappear = MagicMock(return_value=False)
    obj.wait_until_stable = MagicMock(return_value=False)
    obj.wait_until_pos_stable = MagicMock(return_value=False)
    obj.ocr_appear = MagicMock(return_value=False)
    obj.ocr_appear_click = MagicMock(return_value=False)
    obj.ui_click = MagicMock()
    obj.ui_click_until_disappear = MagicMock(return_value=False)
    obj.ui_click_until_smt_disappear = MagicMock(return_value=False)
    obj.ui_reward_appear_click = MagicMock(return_value=False)
    return obj


class TestLogStatsBidirectional(unittest.TestCase):
    def test_chinese_and_english_banners_both_parsed(self):
        lines = [
            "══════════════════════════════════════════════════════════",
            "─────────────────────────── 启动 ───────────────────────────",
            "══════════════════════════════════════════════════════════",
            "2026-11-11 08:00:00.000 | INFO | [Task] DailyTrifles (2026-11-11)",
            "══════════════════════════════════════════════════════════",
            "──────────────────── 每日琐事 [DailyTrifles] ────────────────────",
            "══════════════════════════════════════════════════════════",
            "2026-11-11 08:00:01.000 | INFO | step 1",
            "─────────────────────── 战斗开始 ───────────────────────",
            "2026-11-11 08:00:05.000 | INFO | fighting",
            "2026-11-11 08:00:10.000 | INFO | DailyTrifles 任务结束",
            "══════════════════════════════════════════════════════════",
            "───────────────────────── 六道之门 ─────────────────────────",
            "══════════════════════════════════════════════════════════",
            "2026-11-11 08:00:11.000 | INFO | sr enter",
            "═══════════════════ 月之海 ═══════════════════",
            "2026-11-11 08:00:21.000 | INFO | sr end",
        ]
        stats = LogStatsParser.parse_lines(lines, script_name="oas1")
        self.assertIn("DailyTrifles", stats["tasks"])
        self.assertEqual(stats["tasks"]["DailyTrifles"]["run_count"], 1)
        self.assertEqual(stats["tasks"]["DailyTrifles"]["battle"]["count"], 1)
        self.assertIn("MoonSea", stats["tasks"])
        self.assertEqual(stats["tasks"]["MoonSea"]["run_count"], 1)
        self.assertEqual(stats["total_battle_count"], 2)

        en_lines = [
            "══════════════════════════════════════════════════════════",
            "─────────────────────────── START ───────────────────────────",
            "══════════════════════════════════════════════════════════",
            "2026-11-11 09:00:00.000 | INFO | [Task] Orochi (2026-11-11)",
            "══════════════════════════════════════════════════════════",
            "────────────────────────── Orochi ──────────────────────────",
            "══════════════════════════════════════════════════════════",
            "2026-11-11 09:00:01.000 | INFO | enter",
            "─────────────────── GENERAL BATTLE START ───────────────────",
            "2026-11-11 09:00:06.000 | INFO | fighting",
            "2026-11-11 09:00:12.000 | INFO | Orochi task ended",
        ]
        en_stats = LogStatsParser.parse_lines(en_lines, script_name="oas1")
        self.assertIn("Orochi", en_stats["tasks"])
        self.assertEqual(en_stats["tasks"]["Orochi"]["battle"]["count"], 1)


class TestComponentLoopGuards(unittest.TestCase):
    def test_base_activity_enter_battle_generic_times_out(self):
        act = _make_base_stub(BaseActivity)
        act._current_climb_type = "pass"
        act.is_in_battle = MagicMock(return_value=False)
        act.is_ticket_buy_window = MagicMock(return_value=False)
        act.click_fire_button = MagicMock(return_value=False)
        with patch("tasks.Component.BaseActivity.base_activity.Timer", _ReachedTimer):
            with self.assertRaises(TicketsNotEnough):
                act.enter_battle_generic()

    def test_buy_component_timeouts_return_false(self):
        buy = _make_base_stub(Buy)
        check_img = MagicMock(spec=RuleImage)
        start_btn = MagicMock(spec=RuleImage)
        with patch("tasks.Component.Buy.buy.Timer", _ReachedTimer):
            self.assertFalse(buy.buy_one(start_btn, check_img))
            self.assertFalse(buy.buy_more(start_btn))

    def test_general_buff_and_room_timeouts(self):
        buff = _make_base_stub(GeneralBuff)
        room = _make_base_stub(GeneralRoom)
        room.I_CHECK_TEAM = MagicMock()
        with patch("tasks.Component.GeneralBuff.general_buff.Timer", _ReachedTimer):
            buff.open_buff()
            buff.close_buff()
            buff.reject_invite()
        with patch("tasks.Component.GeneralRoom.general_room.Timer", _ReachedTimer):
            self.assertFalse(room.ensure_private())
            self.assertFalse(room.ensure_public())
            room.appear = MagicMock(side_effect=lambda r, *a, **kw: r is room.I_CHECK_TEAM)
            self.assertFalse(room.exit_team())
            room.appear = MagicMock(return_value=False)
            self.assertFalse(room.create_room())

    def test_summon_timeouts(self):
        sm = _make_base_stub(Summon)
        sm.O_ONE_TICKET = MagicMock()
        sm.O_ONE_TICKET.ocr.return_value = "10"
        with patch("tasks.Component.Summon.summon.Timer", _ReachedTimer):
            self.assertFalse(sm.summon_one())
            sm.back_summon_main()

    def test_switch_soul_by_name_breaks_on_repeated_or_timeout(self):
        ss = _make_base_stub(SwitchSoul)
        ss.O_SS_GROUP_NAME = MagicMock()
        ss.O_SS_GROUP_NAME.detect_and_ocr.return_value = [SimpleNamespace(ocr_text="其他分组")]
        with patch("tasks.Component.SwitchSoul.switch_soul.Timer", _ReachedTimer), \
             patch("tasks.Component.SwitchSoul.switch_soul.sleep", return_value=None):
            self.assertFalse(ss.switch_soul_by_name("不存在分组", "队伍1"))

    def test_replace_shikigami_and_general_battle_timeouts(self):
        from tasks.Utils.config_enum import ShikigamiClass

        rs = _make_base_stub(ReplaceShikigami)
        gb = _make_base_stub(GeneralBattle)
        gb.appear = MagicMock(side_effect=lambda rule, *a, **kw: rule is gb.I_EXIT)
        with patch("tasks.Component.ReplaceShikigami.replace_shikigami.Timer", _ReachedTimer):
            rs.switch_shikigami_class(ShikigamiClass.N)
            rs.unset_shikigami_max_lv()
        with patch("tasks.Component.GeneralBattle.general_battle.Timer", _ReachedTimer):
            self.assertFalse(gb.exit_battle())
            gb.check_lock(True, MagicMock(), MagicMock())
            gb.green_mark_choose()

    def test_general_invite_and_login_account_timeouts(self):
        gi = _make_base_stub(GeneralInvite)
        gi.appear_accept = MagicMock(return_value=True)
        gi.is_in_room = MagicMock(return_value=False)
        with patch("tasks.Component.GeneralInvite.general_invite.Timer", _ReachedTimer):
            self.assertFalse(gi.ensure_enter())
            self.assertFalse(gi.click_fire())
            self.assertFalse(gi.invite_again())
            self.assertFalse(gi.check_then_accept())

        la = _make_base_stub(LoginAccount)
        la.O_SA_ACCOUNT_ACCOUNT_SELECTED = MagicMock()
        la.O_SA_LOGIN_FORM_USER_CENTER_ACCOUNT = MagicMock()
        acc = AccountInfo(account="user@example.com", character="TestChar")
        with patch("tasks.Component.SwitchAccount.login_account.Timer", _ReachedTimer):
            self.assertFalse(la.login(acc))
            self.assertFalse(la.ui_click_until_disappear(MagicMock(spec=RuleClick)))


class TestTaskReuseAndGuards(unittest.TestCase):
    def test_martial_tournament_reuses_shared_exceptions_and_buy_window(self):
        self.assertIs(mt_mod.LimitTimeOut, LimitTimeOut)
        self.assertIs(mt_mod.LimitCountOut, LimitCountOut)
        self.assertIs(mt_mod.TicketsNotEnough, TicketsNotEnough)
        self.assertTrue(issubclass(mt_mod.ScriptTask, BuyWindow))

        mt = _make_base_stub(mt_mod.ScriptTask)
        mt.current_mode = "pass"
        mt.is_in_battle = MagicMock(return_value=False)
        mt.is_ticket_buy_window = MagicMock(return_value=True)
        mt.close_ticket_buy_window = MagicMock(return_value=True)
        with patch("time.sleep", return_value=None):
            with self.assertRaises(TicketsNotEnough):
                mt.enter_battle()
        mt.appear_then_click.assert_not_called()

        mt.is_ticket_buy_window = MagicMock(return_value=False)
        with patch("tasks.MartialTournament.script_task.Timer", _ReachedTimer):
            with self.assertRaises(TicketsNotEnough):
                mt.enter_ap_battle()

        mt.check_lock = MagicMock()
        conf = SimpleNamespace(lock_team_enable=True)
        mt.lock_team(conf)
        mt.check_lock.assert_called_once_with(True, mt.I_LOCK, mt.I_UNLOCK)

    def test_collective_missions_empty_ocr_and_timeout(self):
        cm = _make_base_stub(CollectiveMissionsTask)
        cm.O_SL_NUMBER = MagicMock()
        cm.O_SL_NUMBER.ocr.return_value = "无数字"
        cm.C_CM_1 = MagicMock()
        cm.I_SL_SUBMIT = MagicMock()
        cm.I_UI_BACK_RED = MagicMock()
        cm.I_CM_RECORDS = MagicMock()

        calls = {"n": 0}

        class _AfterOne(_ReachedTimer):
            def reached(self):
                calls["n"] += 1
                return calls["n"] > 1

        with patch("tasks.CollectiveMissions.script_task.Timer", _AfterOne):
            self.assertFalse(cm._soul())

    def test_dokan_find_all_element_stops_on_zero_offset(self):
        dk = _make_base_stub(DokanTask)
        dk.appear = MagicMock(return_value=False)
        item = SimpleNamespace(roi_back=(0, 0, 50, 50), roi_front=(0, 0, 50, 50))
        self.assertEqual(dk.find_all_element(item, offset=(0, 0, 0, 0)), [])

    def test_selected_tasks_timeouts_prevent_infinite_loops(self):
        to = _make_base_stub(TrueOrochiTask)
        to.config = SimpleNamespace(
            true_orochi=SimpleNamespace(
                switch_soul=SimpleNamespace(enable=False, enable_switch_by_name=False),
                true_orochi_config=SimpleNamespace(current_success=0, find_true_orochi=False),
            )
        )
        to.appear = MagicMock(side_effect=lambda r, *a, **kw: r is to.I_ST_MODULE)
        to.check_true_orochi = MagicMock(return_value=True)
        to.goto_page = MagicMock()
        with patch("tasks.TrueOrochi.script_task.Timer", _ReachedTimer):
            with self.assertRaises(GameStuckError):
                to.run()

        ch = _make_base_stub(ChessTask)
        with patch("tasks.Chess.script_task.Timer", _ReachedTimer):
            with self.assertRaises(GameStuckError):
                ch._wait_for_round_start()

        duel = _make_base_stub(DuelTask)
        duel.check_and_get_reward = MagicMock()
        duel.duel_main = MagicMock(return_value=False)
        duel.goto_page = MagicMock()
        duel.can_start_duel = MagicMock(return_value=True)
        duel.prepare_duel = MagicMock()
        duel.set_next_run = MagicMock()
        from tasks.Duel.config import Duel as DuelCfg
        duel.config = SimpleNamespace(duel=DuelCfg())
        fake_now = MagicMock()
        fake_now.now.return_value = datetime(2026, 11, 11, 14, 0, 0)
        with patch("tasks.Duel.script_task.datetime", fake_now):
            with self.assertRaises(TaskEnd):
                duel.run()
        self.assertEqual(duel.duel_main.call_count, 5)

        bf = _make_base_stub(BondlingTask)
        dr = _make_base_stub(DemonRetreatTask)
        dr.goto_page = MagicMock()
        md = _make_base_stub(MetaDemonTask)
        md.start_time = datetime.now()
        md.limit_time = timedelta(minutes=30)
        with patch("tasks.BondlingFairyland.script_task.Timer", _ReachedTimer):
            bf.lock_team()
        with patch("tasks.DemonRetreat.script_task.Timer", _ReachedTimer):
            self.assertFalse(dr.goto_demon_retreat())
        with patch("tasks.MetaDemon.script_task.Timer", _ReachedTimer):
            self.assertFalse(md.check_and_switch_ticket())
            self.assertFalse(md.battle_wait(False))

    def test_auto_checkin_manual_claim_checks_timeout_at_top_of_loop(self):
        mc = _make_base_stub(ManualClaimMixin)
        mc._check_adb_connection = MagicMock(return_value=True)
        mc._init_portrait = MagicMock()
        mc._launch_app_foreground = MagicMock(return_value=True)
        mc._cleanup_portrait = MagicMock()
        mc._screenshot_safe = MagicMock()
        mc._appear_then_click = MagicMock(return_value=True)
        mc.set_next_run = MagicMock()
        from module.exception import TaskEnd
        with patch("tasks.AutoCheckinBigGod.manual_claim.Timer", _ReachedTimer):
            with self.assertRaises(TaskEnd):
                mc._run_manual_claim()
        # Because timeout check happens before A.I_CIRCLE continue branch, loop breaks on tick 1
        mc._screenshot_safe.assert_not_called()

    def test_auto_checkin_ping_frida_repl_sets_timed_out_flag(self):
        svc = AutoCheckinScriptTask.__new__(AutoCheckinScriptTask)

        class _FakeProc:
            def __init__(self):
                self.stdin = MagicMock()
                self.stdout = MagicMock()
                self.stdout.readline.return_value = b""

        self.assertFalse(svc._ping_frida_repl(_FakeProc(), timeout=0.05))


class TestEngineeringHygieneAndDocs(unittest.TestCase):
    def test_no_third_party_cached_property_imports(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        offenders = []
        for sub in ("script.py", "server.py", "module", "tasks", "dev_tools"):
            target = root / sub
            paths = [target] if target.is_file() else target.rglob("*.py")
            for p in paths:
                if "__pycache__" in p.parts:
                    continue
                txt = p.read_text(encoding="utf-8", errors="replace")
                if "from cached_property import" in txt:
                    offenders.append(str(p.relative_to(root)))
        self.assertEqual(offenders, [])

    def test_i18n_sync_and_oasx_assets_match_root(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        for lang in ("zh-CN.json", "en-US.json"):
            root_data = json.loads((root / "assets" / "i18n" / lang).read_text(encoding="utf-8"))
            oasx_data = json.loads((root / "OASX-master" / "assets" / "i18n" / lang).read_text(encoding="utf-8"))
            self.assertEqual(root_data, oasx_data)

    def test_make_patch_excludes_scratch_and_has_launcher_fallbacks(self):
        from docs.make_patch import generate_apply_bat, is_excluded

        self.assertTrue(is_excluded("scratch/temp.py"))
        self.assertTrue(is_excluded("tests/test_batch3_fixes.py"))
        bat = generate_apply_bat()
        self.assertIn("deploy\\launcher\\oas-backend.bat", bat)
        self.assertIn("toolkit\\python.exe", bat)

    def test_deploy_ports_and_dockerfiles_aligned_to_7788(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        from deploy.config import ConfigModel as DeployCfg

        self.assertEqual(DeployCfg().WebuiPort, 7788)
        df_cn = (root / "deploy" / "docker" / "Dockerfile.cn").read_text(encoding="utf-8")
        self.assertIn("CMD python server.py", df_cn)
        self.assertIn("7788:7788", df_cn)


if __name__ == "__main__":
    unittest.main()
