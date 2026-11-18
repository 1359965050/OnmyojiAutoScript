# -*- coding: utf-8 -*-
"""上游 P0 同步项离线回归测试（不依赖真实设备、RPC 图像/OCR 服务）。"""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from module.atom.image import RuleImage, set_roi_match_padding
from module.device.method.minitouch import Minitouch
from tasks.Component.Costume.assets import CostumeAssets
from tasks.Component.Costume.costume_base import CostumeBase
from tasks.Component.GeneralInvite.assets import GeneralInviteAssets
from tasks.Component.SwitchAccount.assets import SwitchAccountAssets
from tasks.Delegation.script_task import ScriptTask as DelegationTask
from tasks.Dokan.assets import DokanAssets
from tasks.Dokan.script_task import ScriptTask as DokanTask
from tasks.EternitySea.script_task import ScriptTask as EternitySeaTask
from tasks.Exploration.assets import ExplorationAssets
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.default_pages import page_mall
from tasks.GlobalGame.assets import GlobalGameAssets
from tasks.KekkaiActivation.assets import KekkaiActivationAssets
from tasks.KekkaiActivation.script_task import ScriptTask as KekkaiActivationTask
from tasks.KekkaiUtilize.assets import KekkaiUtilizeAssets
from tasks.RichMan.mall.navbar import MallNavbar
from tasks.RichMan.mall.scales import Scales


class TestUpstreamP0Sync(unittest.TestCase):
    def setUp(self):
        set_roi_match_padding(0)

    def tearDown(self):
        set_roi_match_padding(0)

    def test_mall_dual_appearance_and_back_mall(self):
        self.assertTrue(hasattr(GameUiAssets, 'I_CHECK_MALL_PURPLE'))
        targets = [child.target for child in page_mall.recognizer.children]
        self.assertIn(GameUiAssets.I_CHECK_MALL, targets)
        self.assertIn(GameUiAssets.I_CHECK_MALL_PURPLE, targets)

        nav = object.__new__(MallNavbar)
        nav.goto_page = MagicMock()
        nav.back_mall()
        nav.goto_page.assert_called_once_with(page_mall, skip_first_screenshot=False, timeout=6)

    def test_exploration_marker_detects_shifted_x(self):
        for x in (1152, 1166):
            with self.subTest(x=x):
                rule = copy.deepcopy(GameUiAssets.I_CHECK_EXPLORATION)
                frame = np.full((720, 1280, 3), 100, dtype=np.uint8)
                h, w = rule.image.shape[:2]
                frame[148:148 + h, x:x + w] = rule.image
                self.assertTrue(rule.template_match(frame))
                self.assertEqual(rule.roi_front[:2], [x, 148])

        blank_rule = copy.deepcopy(GameUiAssets.I_CHECK_EXPLORATION)
        self.assertFalse(blank_rule.template_match(np.full((720, 1280, 3), 100, dtype=np.uint8)))

    def test_main_goto_guild_masked_template_matching(self):
        rule = copy.deepcopy(GameUiAssets.I_MAIN_GOTO_GUILD)
        self.assertEqual(rule.method, RuleImage.METHOD_MASKED_TEMPLATE_MATCH)
        self.assertIsNotNone(rule.mask)
        self.assertEqual(rule.mask.shape, rule.image.shape[:2])
        self.assertGreater(np.count_nonzero(rule.mask), 0)
        self.assertLess(np.count_nonzero(rule.mask), rule.mask.size)

        # 修改 mask==0 的背景像素后仍可高分命中
        icon = rule.image.copy()
        icon[rule.mask == 0] = 255
        frame = np.full((720, 1280, 3), 100, dtype=np.uint8)
        h, w = icon.shape[:2]
        frame[610:610 + h, 550:550 + w] = icon
        self.assertTrue(rule.template_match(frame))
        self.assertGreater(rule.last_score, 0.99)

    def test_minitouch_humanized_pressure_handles_low_max_pressure(self):
        mt = object.__new__(Minitouch)
        for max_p in (1, 5, 10, 19, 20, 100):
            mt.max_pressure = max_p
            for _ in range(20):
                val = mt._humanized_pressure()
                self.assertGreaterEqual(val, 1)
                self.assertLessEqual(val, max_p)

    def test_rule_image_refresh_and_costume_replace_no_alias(self):
        class Probe(CostumeBase):
            pass

        probe = Probe()
        probe.I_CHECK_MAIN = copy.deepcopy(GameUiAssets.I_CHECK_MAIN)
        source = copy.deepcopy(CostumeAssets.I_CHECK_MAIN_1)
        orig_source_roi = list(source.roi_front)
        _ = probe.I_CHECK_MAIN.name  # Prime cached_property
        _ = probe.I_CHECK_MAIN.image

        probe.replace_img('I_CHECK_MAIN', source)
        self.assertIsNot(probe.I_CHECK_MAIN.roi_front, source.roi_front)
        self.assertIsNone(probe.I_CHECK_MAIN._image)
        self.assertNotIn('name', probe.I_CHECK_MAIN.__dict__)
        self.assertEqual(probe.I_CHECK_MAIN.name, source.name)

        probe.I_CHECK_MAIN.roi_front[0] = 999
        self.assertEqual(source.roi_front, orig_source_roi)

    def test_delegation_prioritizes_cancel_and_uses_3s_debounce(self):
        task = object.__new__(DelegationTask)
        task.device = SimpleNamespace(image=np.zeros((720, 1280, 3), dtype=np.uint8))
        task.O_D_NAME = SimpleNamespace(keyword='')
        task.I_D_START = object()
        task.I_D_BACK = object()
        task.I_D_SKIP = object()
        task.I_D_CONFIRM = object()
        task.I_UI_CANCEL = object()
        task.I_REWARDS_MIN = object()
        task.screenshot = MagicMock()
        task.ocr_appear = MagicMock(return_value=True)
        task.wait_until_appear = MagicMock()

        frames = {'step': 0}

        def fake_appear(target, *args, **kwargs):
            if target is task.I_D_BACK:
                return frames['step'] >= 2
            return False

        cancel_clicks = []
        ocr_intervals = []

        def fake_appear_then_click(target, interval=None, *args, **kwargs):
            if target is task.I_UI_CANCEL and frames['step'] == 0:
                frames['step'] = 1
                cancel_clicks.append(target)
                return True
            if target is task.I_D_BACK:
                frames['step'] = 3
                return True
            return False

        def fake_ocr_appear_click(target, interval=None, *args, **kwargs):
            ocr_intervals.append(interval)
            frames['step'] = 2
            return True

        task.appear = fake_appear
        task.appear_then_click = fake_appear_then_click
        task.ocr_appear_click = fake_ocr_appear_click

        # 返回 False（委派中），但应先点取消，且 O_D_NAME 防抖为 3s
        result = task.delegate_one('猫老大')
        self.assertFalse(result)
        self.assertEqual(len(cancel_clicks), 1)
        self.assertEqual(ocr_intervals, [3])

    def test_kekkai_activation_gray_score_prevents_spin(self):
        task = object.__new__(KekkaiActivationTask)
        task.goto_page = MagicMock()
        task.screenshot = MagicMock()
        task.check_card_status = MagicMock(return_value=False)
        task.check_card_effect = MagicMock(return_value=False)
        task.I_A_ACTIVATE_YELLOW = SimpleNamespace(last_score=0.955)
        task.I_A_ACTIVATE_GRAY = SimpleNamespace(last_score=0.992)
        task.I_A_DEMOUNT = object()

        def fake_appear(target, **kwargs):
            if target is task.I_A_ACTIVATE_YELLOW:
                return True
            if target is task.I_A_ACTIVATE_GRAY:
                return True
            return False

        task.appear = fake_appear
        # 当灰按钮得分更高时，应跳过 continue 并进入 screening_card
        task.screening_card = MagicMock(side_effect=StopIteration('reached_screening'))
        cfg = SimpleNamespace(card_type='taiko')
        with patch('tasks.KekkaiActivation.script_task.time.sleep'):
            with self.assertRaisesRegex(StopIteration, 'reached_screening'):
                task.run_activation(cfg)

    def test_richman_scales_sea_auto_buys_once(self):
        scales = object.__new__(Scales)
        scales.device = SimpleNamespace(image=np.zeros((720, 1280, 3), dtype=np.uint8))
        scales.config = SimpleNamespace(rich_man=SimpleNamespace(scales=SimpleNamespace(enable_book_auto=True)))
        scales.I_SCA_PICTURE_BOOK = object()
        scales.O_SCA_NUMBER_SEA = SimpleNamespace(ocr=MagicMock(return_value=25))
        scales.O_SCA_RES_SEA = SimpleNamespace(ocr=MagicMock(return_value=6000))
        scales.screenshot = MagicMock()
        scales.appear = MagicMock(return_value=True)
        scales._scales_buy_more = MagicMock()
        scales._scales_buy_sea_more = MagicMock()

        with patch('tasks.RichMan.mall.scales.time.sleep'):
            scales._scales_sea(25)

        scales._scales_buy_more.assert_called_once_with(scales.I_SCA_PICTURE_BOOK)
        scales._scales_buy_sea_more.assert_not_called()

    def test_eternity_sea_member_respects_team_session_guard(self):
        task = object.__new__(EternitySeaTask)
        task.config = SimpleNamespace(
            model=SimpleNamespace(
                eternity_sea=SimpleNamespace(
                    eternity_sea_config=SimpleNamespace(limit_count=0),
                    invite_config=SimpleNamespace(wait_time=5),
                )
            )
        )
        task.current_count = 0
        task.start_time = MagicMock()
        task.device = SimpleNamespace(stuck_record_add=MagicMock())
        task.screenshot = MagicMock()
        task.exit_room = MagicMock()
        task.exit_team = MagicMock()
        task._prepare_eternity_sea = MagicMock()

        # 已在组队会话中：不得回跳 _prepare_eternity_sea
        task.is_in_team_session = MagicMock(return_value=True)
        task.run_member()
        task._prepare_eternity_sea.assert_not_called()

        # 不在组队会话中：应执行 _prepare_eternity_sea 同步锁阵容
        task.is_in_team_session = MagicMock(return_value=False)
        task.run_member()
        task._prepare_eternity_sea.assert_called_once()

    def test_dokan_map_attempts_create_once_any_weekday(self):
        task = object.__new__(DokanTask)
        task._create_dokan_attempted = False
        task.I_RYOU_DOKAN_FINDING_DOKAN = object()
        task.I_RYOU_DOKAN_FOUND_DOKAN = object()
        task.I_RYOU_DOKAN_CENTER_TOP = object()
        task.config = SimpleNamespace(
            dokan=SimpleNamespace(
                dokan_config=SimpleNamespace(try_start_dokan=True, find_dokan_score=1.0)
            )
        )
        task.appear = lambda target: target is task.I_RYOU_DOKAN_FINDING_DOKAN
        task.update_remain_attack_count = MagicMock(return_value=1)
        task.creat_dokan = MagicMock()
        task.find_dokan = MagicMock(return_value=True)
        task.wait_until_appear = MagicMock()

        task.run_on_dokan_map()
        task.run_on_dokan_map()
        task.creat_dokan.assert_called_once()

    def test_updated_assets_parameters_match_extracted_classes(self):
        self.assertEqual(KekkaiUtilizeAssets.I_CARD_EXP.method, RuleImage.METHOD_MULTI_SCALE_TEMPLATE_MATCH)
        self.assertEqual(KekkaiUtilizeAssets.I_BOX_AP.method, RuleImage.METHOD_MULTI_SCALE_TEMPLATE_MATCH)
        self.assertEqual(KekkaiUtilizeAssets.I_REALM_SHIN.method, RuleImage.METHOD_MULTI_SCALE_TEMPLATE_MATCH)
        self.assertEqual(tuple(KekkaiActivationAssets.I_A_HARVEST_EXP.roi_back), (750, 90, 250, 230))
        self.assertEqual(tuple(GlobalGameAssets.I_UI_CONFIRM.roi_back), (547, 345, 327, 320))
        self.assertEqual(tuple(GlobalGameAssets.I_UI_CANCEL.roi_back), (356, 384, 275, 256))
        self.assertEqual(tuple(GeneralInviteAssets.I_INVITE_ENSURE.roi_back), (473, 505, 409, 121))
        self.assertEqual(tuple(SwitchAccountAssets.O_SA_CHECK_SELECT_SVR.roi), (231, 145, 102, 32))
        self.assertEqual(tuple(ExplorationAssets.O_REALM_RAID_NUMBER1.roi), (920, 12, 78, 30))
        self.assertAlmostEqual(DokanAssets.I_CENTER_GUANZHU_XIUXI.threshold, 0.7)


if __name__ == '__main__':
    unittest.main()
