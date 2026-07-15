# 辅助裁剪六道之门探索入口图标并同步配置
# 用法：
# 1. 把探索界面截图保存到 f:\daima\oas\temp\exploration.png
# 2. python dev_tools/crop_six_gates_icon.py
# 3. 在弹出的窗口中用鼠标框选"六道之门"入口图标，按 ESC 或 q 退出
# 4. 脚本会自动保存图标、更新 page_img.json、重新生成 assets.py

import json
import subprocess
import sys
from pathlib import Path

try:
    import cv2
except ImportError:
    print("请先安装 opencv-python: python -m pip install opencv-python")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "temp" / "exploration.png"
DST = ROOT / "tasks" / "GameUi" / "page" / "page_exploration_goto_six_gates.png"
JSON_FILE = ROOT / "tasks" / "GameUi" / "page" / "page_img.json"


def main():
    if not SRC.exists():
        print(f"请先保存探索界面截图到: {SRC}")
        return
    img = cv2.imread(str(SRC))
    if img is None:
        print(f"无法读取图片: {SRC}")
        return
    h, w = img.shape[:2]
    print(f"截图尺寸: {w}x{h}")
    roi = cv2.selectROI("框选六道之门入口图标 (按 ESC/q 确认)", img, fromCenter=False, showCrosshair=True)
    cv2.destroyAllWindows()
    if roi == (0, 0, 0, 0):
        print("未选择区域，已取消")
        return
    x, y, rw, rh = map(int, roi)
    cropped = img[y:y + rh, x:x + rw]
    cv2.imwrite(str(DST), cropped)
    print(f"已保存新图标: {DST}")

    # 同步更新 page_img.json
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    for item in data:
        if item.get("itemName") == "exploration_goto_six_gates":
            item["roiFront"] = f"{x},{y},{rw},{rh}"
            bx, by, bw, bh = max(0, x - 40), max(0, y - 30), rw + 80, rh + 60
            item["roiBack"] = f"{bx},{by},{bw},{bh}"
            print(f"更新 exploration_goto_six_gates: roiFront={item['roiFront']}, roiBack={item['roiBack']}")
            break
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # 重新生成 assets.py
    env = dict(sys.environ)
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        [sys.executable, str(ROOT / "dev_tools" / "assets_extract.py")],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
    else:
        print("assets.py 已重新生成")


if __name__ == "__main__":
    main()
