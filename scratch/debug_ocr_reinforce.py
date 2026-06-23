import sys
sys.path.append(r"f:\daima\OAS")
import cv2
from module.atom.ocr import RuleOcr

img_path = r"C:\Users\13599\.gemini\antigravity-ide\brain\22181a7e-5403-4990-b871-d2e327a0e08e\media__1782148339041.png"
img = cv2.imread(img_path)
if img is None:
    print(f"Error: {img_path} not found!")
    sys.exit(0)

# Print image size
print(f"Image shape: {img.shape}")

# Resize if needed to check the coordinates in 1280x720 space
if img.shape[0] != 720 or img.shape[1] != 1280:
    img_res = cv2.resize(img, (1280, 720))
else:
    img_res = img

full_ocr = RuleOcr(roi=(0, 0, 1280, 720), area=(0, 0, 1280, 720), mode="Full", method="Default", keyword="", name="full_screen_ocr")
results = full_ocr.detect_and_ocr(img_res, logDisplay=False)

for res in results:
    box = res.box
    cx = int((box[0, 0] + box[2, 0]) / 2)
    cy = int((box[0, 1] + box[2, 1]) / 2)
    print(f"Text: {res.ocr_text:25s} Center: ({cx:4d}, {cy:4d}) Box: {box.tolist()}")
