import cv2

img = cv2.imread(r"f:\daima\OAS\scratch\current_screen.png")
if img is None:
    print("Failed to read image")
else:
    # Crop the confirm button (确定) on the 60 AP popup
    # Coordinates from 确认按钮ROI.csv: X: 521-661, Y: 552-599
    crop = img[552:600, 521:662]
    cv2.imwrite(r"f:\daima\OAS\tasks\SixRealms\gate1\gate1_ap_confirm.png", crop)
    print("Saved AP confirm button template to tasks/SixRealms/gate1/gate1_ap_confirm.png")
