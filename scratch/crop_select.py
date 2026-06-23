import cv2

img = cv2.imread(r"f:\daima\OAS\scratch\current_screen.png")
if img is None:
    print("Failed to read image")
else:
    print(f"Image shape: {img.shape}")
    # Let's crop the first select button at X: 242-290, Y: 617-639
    crop = img[617:640, 242:291]
    cv2.imwrite(r"f:\daima\OAS\scratch\crop_select.png", crop)
    print("Crop saved to crop_select.png")
