# -*- coding: utf-8 -*-
"""上游 P1 精选融入项离线回归测试（新语明霄主题 / 超鬼王 2025-2026 / WindowsClient 底层增强）。"""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from module.base.cBezier import human_track
from module.device.app_control import AppControl
from module.device.handle import EmulatorFamily
from module.device.method import windows_impl
from module.device.method.windows_impl import Window
from module.device.screenshot import Screenshot
from module.exception import GameNotRunningError, GameStuckError
from tasks.Component.Costume.config import CostumeConfig, ThemeType
from tasks.Component.Costume.costume_base import CostumeBase
from tasks.Component.CostumeTheme.assets import CostumeThemeAssets
from tasks.Component.CostumeTheme.theme import _THEME_NAMES, apply_theme
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import BattleAction, BattleContext, GeneralBattle
from tasks.Component.Login import service as login_service
from tasks.Component.Login.service import DESKTOP_MPAY_CLOSE_LIMIT, LoginService
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.navigator import GameUi
from tasks.MetaDemon.assets import MetaDemonAssets
from tasks.MetaDemon.config import MetaDemon, Strategy
from tasks.MetaDemon.script_task import ScriptTask as MetaDemonTask, Star56


class TestCostumeTheme(unittest.TestCase):
    def setUp(self):
        apply_theme(ThemeType.COSTUME_THEME_DEFAULT)

    def tearDown(self):
        apply_theme(ThemeType.COSTUME_THEME_DEFAULT)

    def test_theme_enum_and_legacy_validator(self):
        self.assertEqual(CostumeConfig().costume_theme_type, ThemeType.COSTUME_THEME_DEFAULT)
        for val in ('costume_theme_xinyu_mingxiao', 'costume_theme_1', 'costume_theme_2'):
            cfg = CostumeConfig(costume_theme_type=val)
            self.assertEqual(cfg.costume_theme_type, ThemeType.COSTUME_THEME_XINYU_MINGXIAO)

    def test_apply_theme_updates_in_place_and_restores_default(self):
        refs = {name: getattr(GameUiAssets, name) for name in _THEME_NAMES}
        orig_scroll_file = refs['I_MAIN_SCROLL_CLOSE'].file
        _ = refs['I_MAIN_SCROLL_CLOSE'].image
        _ = refs['I_MAIN_SCROLL_CLOSE'].name

        CostumeBase().check_costume_theme(ThemeType.COSTUME_THEME_XINYU_MINGXIAO)
        self.assertIs(GameUiAssets.I_MAIN_SCROLL_CLOSE, refs['I_MAIN_SCROLL_CLOSE'])
        self.assertIn('/CostumeTheme/theme2/', GameUiAssets.I_MAIN_SCROLL_CLOSE.file)
        self.assertIsNone(GameUiAssets.I_MAIN_SCROLL_CLOSE._image)
        self.assertNotIn('name', GameUiAssets.I_MAIN_SCROLL_CLOSE.__dict__)
        self.assertEqual(GameUiAssets.I_MAIN_GOTO_GUILD.method, 'Masked template matching')

        # 修改匹配后的 roi_front 后重新应用不应污染源资产
        orig_front = list(CostumeThemeAssets.I_MAIN_SCROLL_CLOSE_2.roi_front)
        GameUiAssets.I_MAIN_SCROLL_CLOSE.roi_front[0] = 0
        apply_theme(ThemeType.COSTUME_THEME_XINYU_MINGXIAO)
        self.assertEqual(GameUiAssets.I_MAIN_SCROLL_CLOSE.roi_front, orig_front)

        # 切回默认主题应完整还原
        CostumeBase().check_costume_theme(ThemeType.COSTUME_THEME_DEFAULT)
        self.assertIs(GameUiAssets.I_MAIN_SCROLL_CLOSE, refs['I_MAIN_SCROLL_CLOSE'])
        self.assertEqual(GameUiAssets.I_MAIN_SCROLL_CLOSE.file, orig_scroll_file)


class TestMetaDemon2025(unittest.TestCase):
    def test_config_defaults_and_dynamic_strategies(self):
        md = MetaDemon()
        self.assertTrue(md.meta_demon_config.auto_shared_boss)
        self.assertTrue(md.meta_demon_config.md_fatigue_summon_first)
        self.assertFalse(md.meta_demon_config.auto_tea)
        self.assertEqual(md.md_strategies, [])

        # auto_tea 校验器固定为 False；动态策略条数自动扩展与序列化
        md2 = MetaDemon(
            meta_demon_config={'auto_tea': True, 'md_strategy_count': 2},
            md_strategies_1={'md_match_names': '御撰津,雪女', 'md_preset_group_team_1': '1,2', 'md_preset_group_team_2': '2,3'},
        )
        self.assertFalse(md2.meta_demon_config.auto_tea)
        self.assertEqual(len(md2.md_strategies), 2)
        parsed = Strategy.parse_all(md2.md_strategies)
        self.assertEqual(parsed['御撰津'], [1, 2, 2, 3])
        self.assertEqual(parsed['雪女'], [1, 2, 2, 3])
        dumped = md2.model_dump()
        self.assertIn('md_strategies_1', dumped)
        self.assertIn('md_strategies_2', dumped)

        # 精确匹配与 1 字容错匹配
        self.assertEqual(Star56.strategy2group_team(parsed, '御撰津'), [1, 2, 2, 3])
        self.assertEqual(Star56.strategy2group_team(parsed, '御馔津'), [1, 2, 2, 3])
        self.assertIsNone(Star56.strategy2group_team(parsed, '完全不同名'))

    def test_battle_boss_unlocks_and_uses_general_battle_fsm(self):
        task = object.__new__(MetaDemonTask)
        task.current_count = 3
        task.ui_click = MagicMock(return_value=True)
        task.ui_click_until_disappear = MagicMock(return_value=True)
        task.boss_mark_reset = MagicMock()
        task.run_general_battle = MagicMock(return_value=True)

        win = task.battle_boss(group=2, team=4)
        self.assertTrue(win)
        task.ui_click.assert_called_once_with(task.I_TEAM_LOCK, task.I_TEAM_UNLOCK, interval=1.5, timeout=5)
        task.ui_click_until_disappear.assert_called_once_with(task.I_BATTLE_DEMON, interval=1.8, timeout=10)
        task.boss_mark_reset.assert_called_once()

        call_kwargs = task.run_general_battle.call_args.kwargs
        cfg = call_kwargs['config']
        self.assertFalse(cfg.lock_team_enable)
        self.assertTrue(cfg.preset_enable)
        self.assertEqual((cfg.preset_group, cfg.preset_team), (2, 4))
        self.assertEqual(call_kwargs['battle_key'], 'metademon_2_4_3')
        exit_targets = [c.target for c in call_kwargs['exit_matcher'].children]
        self.assertIn(MetaDemonAssets.I_CRAFTING_1, exit_targets)
        self.assertIn(MetaDemonAssets.I_FIND_DEMON, exit_targets)
        self.assertIn(MetaDemonAssets.I_BATTLE_DEMON, exit_targets)

    def test_handle_result_and_boss_mark(self):
        task = object.__new__(MetaDemonTask)
        task.device = SimpleNamespace(
            click_record_clear=MagicMock(),
            stuck_record_add=MagicMock(),
            click_record=[],
        )
        task.click = MagicMock()
        ctx = SimpleNamespace(last_page=None, reward_no_battle_ts=None, is_win=False)
        cfg = GeneralBattleConfig()

        # 胜利结算识别 I_MD_WIN
        task.appear = lambda rule, **kw: rule is task.I_MD_WIN
        act = task._handle_result(ctx, cfg)
        self.assertEqual(act, BattleAction.CONTINUE)
        self.assertTrue(ctx.is_win)
        task.click.assert_called_once_with(task.I_MD_WIN, interval=0.8)

        # 失败结算识别 I_MD_BATTLE_FAILURE
        task.click.reset_mock()
        task.appear = lambda rule, **kw: rule is task.I_MD_BATTLE_FAILURE
        act = task._handle_result(ctx, cfg)
        self.assertEqual(act, BattleAction.CONTINUE)
        self.assertFalse(ctx.is_win)
        task.click.assert_called_once_with(task.I_MD_BATTLE_FAILURE, interval=0.8)

        # boss_mark 连续两次检测到 O_BOSS_MARK 后置位
        gb = object.__new__(GeneralBattle)
        gb._boss_mark_flag = False
        gb.device = SimpleNamespace(stuck_record_add=MagicMock(), click_record=[])
        gb.screenshot = MagicMock()
        gb.ocr_appear = MagicMock(return_value=True)
        gb.click = MagicMock()
        self.assertTrue(gb.boss_mark())
        self.assertTrue(gb._boss_mark_flag)
        # 已标记后再次调用直接返回 False 不重复检测
        gb.ocr_appear.reset_mock()
        self.assertFalse(gb.boss_mark())
        gb.ocr_appear.assert_not_called()


class TestWindowsClientEnhancements(unittest.TestCase):
    def test_human_track_handles_vertical_short_and_diagonal(self):
        # 纯垂直滑动不可除零
        v_track = human_track([500, 100], [500, 400], interval=30)
        self.assertEqual(len(v_track), 10)
        self.assertTrue(all(pt[0] == 500 for pt in v_track))
        self.assertEqual(v_track[-1], [500, 400])

        # 极短距离不返回空列表
        s_track = human_track([100, 100], [102, 103], interval=10)
        self.assertEqual(s_track, [[102, 103]])

        # 斜向正常贝塞尔轨迹
        d_track = human_track([100, 100], [400, 300], interval=20)
        self.assertGreater(len(d_track), 5)

    def test_desktop_move_click_and_capture_changed(self):
        win = object.__new__(Window)
        win.emulator_family = EmulatorFamily.FAMILY_WINDOWS_CLIENT
        win.control_handle_list = [12345]
        win.screenshot_handle_num = 12345
        win.desktop_message_coord = lambda x, y, hwnd=None: (int(x), int(y))

        with patch.object(windows_impl, 'IsWindow', return_value=True), \
             patch.object(windows_impl, 'IsIconic', return_value=False), \
             patch.object(windows_impl, 'PostMessage') as mock_post, \
             patch.object(windows_impl, 'SendMessage') as mock_send, \
             patch('time.sleep', return_value=None):
            win.click_window_message(100, 100)
            # 第二次远距离点击触发轨迹抽稀，不超过 DESKTOP_MOVE_MAX_POINTS + 2 次 PostMessage
            mock_post.reset_mock()
            mock_send.reset_mock()
            win.click_window_message(1200, 650)

        # 发送了 WM_CAPTURECHANGED
        send_msgs = [c.args[1] for c in mock_send.call_args_list]
        self.assertIn(windows_impl.WM_CAPTURECHANGED, send_msgs)
        self.assertEqual(win._desktop_cursor, (1200, 650))
        self.assertLessEqual(len(mock_post.call_args_list), Window.DESKTOP_MOVE_MAX_POINTS + 2)

    def test_screenshot_interval_for_windows_client(self):
        sc = object.__new__(Screenshot)
        sc.is_windows_client = True
        sc._screenshot_interval = SimpleNamespace(limit=0.3)
        sc.config = SimpleNamespace(
            script=SimpleNamespace(
                optimization=SimpleNamespace(screenshot_interval=0.05, combat_screenshot_interval=0.15),
                device=SimpleNamespace(screenshot_method='window_background'),
            )
        )
        sc.screenshot_interval_set()
        self.assertAlmostEqual(sc._screenshot_interval.limit, 0.05)
        self.assertAlmostEqual(sc.config.script.optimization.screenshot_interval, 0.05)

        sc.screenshot_interval_set('combat')
        self.assertAlmostEqual(sc._screenshot_interval.limit, 0.15)
        self.assertAlmostEqual(sc.config.script.optimization.combat_screenshot_interval, 0.15)

        # 非桌面端仍夹取至 0.1 / 0.6
        sc.is_windows_client = False
        sc.screenshot_interval_set()
        self.assertAlmostEqual(sc._screenshot_interval.limit, 0.1)
        sc.screenshot_interval_set('combat')
        self.assertAlmostEqual(sc._screenshot_interval.limit, 0.6)

    def test_mpay_popup_limit_and_unknown_page_guard(self):
        # 1. LoginService 超过 DESKTOP_MPAY_CLOSE_LIMIT 次重弹应抛 GameStuckError
        svc = object.__new__(LoginService)
        svc.device = SimpleNamespace(
            emulator_family=EmulatorFamily.FAMILY_WINDOWS_CLIENT,
            screenshot_handle_num=0,
            stuck_record_add=MagicMock(),
            sleep=MagicMock(),
            get_orientation=MagicMock(),
        )
        svc.screenshot = MagicMock()
        with patch.object(login_service, 'find_desktop_login_popup', return_value=999), \
             patch.object(login_service, 'confirm_desktop_login_popup', return_value=True) as mock_confirm:
            with self.assertRaises(GameStuckError):
                svc._app_handle_login()
        self.assertEqual(mock_confirm.call_count, DESKTOP_MPAY_CLOSE_LIMIT)

        # 2. AppControl.app_lost_login 仅桌面端检测到 MPay 时返回 True
        ctrl = object.__new__(AppControl)
        ctrl.is_windows_client = False
        self.assertFalse(ctrl.app_lost_login())

        ctrl.is_windows_client = True
        ctrl.screenshot_handle_num = 0
        with patch.object(login_service, 'find_desktop_login_popup', return_value=888):
            self.assertTrue(ctrl.app_lost_login())

        # 3. GameUi.close_unknown_pages 检测到掉回登录态立即抛 GameNotRunningError
        ui = object.__new__(GameUi)
        ui.maybe_screenshot = MagicMock()
        ui.device = SimpleNamespace(app_lost_login=MagicMock(return_value=True))
        ui.navigator = SimpleNamespace(local_unknown_closers=[], unknown_close_history=[])
        with self.assertRaises(GameNotRunningError):
            ui.close_unknown_pages(skip_first_screenshot=True)


if __name__ == '__main__':
    unittest.main()
