import cv2
import numpy as np

screen = cv2.imread(r"f:\daima\OAS\scratch\current_3card.png")
print(f"Screenshot: {screen.shape}")

templates = {
    "I_SELECT_1": {
        "file": r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_select_1.png",
        "roi_back": (200, 540, 400, 140),
    },
    "I_SELECT_2": {
        "file": r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_select_2.png",
        "roi_back": (520, 540, 340, 140),
    },
    "I_SELECT_3": {
        "file": r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_select_3.png",
        "roi_back": (840, 540, 340, 140),
    },
}

for name, info in templates.items():
    tmpl = cv2.imread(info["file"])
    rx, ry, rw, rh = info["roi_back"]
    region = screen[ry:ry+rh, rx:rx+rw]
    
    if tmpl.shape[0] > region.shape[0] or tmpl.shape[1] > region.shape[1]:
        print(f"{name}: template ({tmpl.shape[1]}x{tmpl.shape[0]}) larger than region ({rw}x{rh})")
        continue
    
    res = cv2.matchTemplate(region, tmpl, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    abs_x = rx + max_loc[0]
    abs_y = ry + max_loc[1]
    click_x = abs_x + tmpl.shape[1] // 2
    click_y = abs_y + tmpl.shape[0] // 2
    
    status = "PASS" if max_val >= 0.8 else "FAIL"
    print(f"{name}: score={max_val:.4f} [{status}] match_at=({abs_x},{abs_y}) click_center=({click_x},{click_y})")

print("\n--- Expected 3-card button centers ---")
print("Left:  ~(326, 573)")
print("Mid:   ~(643, 573)")
print("Right: ~(962, 573)")
