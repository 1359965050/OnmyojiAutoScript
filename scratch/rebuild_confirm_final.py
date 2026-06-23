import cv2
import numpy as np
import pandas as pd

# 确认按钮ROI.csv数据的精准坐标
csv_path = r"f:\daima\OAS\docs\确认按钮ROI.csv"
df = pd.read_csv(csv_path)
x_min, x_max = df['X'].min(), df['X'].max()
y_min, y_max = df['Y'].min(), df['Y'].max()
width = x_max - x_min + 1
height = y_max - y_min + 1
cx = x_min + width // 2
cy = y_min + height // 2

print(f"确认按钮ROI.csv 精准定位:")
print(f"  ROI: ({x_min}, {y_min}, {width}, {height})")
print(f"  Center: ({cx}, {cy})")

# 从CSV像素数据逆向重构PNG模板
img_csv = np.zeros((height, width, 3), dtype=np.uint8)
for _, row in df.iterrows():
    x = int(row['X']) - x_min
    y = int(row['Y']) - y_min
    r, g, b = int(row['Red']), int(row['Green']), int(row['Blue'])
    img_csv[y, x] = [b, g, r]

cv2.imwrite(r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_ap_confirm.png", img_csv)
print(f"Saved gate1_ap_confirm.png ({width}x{height})")

# 检测一下像素颜色：橙黄色确认按钮应该是 R~243, G~178, B~94
sample_bgr = img_csv[0, 0]
print(f"Sample pixel at (0,0): BGR={sample_bgr} -> RGB=({sample_bgr[2]},{sample_bgr[1]},{sample_bgr[0]})")
print("This is the orange-yellow '确定' button color" if sample_bgr[2] > 200 else "Unexpected color")
