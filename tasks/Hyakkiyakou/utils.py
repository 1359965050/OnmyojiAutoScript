# This Python file uses the following encoding: utf-8
import cv2
import numpy as np
from tasks.Hyakkiyakou.labels import id2label, id2name, CLASSINDEX as CI

# 预生成确定性色板，保证不同稀有度具有辨识度的颜色
np.random.seed(42)
_palettes = np.random.uniform(50, 240, size=(300, 3)).astype(int)

# 专属稀有度高光配色 (BGR 顺序)
_COLOR_UR = (255, 0, 180)    # 幻彩紫红
_COLOR_SP = (0, 140, 255)     # 亮橙红
_COLOR_SSR = (0, 215, 255)    # 金黄色
_COLOR_SR = (255, 105, 180)   # 紫粉色
_COLOR_R = (255, 191, 0)      # 天蓝色
_COLOR_BUFF = (0, 255, 0)     # 翠绿色


def get_class_color(class_id: int) -> tuple[int, int, int]:
    """根据稀有度区间返回辨识度配色"""
    if CI.MIN_UR <= class_id <= CI.MAX_UR:
        return _COLOR_UR
    elif CI.MIN_SP <= class_id <= CI.MAX_SP:
        return _COLOR_SP
    elif CI.MIN_SSR <= class_id <= CI.MAX_SSR:
        return _COLOR_SSR
    elif CI.MIN_SR <= class_id <= CI.MAX_SR:
        return _COLOR_SR
    elif CI.MIN_BUFF <= class_id <= CI.MAX_BUFF:
        return _COLOR_BUFF
    else:
        c = _palettes[class_id % len(_palettes)]
        return (int(c[0]), int(c[1]), int(c[2]))


def draw_tracks(image: np.ndarray, tracks: list) -> np.ndarray:
    """
    在图像上绘制跟踪目标与运动轨迹信息
    @param image: 原图 (720, 1280, 3)
    @param tracks: list of (_id, _class, _conf, _cx, _cy, _w, _h, _v)
    @return: 绘制完成的图像
    """
    canvas = image.copy()
    for item in tracks:
        if len(item) == 8:
            _id, _class, _conf, _cx, _cy, _w, _h, _v = item
        elif len(item) == 7:
            _id, _class, _conf, _cx, _cy, _w, _h = item
            _v = 0.0
        else:
            continue

        x1 = int(_cx - _w / 2)
        y1 = int(_cy - _h / 2)
        x2 = int(_cx + _w / 2)
        y2 = int(_cy + _h / 2)

        color = get_class_color(_class)
        # 绘制检测框
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)

        # 标签信息：label + 置信度 + 速度
        name = id2name(_class)
        label_code = id2label(_class)
        text_label = f'{name}({label_code}) {_conf:.2f}'
        text_id = f'ID:{_id} v:{_v:.1f}'

        # 绘制顶部标签底色条
        (tw, th), baseline = cv2.getTextSize(text_label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(canvas, (x1, max(0, y1 - th - baseline - 4)), (x1 + tw + 4, y1), color, cv2.FILLED)
        cv2.putText(canvas, text_label, (x1 + 2, y1 - baseline - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        # 绘制 ID 与速度
        cv2.putText(canvas, text_id, (x1, min(canvas.shape[0] - 5, y2 + 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    # 标记水印信息
    cv2.putText(canvas, 'OAS Hyakki OpenTracker', (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)
    return canvas
