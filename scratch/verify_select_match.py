import cv2
import numpy as np

screen = cv2.imread(r"f:\daima\OAS\scratch\current_3card.png")
print(f"Screenshot shape: {screen.shape}")

# 加载现有的select模板
templates = {
    "gate1_select_0": cv2.imread(r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_select_0.png"),
    "gate1_select_1": cv2.imread(r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_select_1.png"),
    "gate1_select_2": cv2.imread(r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_select_2.png"),
    "gate1_select_3": cv2.imread(r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_select_3.png"),
    "gate1_select_gray": cv2.imread(r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_select_gray.png"),
}

# 对每个模板在全屏做匹配
for name, tmpl in templates.items():
    if tmpl is None:
        print(f"{name}: template not found")
        continue
    print(f"\n{name} ({tmpl.shape[1]}x{tmpl.shape[0]}):")
    res = cv2.matchTemplate(screen, tmpl, cv2.TM_CCOEFF_NORMED)
    
    # 找所有匹配度>0.6的位置
    threshold = 0.6
    locs = np.where(res >= threshold)
    matches = list(zip(locs[1], locs[0], res[locs[0], locs[1]]))
    
    # 按分数排序
    matches.sort(key=lambda x: -x[2])
    
    # NMS: 去重近距离的匹配
    filtered = []
    for mx, my, ms in matches:
        if not any(abs(mx - fx) < 30 and abs(my - fy) < 30 for fx, fy, _ in filtered):
            filtered.append((mx, my, ms))
    
    if filtered:
        for mx, my, ms in filtered[:5]:
            print(f"  Match at ({mx}, {my}) score={ms:.4f}")
    else:
        # 找最高分
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        print(f"  No match above {threshold}. Best: ({max_loc[0]}, {max_loc[1]}) score={max_val:.4f}")

# 也试试在ROI限定范围内匹配
print("\n--- ROI-constrained matching ---")
rois = {
    "I_SELECT_0": (180, 560, 170, 120),
    "I_SELECT_1": (382, 544, 196, 100),
    "I_SELECT_2": (666, 546, 196, 100),
    "I_SELECT_3": (1000, 550, 173, 100),
}
for name, (rx, ry, rw, rh) in rois.items():
    region = screen[ry:ry+rh, rx:rx+rw]
    tmpl = templates.get(name.replace("I_", "gate1_").lower())
    if tmpl is None:
        continue
    if tmpl.shape[0] > region.shape[0] or tmpl.shape[1] > region.shape[1]:
        print(f"{name}: template larger than ROI region")
        continue
    res = cv2.matchTemplate(region, tmpl, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    abs_x = rx + max_loc[0]
    abs_y = ry + max_loc[1]
    print(f"{name} roi=({rx},{ry},{rw},{rh}): score={max_val:.4f} at abs({abs_x},{abs_y})")
