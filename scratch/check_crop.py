import sys
sys.path.append(r"f:\daima\OAS")
import cv2
from module.atom.ocr import RuleOcr

crop_path = r"f:\daima\OAS\scratch\crop_reinforce_check.png"
img = cv2.imread(crop_path)
if img is None:
    print("Crop not found")
    sys.exit(0)

print(f"Crop shape: {img.shape}")
# Check pixel values
print("Average color:", cv2.mean(img)[:3])

# Run OCR
full_ocr = RuleOcr(roi=(0, 0, img.shape[1], img.shape[0]), area=(0, 0, img.shape[1], img.shape[0]), mode="Full", method="Default", keyword="", name="crop_ocr")
results = full_ocr.detect_and_ocr(img, logDisplay=False)
for res in results:
    print("Text in crop:", res.ocr_text)
