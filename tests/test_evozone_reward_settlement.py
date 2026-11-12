# This Python file uses the following encoding: utf-8
import time
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from module.exception import TaskEnd
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import BattleAction, BattleContext, GeneralBattle
from tasks.Component.GeneralInvite.assets import GeneralInviteAssets
from tasks.Component.GeneralInvite.config_invite import InviteConfig
from tasks.Component.GeneralInvite.general_invite import GeneralInvite, RoomType
from tasks.EvoZone.config import EvoZone, UserStatus
from tasks.EvoZone.script_task import ScriptTask as EvoZoneTask
from tasks.GameUi.default_pages import (
    handle_battle_reward_page,
    page_battle_prepare,
    page_battle_result,
    page_battle_team,
    page_main,
    page_reward,
)
from tasks.GameUi.navigator import GameUi
from tasks.GameUi.page_definition import Page
from tasks.GameUi.session import NavigatorSession


class _DummyGameUi(GameUi):
    """隔离资产扫描与设备截图的 GameUi 测试桩。"""

    def __init__(self):
        self.device = MagicMock()
        self.device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.device.image_frame_id = 1
        self.config = MagicMock()
        self.interval_timer = {}
        self.animates = {}
        self.navigator = NavigatorSession(task_category="evo_zone")

    def screenshot(self):
        return self.device.image


class TestEvoZoneRewardSettlement(unittest.TestCase):

    def test_goto_page_retries_reward_page_instead_of_stalling(self):
        nav_ui = _DummyGameUi()
        reward_hook = MagicMock(return_value=True)
        reward_stub = Page(lambda _task: False, key=page_reward.key, name="page_reward", register=False)
        reward_stub.add_enter_success_hooks(reward_hook)
        main_stub = Page(lambda _task: False, key=page_main.key, name="page_main", register=False)
        nav_ui.navigator.bootstrap([reward_stub, main_stub])

        # 前 3 次仍在 page_reward（模拟首点击仅跳过开箱动画），第 4 次才退出到 page_main
        with patch.object(nav_ui, "_refresh_current_page", side_effect=[reward_stub, reward_stub, reward_stub, main_stub]), \
             patch.object(nav_ui, "close_unknown_pages") as mock_close, \
             patch.object(nav_ui, "_finalize_arrival", return_value=True) as mock_finalize, \
             patch("tasks.GameUi.navigator.time.sleep"):
            ok = nav_ui.goto_page(main_stub, timeout=30, total_timeout=60, none_buffer_time=0)

        self.assertTrue(ok)
        self.assertEqual(reward_hook.call_count, 3)
        mock_close.assert_not_called()
        mock_finalize.assert_called_once()

    def test_goto_page_clears_battle_enter_key_after_leaving_battle_prepare(self):
        nav_ui = _DummyGameUi()
        prepare_stub = Page(lambda _task: False, key=page_battle_prepare.key, name="page_battle_prepare", register=False)
        result_stub = Page(lambda _task: False, key=page_battle_result.key, name="page_battle_result", register=False)

        def fake_battle_hook(_task):
            nav_ui.navigator.current_page = result_stub
            return True

        prepare_stub.add_enter_success_hooks(fake_battle_hook)
        nav_ui.navigator.bootstrap([prepare_stub, result_stub])

        ran = nav_ui._run_enter_success_hooks_if_needed(prepare_stub)
        self.assertTrue(ran)
        self.assertIsNone(nav_ui.navigator.last_enter_success_page_key)
        # 若后续又遇到新一轮准备页，必须允许再次接管而不是跳过
        ran_again = nav_ui._run_enter_success_hooks_if_needed(prepare_stub)
        self.assertTrue(ran_again)

    def test_handle_battle_reward_page_handles_skin_confirm_and_invite_cancel(self):
        task = MagicMock()
        task.appear_then_click.side_effect = [False, True]
        self.assertTrue(handle_battle_reward_page(task))

        task.reset_mock()
        task.appear_then_click.side_effect = [False, False, True]
        task.appear.return_value = True
        self.assertTrue(handle_battle_reward_page(task))

    def test_general_battle_waits_longer_between_result_and_reward(self):
        gb = GeneralBattle.__new__(GeneralBattle)
        cfg = GeneralBattleConfig()
        ctx = SimpleNamespace(
            last_page=page_battle_result,
            reward_no_battle_ts=time.time() - 3.0,
            is_win=True,
        )
        # 结算页刚点掉后 3.0s 仍处于奖励盒掉落动画窗口，不应提前退出
        self.assertEqual(gb._handle_missing_battle_page(ctx, cfg, None), BattleAction.CONTINUE)

        # 超过 5.0s 后才作为兜底退出
        ctx.reward_no_battle_ts = time.time() - 5.2
        self.assertEqual(gb._handle_missing_battle_page(ctx, cfg, None), BattleAction.EXIT_WIN)

        # 已经出现并离开 page_reward 后仍保持 2.5s 快速兜底
        ctx.last_page = page_reward
        ctx.reward_no_battle_ts = time.time() - 2.7
        self.assertEqual(gb._handle_missing_battle_page(ctx, cfg, None), BattleAction.EXIT_WIN)

    def test_evozone_custom_pages_exit_matcher_and_pet_present(self):
        task = EvoZoneTask.__new__(EvoZoneTask)
        task.navigator = NavigatorSession(task_category="evo_zone")
        task.navigator.bootstrap([page_reward])
        task._custom_pages_registered = False
        task._register_custom_pages()

        resolved = task.navigator.resolve_page(page_reward)
        self.assertIsNotNone(resolved)
        self.assertIsNotNone(task._exit_matcher())

        task.config = SimpleNamespace(evo_zone=SimpleNamespace(evo_zone_config=SimpleNamespace(user_status="member")))
        task.appear_then_click = MagicMock(return_value=True)
        action = task._handle_reward(SimpleNamespace(), GeneralBattleConfig())
        self.assertEqual(action, BattleAction.CONTINUE)
        task.appear_then_click.assert_called_once_with(task.I_PET_PRESENT, action=task.C_RANDOM_RIGHT, interval=1)


    def test_goto_page_rerefreshes_after_battle_prepare_enter_hook(self):
        ui = _DummyGameUi()
        battle_prepare = Page(page_battle_prepare.recognizer, key="page_battle_prepare", name="page_battle_prepare", register=False)
        dest = Page(page_main.recognizer, key="page_main", name="page_main", register=False)
        states = iter([battle_prepare, dest])

        with patch.object(ui, "_refresh_current_page", side_effect=lambda *args, **kwargs: next(states)) as mock_refresh, \
             patch.object(ui, "_run_enter_success_hooks_if_needed", side_effect=lambda page, *args, **kwargs: page.key == "page_battle_prepare") as mock_hooks, \
             patch.object(ui, "close_unknown_pages") as mock_close:
            ui.goto_page(dest)

        self.assertEqual(mock_refresh.call_count, 2)
        self.assertGreaterEqual(mock_hooks.call_count, 1)
        mock_close.assert_not_called()

    def test_general_invite_is_in_room_and_page_battle_team_match_i_gi_in_room(self):
        invite = object.__new__(GeneralInvite)
        with patch.object(invite, "appear", side_effect=lambda target: target is GeneralInviteAssets.I_GI_IN_ROOM):
            self.assertTrue(invite.is_in_room(is_screenshot=False))

        ui = _DummyGameUi()
        with patch.object(ui, "appear", side_effect=lambda target: target is GeneralInviteAssets.I_GI_IN_ROOM):
            self.assertTrue(page_battle_team.recognizer.evaluate(ui))

    def test_evozone_member_in_room_skips_goto_main_and_courtyard_buff(self):
        task = object.__new__(EvoZoneTask)
        task.device = MagicMock()
        task.device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        task.device.image_frame_id = 1
        task.interval_timer = {}
        task.animates = {}
        task._custom_pages_registered = True
        task.start_time = datetime.now()
        task.navigator = NavigatorSession(task_category="evo_zone")
        evo_cfg = EvoZone()
        evo_cfg.evo_zone_config.user_status = UserStatus.MEMBER
        evo_cfg.evo_zone_config.soul_buff_enable = True
        evo_cfg.evo_zone_config.limit_count = 3
        task.config = MagicMock()
        task.config.evo_zone = evo_cfg

        call_order = []

        def fake_goto(dest, *args, **kwargs):
            call_order.append(("goto", dest.key))

        def fake_open_buff():
            call_order.append(("open_buff", None))

        def fake_close_buff():
            call_order.append(("close_buff", None))

        def fake_awake(is_open: bool = True, **kwargs):
            call_order.append(("awake", is_open))

        def fake_run_member():
            call_order.append(("run_member", None))

        with patch.object(task, "screenshot", return_value=task.device.image), \
             patch.object(task, "is_in_room", return_value=True), \
             patch.object(task, "is_in_battle", return_value=False), \
             patch.object(task, "goto_page", side_effect=fake_goto), \
             patch.object(task, "open_buff", side_effect=fake_open_buff), \
             patch.object(task, "close_buff", side_effect=fake_close_buff), \
             patch.object(task, "awake", side_effect=fake_awake), \
             patch.object(task, "run_member", side_effect=fake_run_member), \
             patch.object(task, "set_next_run"):
            with self.assertRaises(TaskEnd):
                task.run()

        self.assertEqual(
            call_order,
            [
                ("run_member", None),
                ("goto", "page_main"),
                ("open_buff", None),
                ("awake", False),
                ("close_buff", None),
            ],
        )

    def test_evozone_leader_in_room_skips_goto_main_and_create_room_then_fires(self):
        task = object.__new__(EvoZoneTask)
        task.device = MagicMock()
        task.device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        task.device.image_frame_id = 1
        task.interval_timer = {}
        task.animates = {}
        task._custom_pages_registered = True
        task.start_time = datetime.now()
        task.navigator = NavigatorSession(task_category="evo_zone")
        evo_cfg = EvoZone()
        evo_cfg.evo_zone_config.user_status = UserStatus.LEADER
        evo_cfg.evo_zone_config.soul_buff_enable = False
        evo_cfg.evo_zone_config.limit_count = 1
        evo_cfg.invite_config = InviteConfig(friend_list="", default_invite=True)
        evo_cfg.general_battle_config.lock_team_enable = False
        task.config = MagicMock()
        task.config.evo_zone = evo_cfg

        in_room = True
        goto_calls = []

        def fake_appear(rule, *args, **kwargs):
            if not in_room:
                return False
            # 模拟截图中的队长组队房间：左上角协战队伍、1号位已有队友(I_ADD_1缺失)、2号位空闲、未锁阵容、可挑战
            return rule in (
                task.I_GI_IN_ROOM,
                task.I_ADD_2,
                task.I_UNLOCK,
                task.I_FIRE,
            )

        def fake_appear_then_click(rule, *args, **kwargs):
            nonlocal in_room
            if in_room and rule is task.I_FIRE:
                in_room = False
                return True
            return False

        def fake_battle(*args, **kwargs):
            nonlocal in_room
            task.current_count += 1
            in_room = True
            return True

        def fake_exit_room():
            nonlocal in_room
            in_room = False
            return True

        with patch.object(task, "screenshot", return_value=task.device.image), \
             patch.object(task, "appear", side_effect=fake_appear), \
             patch.object(task, "appear_then_click", side_effect=fake_appear_then_click), \
             patch.object(task, "goto_page", side_effect=lambda dest, *a, **kw: goto_calls.append(dest.key)), \
             patch.object(task, "create_room") as mock_create_room, \
             patch.object(task, "invite_friends") as mock_invite_friends, \
             patch.object(task, "run_general_battle", side_effect=fake_battle) as mock_battle, \
             patch.object(task, "exit_room", side_effect=fake_exit_room) as mock_exit_room, \
             patch.object(task, "exit_team", return_value=False), \
             patch.object(task, "set_next_run"):
            with self.assertRaises(TaskEnd):
                task.run()

        self.assertEqual(goto_calls, ["page_main"])
        mock_create_room.assert_not_called()
        mock_invite_friends.assert_not_called()
        mock_battle.assert_called_once()
        mock_exit_room.assert_called_once()

    def test_general_invite_3p_room_with_empty_friend_list_and_gi_sure_popup(self):
        task = object.__new__(EvoZoneTask)
        task.device = MagicMock()
        task.device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        task.device.image_frame_id = 1
        task.interval_timer = {}
        task.animates = {}

        # pre_type=NORMAL_3 且 1号位已有队友时，不能误退化为 NORMAL_2
        with patch.object(task.I_ADD_1, "match", return_value=False), \
             patch.object(task.I_ADD_2, "match", return_value=True), \
             patch.object(task.I_ADD_5_1, "match", return_value=False), \
             patch.object(task.I_LOCK_SEA, "match", return_value=False), \
             patch.object(task.I_UNLOCK_SEA, "match", return_value=False):
            self.assertEqual(task.check_room_type(task.device.image, pre_type=RoomType.NORMAL_3), RoomType.NORMAL_3)

        task.room_type = RoomType.NORMAL_3
        cfg_empty = InviteConfig(friend_list="", default_invite=True)
        # 房内已有1名队友（I_ADD_1=False, I_ADD_2=True）时允许直接开战
        with patch.object(task, "appear", side_effect=lambda r, *a, **kw: r is task.I_ADD_2):
            self.assertTrue(task.room_check_can_fire(cfg_empty))
        # 房内无人（I_ADD_1=True, I_ADD_2=True）时不允许误开战
        with patch.object(task, "appear", side_effect=lambda r, *a, **kw: r in (task.I_ADD_1, task.I_ADD_2)):
            self.assertFalse(task.room_check_can_fire(cfg_empty))

        # 确认 I_GI_IN_ROOM 在背景可见时，check_and_invite 仍会等点击完成 I_GI_SURE 弹窗
        step = {"default_checked": False, "sure_gone": False}

        def fake_appear(rule, *args, **kwargs):
            if rule is task.I_GI_IN_ROOM:
                return True
            if rule is task.I_GI_SURE:
                return not step["sure_gone"]
            if rule is task.I_I_NO_DEFAULT:
                return not step["default_checked"]
            if rule is task.I_I_DEFAULT:
                return step["default_checked"]
            return False

        def fake_click(rule, *args, **kwargs):
            if rule is task.I_I_NO_DEFAULT:
                step["default_checked"] = True
                return True
            if rule is task.I_GI_SURE:
                step["sure_gone"] = True
                return True
            return False

        with patch.object(task, "screenshot", return_value=task.device.image), \
             patch.object(task, "appear", side_effect=fake_appear), \
             patch.object(task, "appear_then_click", side_effect=fake_click), \
             patch("tasks.Component.GeneralInvite.general_invite.sleep"):
            self.assertTrue(task.check_and_invite(default_invite=True))
        self.assertTrue(step["default_checked"])
        self.assertTrue(step["sure_gone"])

    def test_dismiss_team_exit_prompt(self):
        task = object.__new__(EvoZoneTask)
        with patch.object(task, "appear", side_effect=lambda r: r is GeneralBattleAssets.I_GB_CHECK_TEAM_EXIT), \
             patch.object(task, "appear_then_click", return_value=True) as mock_click:
            self.assertTrue(task.dismiss_team_exit_prompt())
        mock_click.assert_called_once()


if __name__ == "__main__":
    unittest.main()

