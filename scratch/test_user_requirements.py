# This Python file uses the following encoding: utf-8
import time
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from tasks.Component.BaseActivity.base_activity import BaseActivity
from tasks.Component.BaseActivity.assets import BaseActivityAssets
from module.ocr.base_ocr import BoxedResult


class DummyActivity(BaseActivity):
    def __init__(self):
        self.device = MagicMock()
        self._current_climb_type = 'pass'
        self._switch_souled_map = {}
        self.config = MagicMock()
        self.image = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.device.image = self.image
        self.interval_timer = {}

    def screenshot(self):
        return self.image


class TestUserRequirements(unittest.TestCase):
    """验证用户提出的四项修改：
    1. 爬塔房间环境校验设置 1.2s 的 CD
    2. 中转地图自适应点击入场改为 1.5s 的 CD
    3. 点击挑战进入战斗改为 1.2s 的 CD
    4. 日志杂字过滤：['×1', '一U', '挑战'] 中过滤 '一U'，仅保留 '×1' 和 '挑战'
    """

    def setUp(self):
        self.activity = DummyActivity()

    def test_req_4_fire_ocr_clean_junk_text(self):
        """测试清洗规则：['×1', '一U', '挑战'] 中过滤 '一U'，只保留 '×1' 和 '挑战'"""
        raw_texts = ['×1', '一U', '挑战']
        cleaned_texts = [self.activity.O_GENERIC_FIRE.after_process(t) for t in raw_texts]
        # 验证 '一U' 被清洗为空字符串
        self.assertEqual(cleaned_texts, ['×1', '', '挑战'])

        # 进一步验证在 BaseOcr.detect_and_ocr 流程中空字符串会被直接跳过
        fake_boxed = [
            BoxedResult(box=np.array([0, 0, 10, 10]), text_img=None, ocr_text='×1', score=0.9),
            BoxedResult(box=np.array([10, 0, 10, 10]), text_img=None, ocr_text='一U', score=0.9),
            BoxedResult(box=np.array([20, 0, 10, 10]), text_img=None, ocr_text='挑战', score=0.9),
        ]
        fake_model = MagicMock()
        fake_model.detect_and_ocr.return_value = fake_boxed
        self.activity.O_GENERIC_FIRE.__dict__['model'] = fake_model
        try:
            with patch.object(self.activity.O_GENERIC_FIRE, 'pre_process', return_value=self.activity.image), \
                 patch.object(self.activity.O_GENERIC_FIRE, 'crop', return_value=self.activity.image):
                results = self.activity.O_GENERIC_FIRE.detect_and_ocr(self.activity.image)
                final_texts = [r.ocr_text for r in results]
                self.assertEqual(final_texts, ['×1', '挑战'], "杂字 '一U' 未被有效过滤！")
        finally:
            self.activity.O_GENERIC_FIRE.__dict__.pop('model', None)

    def test_req_1_room_env_check_1_2s_cd(self):
        """测试爬塔房间环境校验 1.2s CD 机制：1.2s 内复用判定结果，超过 1.2s 重新检测"""
        appear_mock = MagicMock(return_value=True)
        self.activity.appear = appear_mock
        fake_model = MagicMock()
        fake_model.detect_and_ocr.return_value = []
        self.activity.O_GENERIC_FIRE.__dict__['model'] = fake_model

        try:
            curr_time = 100.0
            with patch('tasks.Component.BaseActivity.base_activity.time.time', return_value=curr_time):
                # 第 1 次调用，执行真实校验
                _ = self.activity.get_current_climb_mode()
                self.assertGreater(appear_mock.call_count, 0)
                initial_calls = appear_mock.call_count

            # 0.5 秒后（< 1.2s），再次调用，命中 1.2s CD 缓存，不重复执行 appear 校验
            with patch('tasks.Component.BaseActivity.base_activity.time.time', return_value=curr_time + 0.5):
                _ = self.activity.get_current_climb_mode()
                self.assertEqual(appear_mock.call_count, initial_calls, "1.2s CD 内不应重复触发环境校验！")

            # 1.3 秒后（> 1.2s），CD 冷却完毕，重新执行环境校验
            with patch('tasks.Component.BaseActivity.base_activity.time.time', return_value=curr_time + 1.3):
                _ = self.activity.get_current_climb_mode()
                self.assertGreater(appear_mock.call_count, initial_calls, "超过 1.2s 后应重新执行环境校验！")
        finally:
            self.activity.O_GENERIC_FIRE.__dict__.pop('model', None)

    def test_req_2_map_battle_cd_1_5s(self):
        """测试中转地图自适应点击入场的 CD 为 1.5s"""
        with patch.object(self.activity, "screenshot"), \
             patch.object(self.activity, "appear", return_value=False), \
             patch.object(self.activity, "ocr_appear", side_effect=lambda rule: rule == self.activity.O_MAP_BATTLE_ENTRANCE), \
             patch.object(self.activity, "ocr_appear_click", return_value=True) as mock_ocr_click:
            res = self.activity.find_and_click_map_battle()
            self.assertTrue(res)
            # 校验 interval 是否为 1.5
            mock_ocr_click.assert_called_once_with(self.activity.O_MAP_BATTLE_ENTRANCE, interval=1.5)

    def test_req_3_fire_battle_cd_1_2s(self):
        """测试点击挑战进入战斗的 CD 为 1.2s"""
        with patch.object(self.activity, "ocr_appear_click", return_value=True) as mock_ocr_click:
            clicked = self.activity.click_fire_button()
            self.assertTrue(clicked)
            # 校验 interval 是否为 1.2
            mock_ocr_click.assert_called_once_with(self.activity.O_GENERIC_FIRE, interval=1.2)

    def test_req_5_mode_distinction_by_ocr_numbers(self):
        """测试用户新提议：右下角识别到 x1 判定为 pass 门票模式，识别到 x6 判定为 ap 体力模式"""
        self.activity.appear = MagicMock(return_value=True)

        # 1. 门票模式识别结果：包含 '×1' 和 '挑战'
        fake_pass_boxed = [
            BoxedResult(box=np.array([0, 0, 10, 10]), text_img=None, ocr_text='×1', score=0.9),
            BoxedResult(box=np.array([20, 0, 10, 10]), text_img=None, ocr_text='挑战', score=0.9),
        ]
        fake_model_pass = MagicMock()
        fake_model_pass.detect_and_ocr.return_value = fake_pass_boxed
        self.activity.O_GENERIC_FIRE.__dict__['model'] = fake_model_pass
        try:
            self.activity._room_env_last_time = 0.0
            mode_pass = self.activity.get_current_climb_mode()
            self.assertEqual(mode_pass, 'pass', "识别到 '×1' 且无 '6' 必须判定为门票模式！")
        finally:
            self.activity.O_GENERIC_FIRE.__dict__.pop('model', None)

        # 2. 体力模式识别结果：包含 '×6', '×1', '挑战'
        fake_ap_boxed = [
            BoxedResult(box=np.array([0, 0, 10, 10]), text_img=None, ocr_text='×6', score=0.9),
            BoxedResult(box=np.array([10, 0, 10, 10]), text_img=None, ocr_text='×1', score=0.9),
            BoxedResult(box=np.array([20, 0, 10, 10]), text_img=None, ocr_text='挑战', score=0.9),
        ]
        fake_model_ap = MagicMock()
        fake_model_ap.detect_and_ocr.return_value = fake_ap_boxed
        self.activity.O_GENERIC_FIRE.__dict__['model'] = fake_model_ap
        try:
            self.activity._room_env_last_time = 0.0
            mode_ap = self.activity.get_current_climb_mode()
            self.assertEqual(mode_ap, 'ap', "识别到 '×6' 必须判定为体力模式！")
        finally:
            self.activity.O_GENERIC_FIRE.__dict__.pop('model', None)


if __name__ == '__main__':
    unittest.main()
