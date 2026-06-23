import sys
sys.path.append(r"f:\daima\OAS")
import cv2
from module.atom.image import RuleImage

img_path = r"C:\Users\13599\.gemini\antigravity-ide\brain\22181a7e-5403-4990-b871-d2e327a0e08e\media__1782148339041.png"
template_path = r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_reward_close.png"

# Coordinates: X: 835-1026 (w=192), Y: 641-705 (h=65)
rule = RuleImage(roi_front=(835, 641, 192, 65), roi_back=(800, 600, 250, 100), method="Template matching", threshold=0.8, file=template_path)

img = cv2.imread(img_path)
# Resize to standard 1280x720
img = cv2.resize(img, (1280, 720))

rule.debug_mode = True
matched = rule.match(img)
print(f"Matched: {matched}")
print(f"roi_front after match: {rule.roi_front}")
