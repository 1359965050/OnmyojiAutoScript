import cv2

img = cv2.imread(r"f:\daima\OAS\scratch\current_screen.png")
template = cv2.imread(r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_select_gray.png")

if img is None or template is None:
    print(f"Failed to read. img: {img is not None}, template: {template is not None}")
else:
    # Let's perform template matching
    res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    print(f"Max match value: {max_val} at position {max_loc}")
