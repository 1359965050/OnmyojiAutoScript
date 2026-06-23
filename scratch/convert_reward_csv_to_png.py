import csv
import numpy as np
import cv2

csv_path = r"f:\daima\OAS\docs\a4494624-41af-4826-8a3b-544e7f033344.csv"

# Read coordinates first to get dimensions
xs = []
ys = []
with open(csv_path, 'r') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not row:
            continue
        xs.append(int(row[0]))
        ys.append(int(row[1]))

x_min, x_max = min(xs), max(xs)
y_min, y_max = min(ys), max(ys)
width = x_max - x_min + 1
height = y_max - y_min + 1

print(f"X range: {x_min} - {x_max} (width: {width})")
print(f"Y range: {y_min} - {y_max} (height: {height})")

# Create RGB image
img = np.zeros((height, width, 3), dtype=np.uint8)

with open(csv_path, 'r') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not row:
            continue
        x = int(row[0]) - x_min
        y = int(row[1]) - y_min
        r, g, b = int(row[2]), int(row[3]), int(row[4])
        img[y, x] = [b, g, r]  # OpenCV uses BGR

cv2.imwrite(r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_reward_close.png", img)
print("Saved to gate1_reward_close.png")
