import sys
sys.path.append(r"f:\daima\OAS")
import cv2

img_path = r"C:\Users\13599\.gemini\antigravity-ide\brain\22181a7e-5403-4990-b871-d2e327a0e08e\media__1782148339041.png"
img = cv2.imread(img_path)

if img.shape[0] != 720 or img.shape[1] != 1280:
    img_res = cv2.resize(img, (1280, 720))
else:
    img_res = img

# Crop region: X is 835-1026, Y is 641-705
crop = img_res[641:706, 835:1027]
cv2.imwrite(r"f:\daima\OAS\scratch\crop_reinforce_check.png", crop)
print("Crop saved")
