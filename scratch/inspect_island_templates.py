import cv2
import os

folder = r"f:\daima\OAS\tasks\SixRealms\gate1"
for name in ["gate1_aozhan.png", "gate1_shenmi.png", "gate1_hundun.png"]:
    path = os.path.join(folder, name)
    img = cv2.imread(path)
    if img is not None:
        print(f"{name}: shape={img.shape}")
    else:
        print(f"{name}: not found")
