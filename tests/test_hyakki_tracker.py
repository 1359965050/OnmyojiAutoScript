# This Python file uses the following encoding: utf-8
"""
tests/test_hyakki_tracker.py
百鬼夜行纯 Python 开源 Tracker 与决策流水线完整联调测试
"""
import sys
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from tasks.Hyakkiyakou.labels import (
    CLASSINDEX as CI,
    CLASSIFY,
    id2label,
    id2name,
    label2id,
)
from tasks.Hyakkiyakou.tracker import Tracker
from tasks.Hyakkiyakou.utils import draw_tracks
from tasks.Hyakkiyakou.agent.agent import Agent
from tasks.Hyakkiyakou.agent.focus import Focus


def test_labels():
    print("Testing labels system...")
    assert len(CLASSIFY) == 253
    assert id2label(CI.BUFF_001) == "buff_001"
    assert id2name(CI.BUFF_006) == "概率UP"
    assert id2label(CI.MIN_SP) == "sp_001"
    assert id2name(CI.MIN_SP) == "少羽大天狗"
    assert id2label(CI.MIN_UR) == "ur_001"
    assert id2name(CI.MIN_UR) == "妖刀姬·绯夜猎刃"
    assert label2id("sp_001") == CI.MIN_SP
    assert label2id("ur_001") == CI.MIN_UR
    assert CI.R_007 == label2id("r_007")
    assert CI.R_008 == label2id("r_008")
    print("✅ Labels system test passed!")


def test_tracker_and_agent_pipeline():
    print("Testing Tracker initialization & inference pipeline...")
    tracker = Tracker({"conf_threshold": 0.5, "iou_threshold": 0.6})
    
    # 模拟 1280x720 游戏画面
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    
    # 连续调用 3 帧
    for i in range(3):
        tracks = tracker(dummy_frame, response=[0, 0, False, 10])
        assert isinstance(tracks, list)
    
    print("✅ Tracker inference test passed!")

    # 构造模拟检测结果 (包含 SP少羽大天狗、SSR茨木童子、概率UP Buff)
    simulated_tracks = [
        (1, CI.MIN_SP, 0.95, 800.0, 320.0, 100.0, 150.0, -12.5),
        (2, CI.MIN_SSR + 6, 0.92, 450.0, 350.0, 110.0, 160.0, -10.0),
        (3, CI.BUFF_006, 0.98, 600.0, 120.0, 70.0, 70.0, -15.0),
    ]

    # 1. 测试可视化绘制
    rendered = draw_tracks(dummy_frame, simulated_tracks)
    assert rendered.shape == (720, 1280, 3)
    print("✅ draw_tracks test passed!")

    # 2. 测试高斯热图生成
    agent = Agent()
    z = Agent.gamma(simulated_tracks, weights=[1.0, 1.0, 0.7, 0.3, 0.0, 0.0])
    assert z.shape == (720, 1280)
    print("✅ Agent.gamma heatmap generation passed!")

    # 3. 测试焦点选取与决策
    focus = Agent.argmax_gamma(z, simulated_tracks)
    assert isinstance(focus, Focus)
    print(f"✅ Focus selected: ID={focus._id}, class={id2name(focus._class)}")

    # 4. 测试单步撒豆决策
    # 状态格式: [豆子数, 剩余式神数, 单次投豆数, Buff0, Buff1, Buff2, Buff3]
    state = [250, 35, 10, False, False, True, False] # 拥有概率 UP (Buff2)
    decision = agent.decision(simulated_tracks, state=state, freeze=False)
    assert len(decision) == 4
    x, y, do_throw, bean_num = decision
    print(f"✅ Agent.decision result: target=({x}, {y}), throw={do_throw}, bean={bean_num}")

    # 5. 测试轨迹重置
    tracker.clear_tracks()
    assert len(tracker.tracks) == 0
    print("✅ Tracker.clear_tracks passed!")


if __name__ == "__main__":
    test_labels()
    test_tracker_and_agent_pipeline()
    print("\n🎉 ALL PIPELINE TESTS PASSED!")
