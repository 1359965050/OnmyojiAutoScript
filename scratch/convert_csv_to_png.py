import pandas as pd
import numpy as np
import cv2

csv_path = r"f:\daima\OAS\docs\4524148b-a779-4d3a-a2d1-d782f40ae296.csv"
df = pd.read_csv(csv_path)

x_min, x_max = df['X'].min(), df['X'].max()
y_min, y_max = df['Y'].min(), df['Y'].max()
width = x_max - x_min + 1
height = y_max - y_min + 1

print(f"X range: {x_min} - {x_max} (width: {width})")
print(f"Y range: {y_min} - {y_max} (height: {height})")

# Create RGB image
img = np.zeros((height, width, 3), dtype=np.uint8)

for _, row in df.iterrows():
    x = int(row['X']) - x_min
    y = int(row['Y']) - y_min
    r, g, b = int(row['Red']), int(row['Green']), int(row['Blue'])
    img[y, x] = [b, g, r]  # OpenCV uses BGR

cv2.imwrite(r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_learn.png", img)
print("Saved to gate1_learn.png")
