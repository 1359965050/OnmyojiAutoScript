import sys
sys.path.append(r"f:\daima\OAS")
import cv2
import numpy as np

img_path = r"C:\Users\13599\.gemini\antigravity-ide\brain\22181a7e-5403-4990-b871-d2e327a0e08e\media__1782148339041.png"
template_path = r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_reward_close.png"

img = cv2.imread(img_path)
template = cv2.imread(template_path)

# Resize img to 1280x720 first to be consistent
img_res = cv2.resize(img, (1280, 720))

res = cv2.matchTemplate(img_res, template, cv2.TM_CCOEFF_NORMED)
min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

print(f"Max match score on full screen: {max_val}")
print(f"Match location: {max_loc}")
# The coordinates of the matched rectangle
w, h = template.shape[1], template.shape[0]
print(f"Matched bounding box in 1280x720 space: [{max_loc[0]}, {max_loc[1]}, {w}, {h}]")
