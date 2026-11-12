# This Python file uses the following encoding: utf-8
import time
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import cv2
import gevent
import numpy as np

from module.atom.click import RuleClick
from module.atom.image import RuleImage
from module.atom.list import RuleList
from module.atom.swipe import RuleSwipe
from module.base.utils.utils import wait_concurrent_future
from module.image.rpc import ImageClient, _IMAGE_CLIENT_CACHE, get_image_client, shutdown_image_server
from module.image.runtime import ImageRuntime
from module.ocr.base_ocr import OcrMode
from module.ocr.rpc import OcrRuntime, ModelProxy, _OCR_CLIENT_CACHE, get_ocr_client, shutdown_ocr_server
from module.atom.ocr import RuleOcr
from ppocronnx.predict_system import BoxedResult


class TestImageAndOcrRuntimeFixes(unittest.TestCase):
    def test_wait_concurrent_future_does_not_block_gevent_hub(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            ticks = []

            def ticker():
                for _ in range(4):
                    ticks.append(time.monotonic())
                    gevent.sleep(0.03)

            def blocker():
                fut = pool.submit(lambda: (time.sleep(0.15), "ok")[1])
                return wait_concurrent_future(fut)

            g_tick = gevent.spawn(ticker)
            g_block = gevent.spawn(blocker)
            gevent.joinall([g_tick, g_block], raise_error=True)

            self.assertEqual(g_block.value, "ok")
            self.assertGreaterEqual(len(ticks), 3)

    def test_invalid_or_missing_template_returns_false(self):
        rt = ImageRuntime()
        try:
            screen = np.zeros((100, 100, 3), dtype=np.uint8)
            matched, score, roi = rt._template_match_image(
                image=screen,
                template=None,
                roi_back=[0, 0, 50, 50],
                threshold=0.8,
                log_name="MISSING",
            )
            self.assertFalse(matched)
            self.assertEqual(score, -1.0)
            self.assertIsNone(roi)

            matched_ms, score_ms, roi_ms = rt._multi_scale_template_match(
                image=screen,
                template=np.zeros((0, 0, 3), dtype=np.uint8),
                roi_back=[0, 0, 50, 50],
                threshold=0.8,
                scale_range=(0.8, 1.2),
                scale_step=0.1,
                log_name="EMPTY_MS",
            )
            self.assertFalse(matched_ms)
            self.assertEqual(score_ms, -1.0)
            self.assertIsNone(roi_ms)

            self.assertIsNone(rt._get_template_entry("nonexistent_file_12345.png"))
        finally:
            rt.shutdown()

    def test_rule_image_invalid_template_returns_false(self):
        rule = RuleImage(
            roi_front=(0, 0, 10, 10),
            roi_back=(0, 0, 50, 50),
            method=RuleImage.METHOD_TEMPLATE_MATCH,
            threshold=0.8,
            file="dummy.png",
        )
        rule._image = np.zeros((0, 0, 3), dtype=np.uint8)
        screen = np.zeros((100, 100, 3), dtype=np.uint8)
        self.assertFalse(rule.template_match(screen))
        self.assertEqual(rule.last_score, -1.0)
        self.assertFalse(rule.multi_scale_template_match(screen))

    def test_mean_brightness_uses_rgb_weights(self):
        # Pure red image in RGB format: luminance should be ~0.299 * 255 = 76.245, not BGR's 0.114 * 255 = 29.07
        pure_red_rgb = np.zeros((10, 10, 3), dtype=np.uint8)
        pure_red_rgb[:, :, 0] = 255
        mean_val = ImageRuntime._mean_brightness(pure_red_rgb)
        self.assertAlmostEqual(mean_val, 0.299 * 255, delta=1.5)

        gray = np.full((10, 10), 42, dtype=np.uint8)
        self.assertAlmostEqual(ImageRuntime._mean_brightness(gray), 42.0)

    def test_load_template_image_supports_4channel_bgra(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            png_path = Path(tmpdir) / "rgba.png"
            bgra = np.zeros((8, 8, 4), dtype=np.uint8)
            bgra[:, :, 2] = 200  # R in BGRA
            bgra[:, :, 3] = 255  # A
            ok, encoded = cv2.imencode(".png", bgra)
            self.assertTrue(ok)
            png_path.write_bytes(encoded.tobytes())

            rgb = ImageRuntime._load_template_image(str(png_path))
            self.assertEqual(rgb.shape, (8, 8, 3))
            self.assertEqual(int(rgb[0, 0, 0]), 200)

    def test_ocr_runtime_shutdown_releases_models(self):
        with patch("module.ocr.rpc.TextSystem") as mock_ts_cls:
            mock_model = MagicMock()
            mock_model.text_detector.session = object()
            mock_model.text_recognizer.session = object()
            mock_model.ocr_single_line.return_value = ("123", 0.99)
            mock_ts_cls.return_value = mock_model

            rt = OcrRuntime({"worker_count": 1})
            self.assertTrue(rt.warmup())
            self.assertEqual(rt.get_server_info()["loaded_worker_count"], 1)
            rt.shutdown()
            self.assertIsNone(mock_model.text_detector.session)
            self.assertIsNone(mock_model.text_recognizer.session)
            self.assertEqual(rt.get_server_info()["loaded_worker_count"], 0)

    def test_rpc_client_cache_closes_replaced_clients(self):
        old_img = MagicMock(spec=ImageClient)
        new_img = MagicMock(spec=ImageClient)
        _IMAGE_CLIENT_CACHE.clear()
        _IMAGE_CLIENT_CACHE["127.0.0.1:29999"] = old_img
        try:
            with patch("module.image.rpc.ImageClient", return_value=new_img):
                cli = get_image_client("127.0.0.1:29999", refresh=True)
            self.assertIs(cli, new_img)
            old_img.close.assert_called_once()
        finally:
            _IMAGE_CLIENT_CACHE.clear()

        old_ocr = MagicMock(spec=ModelProxy)
        new_ocr = MagicMock(spec=ModelProxy)
        _OCR_CLIENT_CACHE.clear()
        _OCR_CLIENT_CACHE["127.0.0.1:29998"] = old_ocr
        try:
            with patch("module.ocr.rpc.ModelProxy", return_value=new_ocr):
                cli = get_ocr_client("127.0.0.1:29998", refresh=True)
            self.assertIs(cli, new_ocr)
            old_ocr.close.assert_called_once()
        finally:
            _OCR_CLIENT_CACHE.clear()


class TestOcrAndAtomFixes(unittest.TestCase):
    def test_full_ocr_full_merges_multiple_boxes_correctly(self):
        ocr = RuleOcr(name="TEST_FULL", mode="FULL", method="DEFAULT", roi=(100, 50, 300, 100), area=(0, 0, 10, 10), keyword="阴阳师")
        b1 = BoxedResult(np.array([[10, 20], [50, 20], [50, 40], [10, 40]]), None, "阴阳", 0.99)
        b2 = BoxedResult(np.array([[55, 22], [95, 22], [95, 42], [55, 42]]), None, "师", 0.99)
        screen = np.zeros((200, 500, 3), dtype=np.uint8)
        with patch.object(ocr, "detect_and_ocr", return_value=[b1, b2]):
            area = ocr.ocr_full(screen)
        self.assertEqual(area, (110, 70, 85, 22))

    def test_digit_falls_back_to_vertical_detect_and_ocr_when_single_line_empty(self):
        ocr = RuleOcr(name="TEST_DIGIT", mode="DIGIT", method="DEFAULT", roi=(0, 0, 50, 100), area=(0, 0, 50, 100), keyword="0")
        mock_model = MagicMock()
        ocr.__dict__["model"] = mock_model
        mock_model.ocr_single_line.return_value = ("", 0.0)
        mock_model.detect_and_ocr.return_value = [
            BoxedResult(np.array([[0, 0], [20, 0], [20, 40], [0, 40]]), None, "45", 0.95)
        ]
        screen = np.zeros((100, 100, 3), dtype=np.uint8)
        self.assertEqual(ocr.ocr_digit(screen), 45)
        mock_model.detect_and_ocr.assert_called_once()

        # Genuine "0" from ocr_single_line should still work and return 0 without vertical fallback
        mock_model.reset_mock()
        mock_model.ocr_single_line.return_value = ("0", 0.95)
        self.assertEqual(ocr.ocr_digit(screen), 0)
        mock_model.detect_and_ocr.assert_not_called()

    def test_quantity_ocr_handles_int_after_process_and_invalid_cn2an(self):
        ocr = RuleOcr(name="TEST_QTY", mode="QUANTITY", method="DEFAULT", roi=(10, 20, 100, 40), area=(0, 0, 10, 10), keyword="")
        mock_model = MagicMock()
        ocr.__dict__["model"] = mock_model
        mock_model.detect_and_ocr.return_value = [
            BoxedResult(np.array([[0, 0], [40, 0], [40, 20], [0, 20]]), None, "1.2万", 0.95)
        ]
        screen = np.zeros((100, 200, 3), dtype=np.uint8)
        self.assertEqual(ocr.ocr_quantity(screen), 12000)

        # Invalid cn2an string should not raise ValueError
        mock_model.detect_and_ocr.return_value = [
            BoxedResult(np.array([[0, 0], [40, 0], [40, 20], [0, 20]]), None, "1.2.3", 0.95)
        ]
        self.assertEqual(ocr.ocr_quantity(screen), 0)

    def test_rule_list_ocr_appear_returns_none_when_empty(self):
        lst = RuleList(folder="./tasks/Orochi/res", direction="vertical", mode="ocr", roi_back=(100, 100, 200, 300), size=(100, 40), array=["壹层", "贰层"])
        lst._target = MagicMock()
        lst._target.detect_and_ocr.return_value = []
        screen = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.assertIsNone(lst.ocr_appear(screen, "壹层"))

    def test_rule_click_move_uses_delta_not_doubling(self):
        click = RuleClick(roi_front=(100, 200, 30, 40), roi_back=(0, 0, 100, 100))
        click.move(15, -20)
        self.assertEqual(click.roi_front, (115, 180, 30, 40))
        click.move(5000, -5000)
        self.assertEqual(click.roi_front, (1280, 0, 30, 40))

    def test_rule_swipe_trace_unpacks_4_tuple_and_handles_short_distance(self):
        swipe_vec = RuleSwipe(roi_front=(100, 100, 0, 0), roi_back=(102, 102, 0, 0), mode="vector")
        path_vec = swipe_vec.trace()
        self.assertGreaterEqual(len(path_vec), 2)
        self.assertEqual(path_vec[0], (100, 100))
        self.assertEqual(path_vec[-1], (102, 102))

        swipe_bez = RuleSwipe(roi_front=(100, 200, 0, 0), roi_back=(300, 400, 0, 0), mode="default")
        path_bez = swipe_bez.trace()
        self.assertGreaterEqual(len(path_bez), 2)


if __name__ == "__main__":
    unittest.main()
