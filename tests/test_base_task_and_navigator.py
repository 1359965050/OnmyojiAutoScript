# This Python file uses the following encoding: utf-8
import pathlib
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from module.atom.click import RuleClick
from module.atom.image import RuleImage
from module.atom.list import RuleList
from module.atom.long_click import RuleLongClick
from module.atom.ocr import RuleOcr
from module.exception import GamePageUnknownError
from tasks.GameUi.navigator import GameUi
from tasks.GameUi.page_definition import Page, Transition
from tasks.base_task import BaseTask


class DummyTask(BaseTask):
    """隔离真实设备和截图实现的 BaseTask 测试桩。"""

    def __init__(self):
        self.device = MagicMock()
        self.device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.device.image_frame_id = 1
        self.config = MagicMock()
        self.interval_timer = {}
        self.animates = {}

    def screenshot(self):
        return self.device.image


class DummyGameUi(GameUi):
    """隔离页面资产扫描与截图的 GameUi 测试桩。"""

    def __init__(self):
        self.device = MagicMock()
        self.device.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.device.image_frame_id = 1
        self.config = MagicMock()
        self.interval_timer = {}
        self.animates = {}
        from tasks.GameUi.session import NavigatorSession
        self.navigator = NavigatorSession(task_category="global")

    def screenshot(self):
        return self.device.image


class TestBaseTaskAndNavigator(unittest.TestCase):

    def setUp(self):
        self.task = DummyTask()

    def test_click_returns_true_without_interval(self):
        btn = RuleClick(roi_front=(100, 100, 10, 10), roi_back=(100, 100, 10, 10), name="BTN_TEST")
        self.assertTrue(self.task.click(btn))
        self.task.device.click.assert_called_once()
        self.task.device.click.reset_mock()

        self.assertTrue(self.task.click(btn, interval=0))
        self.task.device.click.assert_called_once()
        self.assertFalse(self.task.click(None))

    def test_click_foreground_long_click_and_return_value(self):
        btn = RuleClick(roi_front=(50, 50, 10, 10), roi_back=(50, 50, 10, 10), name="FG_BTN")
        self.assertTrue(self.task.click_foreground(btn))
        self.task.device.click_foreground.assert_called_once()

        long_btn = RuleLongClick(roi_front=(20, 20, 10, 10), roi_back=(20, 20, 10, 10), duration=1500, name="FG_LONG")
        self.assertTrue(self.task.click_foreground(long_btn))
        self.task.device.long_click.assert_called_once()
        _, kwargs = self.task.device.long_click.call_args
        self.assertAlmostEqual(kwargs["duration"], 1.5)

    def test_wait_until_appear_then_click_uses_action_coord_and_wait_time(self):
        target = MagicMock(spec=RuleImage)
        target.name = "TARGET_IMG"
        action = RuleClick(roi_front=(500, 300, 0, 0), roi_back=(500, 300, 0, 0), name="CUSTOM_ACT")

        with patch.object(self.task, "wait_until_appear", return_value=True) as mock_wait:
            ok = self.task.wait_until_appear_then_click(target, action=action, wait_time=4.5)

        self.assertTrue(ok)
        mock_wait.assert_called_once_with(target, wait_time=4.5)
        self.task.device.click.assert_called_once_with(500, 300, control_name="TARGET_IMG")

        self.task.device.long_click.reset_mock()
        long_action = RuleLongClick(roi_front=(420, 220, 0, 0), roi_back=(420, 220, 0, 0), duration=800, name="LONG_ACT")
        with patch.object(self.task, "wait_until_appear", return_value=True):
            ok = self.task.wait_until_appear_then_click(target, action=long_action, wait_time=2.0, duration=1200)
        self.assertTrue(ok)
        self.task.device.long_click.assert_called_once_with(420, 220, duration=1.2, control_name="TARGET_IMG")

    def test_list_appear_click_works_when_interval_is_none(self):
        lst = MagicMock(spec=RuleList)
        lst.name = "TEST_LIST"
        lst.array = ["item_a"]
        with patch.object(self.task, "list_find", return_value=(321, 654)) as mock_find:
            ok = self.task.list_appear_click(lst, interval=None, max_swipe=3)

        self.assertTrue(ok)
        mock_find.assert_called_once_with(lst, name="item_a", max_swipe=3)
        self.task.device.click.assert_called_once_with(321, 654, control_name="TEST_LIST")

    def test_ocr_appear_empty_and_non_digit_guard(self):
        empty_ocr = RuleOcr(name="OCR_EMPTY", mode="SINGLE", method="DEFAULT", roi=(0, 0, 10, 10), area=(0, 0, 10, 10), keyword="")
        with patch.object(empty_ocr, "ocr") as mock_ocr:
            self.assertFalse(self.task.ocr_appear(empty_ocr))
            mock_ocr.assert_not_called()

        bad_digit_ocr = RuleOcr(name="OCR_BAD_DIGIT", mode="DIGIT", method="DEFAULT", roi=(0, 0, 10, 10), area=(0, 0, 10, 10), keyword="abc")
        with patch.object(bad_digit_ocr, "ocr", return_value=123):
            self.assertFalse(self.task.ocr_appear(bad_digit_ocr))

        good_digit_ocr = RuleOcr(name="OCR_GOOD_DIGIT", mode="DIGIT", method="DEFAULT", roi=(0, 0, 10, 10), area=(0, 0, 10, 10), keyword="123")
        with patch.object(good_digit_ocr, "ocr", return_value=123):
            self.assertTrue(self.task.ocr_appear(good_digit_ocr))

    def test_wait_until_pos_stable_restores_roi_back_on_exception(self):
        target = MagicMock(spec=RuleImage)
        target.name = "STABLE_IMG"
        origin_roi = [10, 20, 30, 40]
        target.roi_back = origin_roi
        target.roi_front = [12, 22, 30, 40]

        call_count = 0

        def fake_match(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True
            if call_count == 2:
                return True
            raise RuntimeError("boom")

        target.match.side_effect = fake_match
        with self.assertRaises(RuntimeError):
            self.task.wait_until_pos_stable(target, stable_time=0.1, timeout=1.0)
        self.assertEqual(target.roi_back, origin_roi)

    def test_ui_click_until_smt_disappear_timeout_and_rule_ocr(self):
        ocr_click = RuleOcr(name="OCR_CLK", mode="SINGLE", method="DEFAULT", roi=(0, 0, 10, 10), area=(0, 0, 10, 10), keyword="确定")
        stop_img = MagicMock(spec=RuleImage)
        stop_img.name = "STOP_IMG"

        with patch.object(self.task, "appear", return_value=True), \
             patch.object(self.task, "ocr_appear_click", return_value=True) as mock_ocr_click:
            ok = self.task.ui_click_until_smt_disappear(ocr_click, stop_img, interval=0, timeout=0.05)

        self.assertFalse(ok)
        self.assertGreaterEqual(mock_ocr_click.call_count, 1)

    def test_navigator_refresh_clears_stale_cache_on_none(self):
        nav_ui = DummyGameUi()
        page_a = Page(lambda img: True, key="page_a", name="PageA", register=False)
        nav_ui.navigator.bootstrap([page_a])
        nav_ui.navigator.current_page = page_a

        with patch.object(nav_ui, "confirm_page", return_value=False), \
             patch.object(nav_ui, "_detect_current_page_with_fallback", return_value=None):
            res = nav_ui._refresh_current_page(page_a, skip_first_screenshot=False)

        self.assertIsNone(res)
        self.assertIsNone(nav_ui.navigator.current_page)

    def test_goto_page_none_buffer_defers_close_unknown_pages(self):
        nav_ui = DummyGameUi()
        dest = Page(lambda img: True, key="dest", name="Dest", register=False)
        nav_ui.navigator.bootstrap([dest])

        # 前两次返回 None（模拟过场黑屏），第三次识别到目标页
        with patch.object(nav_ui, "_refresh_current_page", side_effect=[None, None, dest]), \
             patch.object(nav_ui, "close_unknown_pages") as mock_close, \
             patch.object(nav_ui, "_finalize_arrival", return_value=True) as mock_finalize, \
             patch("tasks.GameUi.navigator.time.sleep"):
            ok = nav_ui.goto_page(dest, timeout=10, total_timeout=20, none_buffer_time=2.0)

        self.assertTrue(ok)
        mock_close.assert_not_called()
        mock_finalize.assert_called_once()

    def test_goto_page_total_timeout_breaks_oscillation(self):
        nav_ui = DummyGameUi()
        page_a = Page(lambda img: False, key="page_a", name="PageA", register=False)
        page_b = Page(lambda img: False, key="page_b", name="PageB", register=False)
        page_c = Page(lambda img: False, key="page_c", name="PageC", register=False)
        act_ab = RuleClick(roi_front=(10, 10, 10, 10), roi_back=(10, 10, 10, 10), name="AB")
        act_bc = RuleClick(roi_front=(20, 20, 10, 10), roi_back=(20, 20, 10, 10), name="BC")
        page_a.transitions.append(Transition(source=page_a, destination=page_b, action=act_ab))
        page_b.transitions.append(Transition(source=page_b, destination=page_c, action=act_bc))
        nav_ui.navigator.bootstrap([page_a, page_b, page_c])

        # 始终在 A 和 B 之间震荡，每次切换都会重置 progress_timer，必须依靠 total_timeout 熔断
        seq = [page_a, page_b] * 50

        def next_page(*args, **kwargs):
            return seq.pop(0) if seq else page_a

        with patch.object(nav_ui, "_refresh_current_page", side_effect=next_page), \
             patch.object(nav_ui, "_execute_transition", return_value=False), \
             patch.object(nav_ui, "close_unknown_pages", return_value=False):
            with self.assertRaises(GamePageUnknownError):
                nav_ui.goto_page(page_c, timeout=5, total_timeout=0.15, none_buffer_time=0)

    def test_goto_page_none_buffer_expires_calls_close_and_respects_total_timeout(self):
        nav_ui = DummyGameUi()
        dest = Page(lambda img: True, key="dest", name="Dest", register=False)
        nav_ui.navigator.bootstrap([dest])

        # 持续返回 None，即使 close_unknown_pages 每次都返回 True（会一直重置 progress_timer），
        # 也必须先触发 close_unknown_pages（在缓冲期过后）并最终由 total_timeout 熔断。
        with patch.object(nav_ui, "_refresh_current_page", return_value=None), \
             patch.object(nav_ui, "close_unknown_pages", return_value=True) as mock_close:
            with self.assertRaises(GamePageUnknownError):
                nav_ui.goto_page(dest, timeout=1, total_timeout=0.4, none_buffer_time=0.05)

        self.assertGreaterEqual(mock_close.call_count, 1)

    def test_page_registry_load_all_pages_loads_task_page_modules(self):
        from tasks.GameUi.registry import PageRegistry

        PageRegistry._page_modules_loaded = False
        PageRegistry._loaded_modules.clear()
        PageRegistry.load_all_pages()
        self.assertTrue(PageRegistry._page_modules_loaded)
        self.assertIn("tasks.GameUi.page", PageRegistry._loaded_modules)
        self.assertIn("tasks.Exploration.page", PageRegistry._loaded_modules)
        self.assertIn("tasks.Orochi.page", PageRegistry._loaded_modules)
        self.assertGreaterEqual(len(PageRegistry._loaded_modules), 15)

    def test_heian_kitan_exit_edge_uses_back_buttons_with_fallback(self):
        from tasks.GameUi.assets import GameUiAssets
        from tasks.GameUi.default_pages import exit_heian_kitan, page_heian_kitan
        from tasks.GlobalGame.assets import GlobalGameAssets

        transitions = [t for t in page_heian_kitan.transitions if t.key == "page_heian_kitan->page_exploration"]
        self.assertEqual(len(transitions), 1)
        self.assertIs(transitions[0].action, exit_heian_kitan)

        fake_task = MagicMock()
        # 第一种情况：命中标准黄色返回键即短路返回
        fake_task.appear_then_click.side_effect = [True]
        self.assertTrue(exit_heian_kitan(fake_task))
        fake_task.appear_then_click.assert_called_once_with(GlobalGameAssets.I_UI_BACK_YELLOW, interval=0.8)

        # 第二种情况：未匹配标准黄色/圆形返回键时，回退点击奇谭返回图标
        fake_task.appear_then_click.reset_mock()
        fake_task.appear_then_click.side_effect = [False, False, True]
        self.assertTrue(exit_heian_kitan(fake_task))
        self.assertEqual(
            [c.args[0] for c in fake_task.appear_then_click.call_args_list],
            [GlobalGameAssets.I_UI_BACK_YELLOW, GlobalGameAssets.I_UI_BACK_CIRCLE, GameUiAssets.I_CHECK_HEIAN_KITAN],
        )

    def test_repaired_roi_back_covers_template_dimensions(self):
        from tasks.Component.CostumeShikigami.assets import CostumeShikigamiAssets
        from tasks.Dokan.assets import DokanAssets
        from tasks.SixRealms.assets import SixRealmsAssets

        rules = [
            CostumeShikigamiAssets.I_ST_SOULS_2,
            CostumeShikigamiAssets.I_ST_REPLACE_2,
            CostumeShikigamiAssets.I_ST_SOULS_3,
            CostumeShikigamiAssets.I_ST_REPLACE_3,
            CostumeShikigamiAssets.I_ST_SOULS_4,
            CostumeShikigamiAssets.I_ST_REPLACE_4,
            CostumeShikigamiAssets.I_ST_SOULS_5,
            CostumeShikigamiAssets.I_ST_REPLACE_5,
            DokanAssets.I_RYOU_DOKAN_FIGHTING,
            SixRealmsAssets.I_MS_SKILL_UNLOCK,
        ]
        for rule in rules:
            im = cv2.imread(rule.file)
            self.assertIsNotNone(im, f"Missing image file: {rule.file}")
            ih, iw = im.shape[:2]
            _, _, rw, rh = rule.roi_back
            self.assertGreaterEqual(rw, iw, f"{rule.name} roi_back width {rw} < {iw}")
            self.assertGreaterEqual(rh, ih, f"{rule.name} roi_back height {rh} < {ih}")

    def test_assets_extract_skips_pycache_directories(self):
        from dev_tools.assets_extract import AllAssetsExtractor, AssetsExtractor

        self.assertFalse(AllAssetsExtractor._is_valid_task_dir(pathlib.Path("tasks/__pycache__")))
        self.assertFalse(AllAssetsExtractor._is_valid_task_dir(pathlib.Path("tasks/Component/__pycache__")))
        self.assertFalse(pathlib.Path("tasks/__pycache__/assets.py").exists())
        self.assertFalse(pathlib.Path("tasks/Component/__pycache__/assets.py").exists())
        ex = AssetsExtractor("tasks")
        for jf in ex.all_json_file():
            self.assertNotIn("__pycache__", pathlib.Path(jf).parts)


if __name__ == "__main__":
    unittest.main()
