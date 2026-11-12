# This Python file uses the following encoding: utf-8
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np

from module.exception import TaskEnd
from tasks.Component.GeneralInvite.config_invite import InviteConfig
from tasks.Component.GeneralInvite.general_invite import RoomType
from tasks.GameUi.default_pages import page_reward
from tasks.GameUi.session import NavigatorSession
from tasks.Orochi.config import Orochi, UserStatus
from tasks.Orochi.script_task import ScriptTask as OrochiTask


def _build_orochi_stub() -> OrochiTask:
    task = object.__new__(OrochiTask)
    task.device = MagicMock()
    task.device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
    task.device.image_frame_id = 1
    task.interval_timer = {}
    task.animates = {}
    task.start_time = datetime.now()
    task.navigator = NavigatorSession(task_category="orochi")
    orochi_cfg = Orochi()
    orochi_cfg.orochi_config.user_status = UserStatus.MEMBER
    orochi_cfg.orochi_config.soul_buff_enable = True
    orochi_cfg.orochi_config.limit_count = 3
    task.config = MagicMock()
    task.config.orochi = orochi_cfg
    return task


class TestOrochiTeamRoom(unittest.TestCase):

    def test_orochi_member_in_room_skips_switch_soul_goto_main_and_courtyard_buff(self):
        task = _build_orochi_stub()
        call_order = []

        with patch.object(task, "screenshot", return_value=task.device.image), \
             patch.object(task, "is_in_room", return_value=True), \
             patch.object(task, "is_in_battle", return_value=False), \
             patch.object(task, "switch_orochi_souls", side_effect=lambda: call_order.append(("switch_soul", None))), \
             patch.object(task, "goto_page", side_effect=lambda dest, *a, **kw: call_order.append(("goto", dest.key))), \
             patch.object(task, "open_buff", side_effect=lambda: call_order.append(("open_buff", None))), \
             patch.object(task, "soul", side_effect=lambda is_open=True, **kw: call_order.append(("soul", is_open))), \
             patch.object(task, "close_buff", side_effect=lambda: call_order.append(("close_buff", None))), \
             patch.object(task, "run_member", side_effect=lambda: call_order.append(("run_member", None)) or True), \
             patch.object(task, "set_next_run"):
            with self.assertRaises(TaskEnd):
                task.run()

        self.assertTrue(task._custom_pages_registered)
        self.assertEqual(
            call_order,
            [
                ("run_member", None),
                ("goto", "page_main"),
                ("open_buff", None),
                ("soul", False),
                ("close_buff", None),
            ],
        )

    def test_orochi_exit_matcher_and_custom_reward_page_recognize_i_gi_in_room_and_sure(self):
        task = _build_orochi_stub()
        task._register_custom_pages()

        with patch.object(task, "appear", side_effect=lambda target: target is task.I_GI_IN_ROOM):
            self.assertTrue(task._team_exit_matcher().evaluate(task))
            self.assertTrue(task._exit_matcher().evaluate(task))

        reward_page = task.navigator.resolve_page(page_reward)
        self.assertIsNotNone(reward_page)
        with patch.object(task, "appear", side_effect=lambda target: target is task.I_GI_SURE), \
             patch.object(task, "ocr_appear", return_value=False):
            self.assertTrue(reward_page.recognizer.evaluate(task))

    def test_orochi_leader_in_room_skips_switch_soul_goto_main_and_create_room(self):
        task = _build_orochi_stub()
        self.assertEqual(task.default_room_type, RoomType.NORMAL_3)
        task.config.orochi.orochi_config.user_status = UserStatus.LEADER
        task.config.orochi.orochi_config.soul_buff_enable = False
        task.config.orochi.orochi_config.limit_count = 1
        task.config.orochi.invite_config = InviteConfig(friend_list="", default_invite=True)

        in_room = True
        goto_calls = []

        def fake_appear(rule, *args, **kwargs):
            if not in_room:
                return False
            return rule in (
                task.I_GI_IN_ROOM,
                task.I_ADD_2,
                task.I_LOCK,
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
             patch.object(task, "switch_orochi_souls") as mock_switch_soul, \
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
        mock_switch_soul.assert_not_called()
        mock_create_room.assert_not_called()
        mock_invite_friends.assert_not_called()
        mock_battle.assert_called_once()
        mock_exit_room.assert_called_once()


if __name__ == "__main__":
    unittest.main()

