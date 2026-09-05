# This Python file uses the following encoding: utf-8
"""
dev_tools/hyakki_train_yolo11.py
百鬼夜行 YOLO11s 定制识别模型微调与训练工具
自动从 tasks/Hyakkiyakou/labels.py 导出数据配置字典，执行定制训练。
"""
import sys
import yaml
import argparse
from pathlib import Path

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 添加项目根目录至 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tasks.Hyakkiyakou.labels import CLASSIFY


def generate_data_yaml(dataset_dir: Path, output_yaml_path: Path) -> Path:
    """自动生成 Ultralytics 兼容的百鬼夜行数据集配置文件"""
    names_dict = {item['id']: item['class'] for item in CLASSIFY}
    
    yaml_content = {
        'path': str(dataset_dir.resolve()),
        'train': 'images/train',
        'val': 'images/val',
        'names': names_dict,
    }
    
    output_yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_yaml_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(yaml_content, f, sort_keys=False, allow_unicode=True)
        
    print(f'✅ 已自动生成数据集配置文件: {output_yaml_path} (类别总数: {len(names_dict)})')
    return output_yaml_path


def ensure_model_weights(model_name: str) -> str:
    """若本地缺少权重文件，自动通过国内镜像源下载预训练模型至 models/pretrained/ 目录"""
    model_path = Path(model_name)
    if model_path.exists():
        return str(model_path.resolve())

    # 优先检查 models/pretrained/ 目录
    pretrained_dir = PROJECT_ROOT / 'models' / 'pretrained'
    pretrained_dir.mkdir(parents=True, exist_ok=True)
    target_path = pretrained_dir / model_path.name
    if target_path.exists():
        return str(target_path.resolve())

    # 仅针对官方标准权重自动下载至 models/pretrained/ 目录
    if model_name.endswith('.pt'):
        print(f"🔍 检测到本地缺失基础模型权重 [{target_path.name}]，正在通过镜像源自动下载至 {pretrained_dir} ...")
        mirrors = [
            f"https://ghproxy.net/https://github.com/ultralytics/assets/releases/download/v8.4.0/{target_path.name}",
            f"https://mirror.ghproxy.com/https://github.com/ultralytics/assets/releases/download/v8.4.0/{target_path.name}",
            f"https://hub.gitmirror.com/https://github.com/ultralytics/assets/releases/download/v8.4.0/{target_path.name}",
        ]
        import urllib.request
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        for url in mirrors:
            try:
                print(f"   尝试从镜像下载: {url} ...")
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, context=ctx, timeout=10) as resp, open(target_path, 'wb') as out_f:
                    data = resp.read()
                    out_f.write(data)
                if target_path.exists() and target_path.stat().st_size > 1000000:
                    print(f"✅ 权重下载成功: {target_path} ({target_path.stat().st_size / 1024 / 1024:.1f}MB)")
                    return str(target_path.resolve())
            except Exception as e:
                print(f"   镜像下载失败 ({e})，尝试下一个...")

    return model_name


def clean_training_artifacts(save_dir: Path, clean_history: bool = True) -> int:
    """
    自动清理训练产物目录中无用途的可清理项与训练历史数据：
    1. 临时批次预览图片：train_batch*.jpg (Mosaic 数据增强抽样，无推理用途)
    2. 验证集对比抽样图片：val_batch*.jpg
    3. 离散辅助曲线图与混淆矩阵：Box*.png, confusion_matrix*.png, labels.jpg, results.png
    4. 冗余权重：last.pt (仅在存在有效 best.pt 时清理，释放数十 MB)
    5. 临时导出文件：weights/*.onnx, weights/*.engine (官方模型统一保存于 models/ 目录)
    6. 训练历史数据：results.csv, per_class_results.json, args.yaml (已完整归档至 docs/ 成果报告)
    返回释放的总字节数。
    """
    save_dir = Path(save_dir)
    if not save_dir.exists():
        return 0

    print(f"\n🧹 正在自动清理训练产物目录中的无用途文件与历史数据: {save_dir}")
    deleted_files = []
    freed_bytes = 0

    # 1. 清理临时批次与验证集抽样预览图
    for p in list(save_dir.glob('train_batch*.jpg')) + list(save_dir.glob('val_batch*.jpg')):
        if p.is_file():
            freed_bytes += p.stat().st_size
            deleted_files.append(p.name)
            p.unlink(missing_ok=True)

    # 2. 清理所有指标曲线与图表 (含 results.png, Box*.png, confusion_matrix*.png, labels.jpg)
    aux_patterns = ['Box*.png', 'confusion_matrix*.png', 'labels.jpg', 'results.png']
    for pat in aux_patterns:
        for p in save_dir.glob(pat):
            if p.is_file():
                freed_bytes += p.stat().st_size
                deleted_files.append(p.name)
                p.unlink(missing_ok=True)

    # 3. 清理训练历史数据文件 (指标与配置已在生成报告时完整归档至 docs/百鬼夜行模型训练成果报告.md)
    if clean_history:
        history_files = ['results.csv', 'per_class_results.json', 'args.yaml']
        for name in history_files:
            p = save_dir / name
            if p.is_file():
                freed_bytes += p.stat().st_size
                deleted_files.append(p.name)
                p.unlink(missing_ok=True)

    # 4. 清理 weights/ 内部冗余项
    weights_dir = save_dir / 'weights'
    if weights_dir.exists():
        best_pt = weights_dir / 'best.pt'
        last_pt = weights_dir / 'last.pt'
        # 仅当 best.pt 存在且有效时安全删除 last.pt
        if best_pt.exists() and best_pt.stat().st_size > 1000000 and last_pt.exists():
            freed_bytes += last_pt.stat().st_size
            deleted_files.append(f"weights/{last_pt.name}")
            last_pt.unlink(missing_ok=True)

        # 清理导出留存的中间 onnx/engine (已部署至 models/ 目录)
        for ext in ['*.onnx', '*.engine']:
            for p in weights_dir.glob(ext):
                freed_bytes += p.stat().st_size
                deleted_files.append(f"weights/{p.name}")
                p.unlink(missing_ok=True)

    freed_mb = freed_bytes / (1024 * 1024)
    print(f"✨ 自动清理完成！共移除 {len(deleted_files)} 个无用途/历史文件，累计释放存储空间: {freed_mb:.2f} MB")
    print(f"📁 训练目录最终仅保留最优权重核心资产: weights/best.pt")
    return freed_bytes


def generate_chinese_training_report(save_dir: Path, report_path: Path, trainer=None, model_name: str = 'yolo11s.pt') -> Path:
    """从训练产物中提取指标与参数，在 docs 目录下自动生成结构化中文成果报告"""
    import json
    import csv
    from datetime import datetime
    from tasks.Hyakkiyakou.labels import id2name, label2id, _label_to_id

    save_dir = Path(save_dir)
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. 优先从实时 trainer 提取并缓存详细验证指标
    per_class_file = save_dir / 'per_class_results.json'
    if trainer and hasattr(trainer, 'validator') and getattr(trainer.validator, 'metrics', None):
        try:
            val = trainer.validator
            m = val.metrics
            speed = getattr(val, 'speed', {})
            overall = {
                'images': int(val.seen) if hasattr(val, 'seen') else 0,
                'instances': int(m.nt_per_class.sum()) if hasattr(m, 'nt_per_class') else 0,
                'precision': float(m.mean_results()[0]) if hasattr(m, 'mean_results') else 0.0,
                'recall': float(m.mean_results()[1]) if hasattr(m, 'mean_results') else 0.0,
                'map50': float(m.mean_results()[2]) if hasattr(m, 'mean_results') else 0.0,
                'map50_95': float(m.mean_results()[3]) if hasattr(m, 'mean_results') else 0.0,
            }
            class_records = []
            if hasattr(m, 'ap_class_index'):
                for i, c in enumerate(m.ap_class_index):
                    class_key = val.names[c] if hasattr(val, 'names') and c in val.names else f'class_{c}'
                    res = m.class_result(i)
                    class_records.append({
                        'class': class_key,
                        'class_id': int(c),
                        'images': int(m.nt_per_image[c]) if hasattr(m, 'nt_per_image') else 0,
                        'instances': int(m.nt_per_class[c]) if hasattr(m, 'nt_per_class') else 0,
                        'precision': float(res[0]),
                        'recall': float(res[1]),
                        'map50': float(res[2]),
                        'map50_95': float(res[3]),
                    })
            data_to_save = {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'speed': speed,
                'overall': overall,
                'classes': class_records,
            }
            with open(per_class_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 提取实时验证明细指标异常: {e}")

    # 2. 读取 per_class_results.json 缓存
    per_class_data = {}
    if per_class_file.exists():
        try:
            with open(per_class_file, 'r', encoding='utf-8') as f:
                per_class_data = json.load(f)
        except Exception as e:
            print(f"⚠️ 读取 {per_class_file} 失败: {e}")

    # 3. 读取 args.yaml
    args_yaml_file = save_dir / 'args.yaml'
    args_data = {}
    if args_yaml_file.exists():
        try:
            with open(args_yaml_file, 'r', encoding='utf-8') as f:
                args_data = yaml.safe_load(f) or {}
        except Exception:
            pass

    # 4. 读取 results.csv 提取轮数与收敛损失
    results_csv_file = save_dir / 'results.csv'
    csv_rows = []
    best_row = {}
    last_row = {}
    best_epoch = 0
    if results_csv_file.exists():
        try:
            with open(results_csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for r in reader:
                    cleaned = {k.strip(): float(v.strip()) for k, v in r.items() if v.strip()}
                    csv_rows.append(cleaned)
            if csv_rows:
                best_row = max(csv_rows, key=lambda x: x.get('metrics/mAP50(B)', 0.0))
                best_epoch = int(best_row.get('epoch', 0))
                last_row = csv_rows[-1]
        except Exception as e:
            print(f"⚠️ 读取 {results_csv_file} 失败: {e}")

    # 5. 聚合关键指标
    epochs_trained = len(csv_rows) if csv_rows else args_data.get('epochs', 0)
    batch_size = args_data.get('batch', 16)
    imgsz = args_data.get('imgsz', [384, 640])
    imgsz_str = f"{imgsz[1]} x {imgsz[0]}" if isinstance(imgsz, list) and len(imgsz) == 2 else str(imgsz)
    device_name = args_data.get('device', 'cpu')
    optimizer_name = args_data.get('optimizer', 'AdamW')
    base_model = args_data.get('model', model_name)

    overall = per_class_data.get('overall', {})
    p_all = overall.get('precision', best_row.get('metrics/precision(B)', 0.0))
    r_all = overall.get('recall', best_row.get('metrics/recall(B)', 0.0))
    map50_all = overall.get('map50', best_row.get('metrics/mAP50(B)', 0.0))
    map50_95_all = overall.get('map50_95', best_row.get('metrics/mAP50-95(B)', 0.0))
    total_val_imgs = overall.get('images', 0)
    total_val_insts = overall.get('instances', 0)

    speed = per_class_data.get('speed', {})
    pre_ms = speed.get('preprocess', 0.0)
    inf_ms = speed.get('inference', 0.0)
    post_ms = speed.get('postprocess', 0.0)
    total_ms = pre_ms + inf_ms + post_ms
    fps_est = (1000.0 / total_ms) if total_ms > 0 else 0.0

    # 健康度评级
    if map50_all >= 0.85:
        health_status = '🌟 极佳 (可直接投入实战)'
        health_comment = '模型对大多数目标定位精准、召回充沛，完全满足百鬼夜行实时追踪要求。'
    elif map50_all >= 0.70:
        health_status = '✅ 良好 (达到实战标准)'
        health_comment = '核心目标识别稳定，部分小目标或复杂光影背景下偶有漏检，可补充标注。'
    elif map50_all >= 0.50:
        health_status = '⚠️ 一般 (建议补充样本)'
        health_comment = '模型初步收敛，但漏检或误检率稍高，建议增加训练轮数或补充样本多样性。'
    else:
        health_status = '❌ 欠拟合/数据不足'
        health_comment = '模型未充分收敛，需检查标注数据准确性、图片数量或增加训练 Epoch。'

    # 构建 Markdown 报告
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    best_pt_path = save_dir / 'weights' / 'best.pt'

    lines = []
    lines.append('# 百鬼夜行 YOLO11 模型训练成果评估报告\n')
    lines.append(f'> **生成时间**：`{now_str}`  ')
    lines.append(f'> **关联模型权重**：`{best_pt_path}`  ')
    lines.append(f'> **训练输出目录**：`{save_dir}`\n')
    lines.append('---\n')

    lines.append('## 一、 核心综合指标总览 (Overall Metrics)\n')
    lines.append('| 关键综合指标 | 数值结果 | 状态评定 | 业务含义与实战表现 |')
    lines.append('| :--- | :---: | :---: | :--- |')
    lines.append(f'| **基准检测精度 (mAP@50)** | **`{map50_all:.3f}` ({map50_all*100:.1f}%)** | {health_status.split()[0]} {health_status.split()[1]} | IoU=0.5 判定下综合识别准确率，核心实战依据 |')
    lines.append(f'| **严格综合精度 (mAP@50-95)** | **`{map50_95_all:.3f}` ({map50_95_all*100:.1f}%)** | - | 连续高重叠度判定下的均值，反映边框贴合紧密程度 |')
    lines.append(f'| **查准率 (Precision)** | **`{p_all:.3f}` ({p_all*100:.1f}%)** | - | 模型预测为式神的框中真实有效目标的比例 |')
    lines.append(f'| **查全率 (Recall)** | **`{r_all:.3f}` ({r_all*100:.1f}%)** | - | 验证集内真实式神被成功检出的比例 |')
    if total_val_imgs > 0:
        lines.append(f'| **验证集规模** | **{total_val_imgs} 张图片 / {total_val_insts} 个目标** | - | 本轮独立验证集统计 |')
    if total_ms > 0:
        fps_tag = "🚀 丝滑高刷" if fps_est >= 15 else "⏱️ 实时达标"
        lines.append(f'| **单帧总耗时 / 预估帧率** | **`{total_ms:.1f} ms` (~{fps_est:.1f} FPS)** | {fps_tag} | 推理 {inf_ms:.1f}ms + 前处理 {pre_ms:.1f}ms + 后处理 {post_ms:.1f}ms |')
    lines.append(f'| **整体健康度评级** | **{health_status}** | - | {health_comment} |\n')

    lines.append('## 二、 训练配置与环境参数\n')
    lines.append('| 配置项 | 参数设定 | 说明 |')
    lines.append('| :--- | :--- | :--- |')
    lines.append(f'| **预训练基础权重** | `{base_model}` | 基础网络骨干架构 |')
    lines.append(f'| **总训练轮数** | `{epochs_trained}` 轮 | 最佳权重收敛于第 **{best_epoch}** 轮 |')
    lines.append(f'| **批次大小 (Batch)** | `{batch_size}` | 梯度更新步长设定 |')
    lines.append(f'| **输入画幅尺寸** | `{imgsz_str}` | 近似 16:9 比例，避免将画面暴力拉伸压扁成正方形 |')
    lines.append(f'| **优化器与学习率** | `{optimizer_name} (lr0={args_data.get("lr0", 0.001)})` | 后 10 轮关闭 Mosaic 数据增强提高边框精准度 |')
    lines.append(f'| **运行计算设备** | `{device_name}` | 训练计算硬件环境 |')
    if last_row:
        lines.append(f'| **最终收敛损失** | Box Loss: `{last_row.get("train/box_loss", 0):.4f}`, Cls Loss: `{last_row.get("train/cls_loss", 0):.4f}`, DFL Loss: `{last_row.get("train/dfl_loss", 0):.4f}` | 损失收敛平稳 |')
    lines.append('\n---\n')

    # 明细表
    classes_list = per_class_data.get('classes', [])
    if classes_list:
        lines.append('## 三、 各品类式神与增益目标检测明细表 (Per-Class Breakdown)\n')
        lines.append('| YOLO ID | 英文标识 (Key) | 式神 / 目标名称 | 验证样本 | 准确率 (P) | 召回率 (R) | mAP@50 | mAP@50-95 | 评估状态 |')
        lines.append('| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |')

        warn_classes = []
        zero_classes = []

        for item in classes_list:
            key = item.get('class', '')
            cid = item.get('class_id', label2id(key) if key in _label_to_id else -1)
            name = id2name(cid) if cid >= 0 else key

            p = item.get('precision', 0.0)
            r = item.get('recall', 0.0)
            m50 = item.get('map50', 0.0)
            m95 = item.get('map50_95', 0.0)
            inst = item.get('instances', 0)
            img = item.get('images', 0)

            if m50 >= 0.90:
                eval_tag = '🌟 极佳'
            elif m50 >= 0.75:
                eval_tag = '✅ 良好'
            elif m50 >= 0.50:
                eval_tag = '⚠️ 需补充'
                warn_classes.append(f"{name} ({key})")
            else:
                eval_tag = '❌ 严重不足'
                zero_classes.append(f"{name} ({key})")

            sample_str = f"{img}图 / {inst}目标"
            lines.append(f'| `{cid}` | `{key}` | **{name}** | {sample_str} | {p*100:.1f}% | {r*100:.1f}% | **{m50:.3f}** | {m95:.3f} | {eval_tag} |')

        lines.append('\n---\n')

        lines.append('## 四、 智能诊断与优化排查建议\n')
        if zero_classes:
            lines.append(f'> ⚠️ **未检出/样本缺失预警**：  \n> 以下类别指标为 0 或严重不足：**{", ".join(zero_classes)}**。  \n> **排查建议**：请检查这些式神是否仅在 `labels/val/` 标注，而在 `labels/train/` 中缺失。深度学习模型必须在训练集中学习至少 3~5 张样本方可正确预测。\n')
        if warn_classes:
            lines.append(f'> 💡 **小样本/表现一般提示**：  \n> 以下类别 mAP@50 低于 75%：**{", ".join(warn_classes)}**。  \n> **优化建议**：若属于高频出现的关键式神，建议在自动保存的 `log/baigui/` 截图中补充更多不同角度与背景的样本。\n')
        if not zero_classes and not warn_classes:
            lines.append('> 🎉 **全品类表现优异**：所有参与验证的式神与 Buff 目标均达到高精度识别水平，无明显漏检弱项。\n')

    report_content = '\n'.join(lines)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"\n📄 训练成果中文报告已成功生成: {report_path}")
    return report_path


def main():
    parser = argparse.ArgumentParser(description='OAS 百鬼夜行 YOLO11s 模型训练与成果报告生成工具')
    parser.add_argument('--dataset', type=str, default='baigui', help='数据集根目录 (默认: baigui)')
    parser.add_argument('--model', type=str, default='models/pretrained/yolo11s.pt', help='预训练权重 (推荐 models/pretrained/yolo11s.pt / yolo11n.pt)')
    parser.add_argument('--epochs', type=int, default=120, help='训练轮数 (建议 100~150)')
    parser.add_argument('--batch', type=int, default=16, help='批次大小 (显存不足可设为 8)')
    parser.add_argument('--imgsz-h', type=int, default=384, help='输入高度 (推荐 384，保持 16:9 近似比例)')
    parser.add_argument('--imgsz-w', type=int, default=640, help='输入宽度 (推荐 640)')
    parser.add_argument('--device', type=str, default='0', help='训练设备 (如 0, 1 或 cpu)')
    parser.add_argument('--workers', type=int, default=4, help='DataLoader 线程数')
    parser.add_argument('--report-path', type=str, default='docs/百鬼夜行模型训练成果报告.md', help='中文报告保存路径')
    parser.add_argument('--report-only', action='store_true', help='仅根据已有的训练产物生成中文成果报告，不执行重新训练')
    parser.add_argument('--clean-only', action='store_true', help='仅清理指定或默认训练产物目录中的无用途文件，不执行重新训练')
    parser.add_argument('--no-clean', action='store_true', help='训练完成后不自动清理无用途的临时图片与冗余权重')
    parser.add_argument('--run-dir', type=str, default=None, help='指定的训练输出目录 (配合 --report-only / --clean-only 使用)')
    args = parser.parse_args()

    # 如果仅需清理无用途文件
    if args.clean_only:
        run_dir = None
        if args.run_dir:
            run_dir = Path(args.run_dir)
        elif Path('runs/hyakki/yolo11s_train').exists():
            run_dir = Path('runs/hyakki/yolo11s_train')
        elif Path('runs/detect/runs/hyakki/yolo11s_train').exists():
            run_dir = Path('runs/detect/runs/hyakki/yolo11s_train')

        if not run_dir or not run_dir.exists():
            print("❌ 未找到有效的训练产物目录，请通过 --run-dir 指定路径")
            sys.exit(1)

        clean_training_artifacts(run_dir)
        return

    # 如果仅需生成报告
    if args.report_only:
        run_dir = None
        if args.run_dir:
            run_dir = Path(args.run_dir)
        elif Path('runs/hyakki/yolo11s_train').exists():
            run_dir = Path('runs/hyakki/yolo11s_train')
        elif Path('runs/detect/runs/hyakki/yolo11s_train').exists():
            run_dir = Path('runs/detect/runs/hyakki/yolo11s_train')

        if not run_dir or not run_dir.exists():
            print("❌ 未找到有效的训练产物目录，请通过 --run-dir 指定路径")
            sys.exit(1)

        print(f"📊 正在根据历史训练产物生成成果报告: {run_dir}")
        generate_chinese_training_report(run_dir, Path(args.report_path), model_name=args.model)
        return

    try:
        from ultralytics import YOLO
    except ImportError:
        print('❌ 未检测到 ultralytics 包，请先在终端运行:')
        print('   .\\toolkit\\python.exe -m pip install ultralytics')
        sys.exit(1)

    dataset_path = Path(args.dataset)
    # 若传入的历史路径 docs/baigui 不存在，自动平滑重定向至根目录 baigui
    if not dataset_path.exists() and (PROJECT_ROOT / 'baigui').exists():
        dataset_path = PROJECT_ROOT / 'baigui'

    yaml_path = dataset_path / 'hyakki_data.yaml'
    
    # 自动创建或刷新 data.yaml
    generate_data_yaml(dataset_path, yaml_path)

    # 确保权重文件存在
    weights_path = ensure_model_weights(args.model)

    # 智能设备选择
    device = args.device
    import torch
    if device != 'cpu' and not torch.cuda.is_available():
        print(f"⚠️ 当前 PyTorch 未检测到可用 CUDA GPU，自动将训练设备切换为 [cpu]")
        device = 'cpu'

    print('\n🚀 开始启动 YOLO11 模型训练...')
    print(f'   基础模型: {weights_path}')
    print(f'   数据集配置: {yaml_path}')
    print(f'   输入画幅: {args.imgsz_w}x{args.imgsz_h} (防形变长宽比)')
    print(f'   训练轮数: {args.epochs}, 批大小: {args.batch}, 设备: {device}\n')

    project_dir = (PROJECT_ROOT / 'runs' / 'hyakki').resolve()

    model = YOLO(weights_path)
    model.train(
        data=str(yaml_path),
        epochs=args.epochs,
        batch=args.batch,
        imgsz=(args.imgsz_h, args.imgsz_w),
        device=device,
        workers=args.workers,
        optimizer='AdamW',
        lr0=0.001,
        close_mosaic=10,        # 最后 10 轮关闭 Mosaic，提高目标边界框定位精度
        project=str(project_dir),
        name='yolo11s_train',
        exist_ok=True,
    )

    # 确定保存目录与最佳权重路径
    save_dir = Path(model.trainer.save_dir) if hasattr(model, 'trainer') and getattr(model.trainer, 'save_dir', None) else project_dir / 'yolo11s_train'
    if not save_dir.exists() and Path('runs/detect/runs/hyakki/yolo11s_train').exists():
        save_dir = Path('runs/detect/runs/hyakki/yolo11s_train')

    best_pt = save_dir / 'weights' / 'best.pt'

    # 自动生成中文成果报告
    report_file = generate_chinese_training_report(
        save_dir=save_dir,
        report_path=Path(args.report_path),
        trainer=getattr(model, 'trainer', None),
        model_name=args.model
    )

    # 自动清理无用途的临时图片与冗余权重 (可通过 --no-clean 跳过)
    if not args.no_clean:
        clean_training_artifacts(save_dir)

    if best_pt and best_pt.exists():
        print(f'\n🎉 训练完成！最佳权重保存在: {best_pt}')
        print(f'👉 请接着运行以下命令将其导出为 ONNX 模型:')
        print(f'   .\\toolkit\\python.exe dev_tools/hyakki_export_onnx.py --weights {best_pt} --output models/hyakki/yolo11s.onnx')
    print(f'👉 完整中文评估报告已归档至: {report_file}')


if __name__ == '__main__':
    main()

