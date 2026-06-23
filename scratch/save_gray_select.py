import cv2

img = cv2.imread(r"f:\daima\OAS\scratch\current_screen.png")
if img is None:
    print("Failed to read image")
else:
    # Crop the gray select button
    crop = img[617:640, 242:291]
    cv2.imwrite(r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_select_gray.png", crop)
    print("Saved gray select button template to tasks/SixRealms/gate1/gate1_select_gray.png")
