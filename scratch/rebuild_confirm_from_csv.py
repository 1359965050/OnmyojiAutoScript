import cv2
import numpy as np
import pandas as pd

# 1. 使用确认按钮ROI.csv精准定位并生成模板
csv_path = r"f:\daima\OAS\docs\确认按钮ROI.csv"
df = pd.read_csv(csv_path)

x_min, x_max = df['X'].min(), df['X'].max()
y_min, y_max = df['Y'].min(), df['Y'].max()
width = x_max - x_min + 1
height = y_max - y_min + 1

print(f"确认按钮CSV精准定位:")
print(f"  X range: {x_min} ~ {x_max} (width: {width})")
print(f"  Y range: {y_min} ~ {y_max} (height: {height})")
print(f"  ROI: ({x_min}, {y_min}, {width}, {height})")
print(f"  Center: ({x_min + width//2}, {y_min + height//2})")

# 2. 从CSV像素数据逆向重构PNG模板
img_csv = np.zeros((height, width, 3), dtype=np.uint8)
for _, row in df.iterrows():
    x = int(row['X']) - x_min
    y = int(row['Y']) - y_min
    r, g, b = int(row['Red']), int(row['Green']), int(row['Blue'])
    img_csv[y, x] = [b, g, r]  # OpenCV uses BGR

cv2.imwrite(r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_ap_confirm.png", img_csv)
print(f"\nSaved CSV-reconstructed template to gate1_ap_confirm.png ({width}x{height})")

# 3. 验证: 在当前截图上进行模板匹配
screen = cv2.imread(r"f:\daima\OAS\scratch\current_screen.png")
if screen is not None:
    res = cv2.matchTemplate(screen, img_csv, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    print(f"\nTemplate matching on current screen:")
    print(f"  Max score: {max_val:.4f} at position {max_loc}")
    print(f"  Expected position: ({x_min}, {y_min})")
