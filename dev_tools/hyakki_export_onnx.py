# This Python file uses the following encoding: utf-8
"""
dev_tools/hyakki_export_onnx.py
百鬼夜行 YOLO11s 模型 ONNX 导出与性能压测工具
导出为高效静态图结构，并使用 ONNX Runtime 测试单帧推理延迟与输出结构。
"""
import sys
import time
import shutil
import argparse
import numpy as np
from pathlib import Path

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def export_model(pt_path: Path, output_onnx: Path, imgsz_h: int = 384, imgsz_w: int = 640):
    try:
        from ultralytics import YOLO
    except ImportError:
        print('❌ 未检测到 ultralytics 包，请先在终端运行:')
        print('   .\\toolkit\\python.exe -m pip install ultralytics')
        sys.exit(1)

    if not pt_path.exists():
        print(f'❌ 权重文件不存在: {pt_path}')
        sys.exit(1)

    print(f'📦 正在从 {pt_path} 导出 ONNX 模型...')
    print(f'   画幅规格: {imgsz_w}x{imgsz_h}, opset: 17, simplify: True')

    model = YOLO(str(pt_path))
    exported_file = model.export(
        format='onnx',
        imgsz=(imgsz_h, imgsz_w),
        dynamic=False,
        simplify=True,
        opset=17
    )

    output_onnx.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(exported_file, output_onnx)
    print(f'✅ ONNX 模型已成功部署至: {output_onnx}')

    # 清理 weights 目录下遗留的中间 onnx 冗余副本 (已归档至 models/ 目录)
    if Path(exported_file).resolve() != output_onnx.resolve() and Path(exported_file).exists():
        try:
            Path(exported_file).unlink(missing_ok=True)
        except Exception:
            pass

    return output_onnx


def benchmark_onnx(onnx_path: Path):
    """使用本地纯 Python 开源 Tracker 验证模型结构与基准延迟"""
    print('\n🧪 正在使用 OAS 开源 Tracker 验证模型推理...')
    import onnxruntime as ort
    from tasks.Hyakkiyakou.tracker import Tracker

    tracker = Tracker({'model_path': str(onnx_path), 'conf_threshold': 0.5, 'iou_threshold': 0.6})
    
    # 模拟真实百鬼夜行 1280x720 画面
    dummy_frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)

    # 预热
    for _ in range(5):
        _ = tracker(dummy_frame)

    # 测速 30 帧
    latencies = []
    for _ in range(30):
        t0 = time.perf_counter()
        _ = tracker(dummy_frame)
        latencies.append((time.perf_counter() - t0) * 1000)

    avg_ms = np.mean(latencies)
    fps = 1000.0 / avg_ms
    print(f'⚡ 基准测试结果: 单帧推理延迟 {avg_ms:.2f} ms | 等效帧率 {fps:.1f} FPS')
    if avg_ms < 50:
        print('🎉 性能非常优秀，完全满足实战动态追踪要求！')
    elif avg_ms < 100:
        print('👍 性能良好，可平稳运行。')
    else:
        print('⚠️ 推理延迟偏高，建议检查硬件加速或改用 imgsz=(384, 640)。')


def main():
    parser = argparse.ArgumentParser(description='OAS 百鬼夜行 ONNX 导出与测速工具')
    parser.add_argument('--weights', type=str, default='runs/hyakki/yolo11s_train/weights/best.pt', help='训练权重路径')
    parser.add_argument('--output', type=str, default='models/hyakki/yolo11s.onnx', help='ONNX 输出路径')
    parser.add_argument('--imgsz-h', type=int, default=384, help='输入高度')
    parser.add_argument('--imgsz-w', type=int, default=640, help='输入宽度')
    parser.add_argument('--benchmark-only', action='store_true', help='仅对现有 ONNX 进行测速')
    args = parser.parse_args()

    output_path = Path(args.output)

    if not args.benchmark_only:
        export_model(Path(args.weights), output_path, args.imgsz_h, args.imgsz_w)

    benchmark_onnx(output_path)


if __name__ == '__main__':
    main()
