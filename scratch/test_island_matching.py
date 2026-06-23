import cv2
import os
from module.config.config import Config
from module.device.device import Device
from tasks.SixRealms.script_task import ScriptTask

c = Config('oas1')
d = Device(c)
t = ScriptTask(c, d)

img_path = r"C:\Users\13599\.gemini\antigravity-ide\brain\32b19f03-21b0-4572-a690-3f8560a1132a\media__1782193269725.jpg"
img = cv2.imread(img_path)
img_resized = cv2.resize(img, (1280, 720))
img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)

d.image = img_rgb

for item in [t.I_ISLAND_AOZHAN, t.I_ISLAND_HUNDUN]:
    item.debug_mode = True
    match_res = item.match(d.image)
    # Let's also find the max score on the whole screen for debugging
    source = item.corp(d.image)
    mat = item.image
    res = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    print(f"{item.name}: threshold={item.threshold}, match={match_res}, max_val={max_val:.5f} at {max_loc}")
