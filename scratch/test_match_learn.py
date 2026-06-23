import sys
sys.path.append(r"f:\daima\OAS")
import cv2
from module.atom.image import RuleImage

img_path = r"C:\Users\13599\.gemini\antigravity-ide\brain\22181a7e-5403-4990-b871-d2e327a0e08e\media__1782145577535.jpg"
learn_path = r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_learn.png"

rule = RuleImage(roi_front=(1129, 588, 76, 94), roi_back=(1080, 550, 180, 150), method="Template matching", threshold=0.8, file=learn_path)

img = cv2.imread(img_path)
img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

# Resize to standard 1280x720
img = cv2.resize(img, (1280, 720))

print(f"img shape: {img.shape}")
source = rule.corp(img)
print(f"source shape: {source.shape}")
mat = rule.image
print(f"mat shape: {mat.shape}")

rule.debug_mode = True
matched = rule.match(img)
print(f"Matched: {matched}")
print(f"roi_front after match: {rule.roi_front}")
