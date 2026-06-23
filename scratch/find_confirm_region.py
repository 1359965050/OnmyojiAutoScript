import cv2
import numpy as np

screen = cv2.imread(r"f:\daima\OAS\scratch\current_screen.png")
if screen is None:
    print("Failed to read screenshot")
    exit()

print(f"Screenshot shape: {screen.shape}")

# 从截图中可以看到弹窗"确定"按钮大致在右侧偏中的位置
# 从用户截图分析：弹窗大约在 X:350~780, Y:250~460
# "确定"按钮在弹窗右侧，大约 X:530~660, Y:390~430
# 我们先粗裁一个大区域看看
regions = [
    ("region_full_popup", (350, 250, 430, 210)),   # 整个弹窗区域
    ("region_confirm_1", (520, 380, 160, 60)),      # 确定按钮猜测区1
    ("region_confirm_2", (540, 390, 140, 50)),      # 确定按钮猜测区2
    ("region_confirm_3", (550, 395, 120, 40)),      # 确定按钮猜测区3
]

for name, (x, y, w, h) in regions:
    crop = screen[y:y+h, x:x+w]
    path = f"f:\\daima\\OAS\\scratch\\{name}.png"
    cv2.imwrite(path, crop)
    print(f"Saved {name}: roi=({x},{y},{w},{h}), shape={crop.shape}")

# 也对比一下通用确认按钮的位置 I_UI_CONFIRM: roi_front=(667,398,179,66)
crop_ui_confirm = screen[398:464, 667:846]
cv2.imwrite(r"f:\daima\OAS\scratch\region_ui_confirm.png", crop_ui_confirm)
print(f"Saved region_ui_confirm: roi=(667,398,179,66), shape={crop_ui_confirm.shape}")
