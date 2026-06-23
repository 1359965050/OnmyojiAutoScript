import os
import re
import sys
sys.path.append(r"f:\daima\OAS")
import cv2
from module.atom.ocr import RuleOcr

brain_dir = r"C:\Users\13599\.gemini\antigravity-ide\brain\22181a7e-5403-4990-b871-d2e327a0e08e"
full_ocr = RuleOcr(roi=(0, 0, 1280, 720), area=(0, 0, 1280, 720), mode="Full", method="Default", keyword="", name="full_screen_ocr")

# Find all image files in brain directory
img_files = [f for f in os.listdir(brain_dir) if f.endswith('.png') or f.endswith('.jpg')]

for filename in img_files:
    filepath = os.path.join(brain_dir, filename)
    img = cv2.imread(filepath)
    if img is None:
        continue
    
    if img.shape[0] != 720 or img.shape[1] != 1280:
        img_res = cv2.resize(img, (1280, 720))
    else:
        img_res = img
        
    # Check if the image contains sub-skill reinforcement popup
    ocr_results = full_ocr.detect_and_ocr(img_res, logDisplay=False)
    ocr_texts = [res.ocr_text for res in ocr_results]
    
    if any(t in ocr_texts for t in ["力量强化", "技巧强化", "魅力强化"]):
        print(f"\n=================== Testing {filename} ===================")
        slots = [
            {"name": None, "level": 0, "btn": (292, 518)},
            {"name": None, "level": 0, "btn": (647, 518)},
            {"name": None, "level": 0, "btn": (1002, 518)}
        ]
        for res in ocr_results:
            box = res.box
            cx = int((box[0, 0] + box[2, 0]) / 2)
            cy = int((box[0, 1] + box[2, 1]) / 2)
            
            slot_idx = None
            if 100 <= cx <= 420:
                slot_idx = 0
            elif 420 < cx <= 840:
                slot_idx = 1
            elif 840 < cx <= 1180:
                slot_idx = 2
                
            if slot_idx is not None:
                text = res.ocr_text
                if "力量" in text:
                    slots[slot_idx]["name"] = "力量强化"
                elif "技巧" in text:
                    slots[slot_idx]["name"] = "技巧强化"
                elif "魅力" in text:
                    slots[slot_idx]["name"] = "魅力强化"
                    
                if text == "选择" and 480 <= cy <= 560:
                    slots[slot_idx]["btn"] = (cx, cy)
                    
                if 380 <= cy <= 460:
                    if any(k in text for k in ["升", "提", "增", "%"]):
                        match = re.search(r'(\d+)', text)
                        if match:
                            val = int(match.group(1))
                            if 0 <= val <= 100:
                                slots[slot_idx]["level"] = max(slots[slot_idx]["level"], val)
                                
        for i, slot in enumerate(slots):
            print(f"Slot {i}: name={slot['name']}, level={slot['level']}, btn={slot['btn']}")
