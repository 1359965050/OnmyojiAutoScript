# This Python file uses the following encoding: utf-8
"""
tasks/Hyakkiyakou/tracker.py
OAS 百鬼夜行纯 Python 开源检测器与多目标跟踪器
支持 YOLO11s 与 YOLOv10 ONNX 模型自适应推理，内置 DirectML / CUDA / CPU 硬件加速选择。
"""
import os
import cv2
import numpy as np
import onnxruntime as ort
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from module.logger import logger
from module.exception import RequestHumanTakeover

# Fernet 密钥，用于在未部署自定义模型时无缝解密基准模型
_FERNET_KEY = b'Z8Nj6PzDEA0YlybHb6-_oUaSuO0FpZqY0ntcIH1GviU='

# 原版 baseline 模型 (219 类) 的标签序列，用于将旧模型输出的类别映射到当前扩充后的类别 ID
_LEGACY_BASELINE_KEYS = (
    [f"buff_{i:03d}" for i in range(1, 8)]
    + [f"n_{i:03d}" for i in range(1, 13)]
    + [f"g_{i:03d}" for i in range(1, 18)]
    + [f"r_{i:03d}" for i in range(1, 38)]
    + [f"sr_{i:03d}" for i in range(1, 66)]
    + [f"ssr_{i:03d}" for i in range(1, 47)]
    + [f"sp_{i:03d}" for i in range(1, 36)]
)


def _build_legacy_baseline_map() -> dict[int, int]:
    try:
        from tasks.Hyakkiyakou.labels import label2id
        mapping = {}
        for old_id, key in enumerate(_LEGACY_BASELINE_KEYS):
            mapping[old_id] = label2id(key)
        return mapping
    except Exception as e:
        logger.warning(f"Failed to build legacy baseline label mapping: {e}")
        return {}


_BASELINE_TO_CURRENT_MAP = _build_legacy_baseline_map()


def _get_new_class_ids() -> set[int]:
    """获取所有扩充的新式神类别 ID (基准 baseline 模型无法识别的式神)"""
    try:
        from tasks.Hyakkiyakou.labels import CLASSIFY
        known_by_baseline = set(_BASELINE_TO_CURRENT_MAP.values())
        return {item['id'] for item in CLASSIFY if item['id'] not in known_by_baseline}
    except Exception:
        return set(range(186, 202)) | set(range(237, 253)) | {19, 139}


_NEW_CLASS_IDS = _get_new_class_ids()


class SingleDetectorEngine:
    """单个 ONNX Session 检测引擎 (负责预处理、推理与后处理)"""
    def __init__(self, session: ort.InferenceSession, is_legacy_baseline: bool,
                 conf_thresh: float = 0.5, iou_thresh: float = 0.6):
        self.session = session
        self.is_legacy_baseline = is_legacy_baseline
        self.conf_thresh = float(conf_thresh)
        self.iou_thresh = float(iou_thresh)
        self._inspect_io()

    def _inspect_io(self):
        """解析输入与输出维度规格"""
        input_meta = self.session.get_inputs()[0]
        self.input_name = input_meta.name
        shape = input_meta.shape
        
        # 获取预期的图片长宽 (默认 384x640 或 640x640)
        self.input_h = shape[2] if len(shape) == 4 and isinstance(shape[2], int) and shape[2] > 0 else 384
        self.input_w = shape[3] if len(shape) == 4 and isinstance(shape[3], int) and shape[3] > 0 else 640
        logger.info(f'Hyakki Detector ({ "Baseline" if self.is_legacy_baseline else "Custom" }) resolution: {self.input_w}x{self.input_h}')

        output_meta = self.session.get_outputs()[0]
        self.output_name = output_meta.name
        out_shape = output_meta.shape
        logger.info(f'Hyakki Detector ({ "Baseline" if self.is_legacy_baseline else "Custom" }) output shape: {out_shape}')
        
        # 判断是 YOLOv10 (NMS-Free, [1, 300, 6]) 还是 YOLO11 ([1, 4+C, N])
        self.is_yolov10_nms_free = (len(out_shape) == 3 and out_shape[2] == 6)

    def preprocess(self, img_bgr: np.ndarray):
        """缩放与填充预处理"""
        h, w = img_bgr.shape[:2]

        if self.is_legacy_baseline:
            img_resized = cv2.resize(img_bgr, (self.input_w, self.input_h), interpolation=cv2.INTER_LINEAR)
            tensor = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            tensor = np.transpose(tensor, (2, 0, 1))
            tensor = np.expand_dims(tensor, axis=0)
            return tensor, 1.0, 0.0, 0.0

        r = min(self.input_h / h, self.input_w / w)
        new_unpad_w = int(round(w * r))
        new_unpad_h = int(round(h * r))
        dw = (self.input_w - new_unpad_w) / 2.0
        dh = (self.input_h - new_unpad_h) / 2.0

        if (w, h) != (new_unpad_w, new_unpad_h):
            img_resized = cv2.resize(img_bgr, (new_unpad_w, new_unpad_h), interpolation=cv2.INTER_LINEAR)
        else:
            img_resized = img_bgr

        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        padded = cv2.copyMakeBorder(img_resized, top, bottom, left, right,
                                    cv2.BORDER_CONSTANT, value=(114, 114, 114))

        tensor = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))
        tensor = np.expand_dims(tensor, axis=0)
        return tensor, r, dw, dh

    def postprocess(self, outputs, r: float, dw: float, dh: float, orig_shape: tuple) -> list[dict]:
        """统一将模型预测输出转换为绝对坐标 [cx, cy, w, h]"""
        raw = outputs[0]
        orig_h, orig_w = orig_shape
        detections = []

        if self.is_yolov10_nms_free:
            preds = raw[0]
            mask = preds[:, 4] >= self.conf_thresh
            valid_preds = preds[mask]
            
            for item in valid_preds:
                x1, y1, x2, y2, conf, cls_id = item
                cls_id = int(cls_id)
                if self.is_legacy_baseline:
                    x1 = float(x1) * (orig_w / float(self.input_w))
                    y1 = float(y1) * (orig_h / float(self.input_h))
                    x2 = float(x2) * (orig_w / float(self.input_w))
                    y2 = float(y2) * (orig_h / float(self.input_h))
                    cls_id = _BASELINE_TO_CURRENT_MAP.get(cls_id, cls_id)
                else:
                    x1 = (x1 - dw) / r
                    y1 = (y1 - dh) / r
                    x2 = (x2 - dw) / r
                    y2 = (y2 - dh) / r
                
                x1 = max(0.0, min(float(orig_w), float(x1)))
                y1 = max(0.0, min(float(orig_h), float(y1)))
                x2 = max(0.0, min(float(orig_w), float(x2)))
                y2 = max(0.0, min(float(orig_h), float(y2)))
                
                bw = max(1.0, x2 - x1)
                bh = max(1.0, y2 - y1)
                cx = x1 + bw / 2.0
                cy = y1 + bh / 2.0
                
                detections.append({
                    'class': int(cls_id),
                    'conf': float(conf),
                    'cx': float(cx),
                    'cy': float(cy),
                    'w': float(bw),
                    'h': float(bh)
                })
        else:
            preds = raw[0]
            if preds.shape[0] < preds.shape[1]:
                preds = np.transpose(preds, (1, 0))

            boxes = preds[:, :4]
            scores = preds[:, 4:]

            class_ids = np.argmax(scores, axis=1)
            confidences = np.max(scores, axis=1)

            mask = confidences >= self.conf_thresh
            if not np.any(mask):
                return []

            valid_boxes = boxes[mask]
            valid_confs = confidences[mask]
            valid_classes = class_ids[mask]

            if self.is_legacy_baseline:
                scale_x = orig_w / float(self.input_w)
                scale_y = orig_h / float(self.input_h)
                cx = valid_boxes[:, 0] * scale_x
                cy = valid_boxes[:, 1] * scale_y
                bw = valid_boxes[:, 2] * scale_x
                bh = valid_boxes[:, 3] * scale_y
            else:
                cx = (valid_boxes[:, 0] - dw) / r
                cy = (valid_boxes[:, 1] - dh) / r
                bw = valid_boxes[:, 2] / r
                bh = valid_boxes[:, 3] / r

            x1 = np.clip(cx - bw / 2.0, 0, orig_w)
            y1 = np.clip(cy - bh / 2.0, 0, orig_h)
            x2 = np.clip(cx + bw / 2.0, 0, orig_w)
            y2 = np.clip(cy + bh / 2.0, 0, orig_h)

            nms_boxes = [[int(x1[i]), int(y1[i]), int(x2[i] - x1[i]), int(y2[i] - y1[i])]
                         for i in range(len(x1))]
            
            indices = cv2.dnn.NMSBoxes(nms_boxes, valid_confs.tolist(), self.conf_thresh, self.iou_thresh)
            if len(indices) > 0:
                for idx in indices.flatten():
                    c_id = int(valid_classes[idx])
                    if self.is_legacy_baseline:
                        c_id = _BASELINE_TO_CURRENT_MAP.get(c_id, c_id)
                    detections.append({
                        'class': c_id,
                        'conf': float(valid_confs[idx]),
                        'cx': float(cx[idx]),
                        'cy': float(cy[idx]),
                        'w': float(bw[idx]),
                        'h': float(bh[idx])
                    })

        return detections

    def detect(self, img_bgr: np.ndarray) -> list[dict]:
        """单帧检测执行"""
        if self.is_legacy_baseline:
            h, w = img_bgr.shape[:2]
            crop_h = min(640, h)
            left_crop = img_bgr[0:crop_h, 0:640]
            right_crop = img_bgr[0:crop_h, 640:1280]

            def _infer_single_crop(crop, offset_x=0.0):
                ch, cw = crop.shape[:2]
                if (cw, ch) != (self.input_w, self.input_h):
                    crop_resized = cv2.resize(crop, (self.input_w, self.input_h), interpolation=cv2.INTER_LINEAR)
                else:
                    crop_resized = crop
                tensor = cv2.cvtColor(crop_resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                tensor = np.transpose(tensor, (2, 0, 1))[np.newaxis, ...]
                outputs = self.session.run([self.output_name], {self.input_name: tensor})
                preds = outputs[0][0]
                mask = preds[:, 4] >= self.conf_thresh
                valid = preds[mask]
                dets = []
                for x1, y1, x2, y2, conf, cls_id in valid:
                    cls_id = int(cls_id)
                    mapped_cls = _BASELINE_TO_CURRENT_MAP.get(cls_id, cls_id)
                    bw = float(x2 - x1)
                    bh = float(y2 - y1)
                    cx = float(x1 + bw / 2.0) + offset_x
                    cy = float(y1 + bh / 2.0)
                    dets.append({
                        'class': mapped_cls,
                        'conf': float(conf),
                        'cx': float(cx),
                        'cy': float(cy),
                        'w': float(bw),
                        'h': float(bh)
                    })
                return dets

            left_dets = _infer_single_crop(left_crop, offset_x=0.0)
            right_dets = _infer_single_crop(right_crop, offset_x=640.0)
            all_dets = left_dets + right_dets
            if len(all_dets) <= 1:
                return all_dets

            filtered = []
            all_dets.sort(key=lambda d: d['conf'], reverse=True)
            for d in all_dets:
                keep = True
                for f in filtered:
                    if d['class'] == f['class']:
                        dist = np.hypot(d['cx'] - f['cx'], d['cy'] - f['cy'])
                        if dist < 60.0:
                            keep = False
                            break
                if keep:
                    filtered.append(d)
            return filtered

        orig_shape = img_bgr.shape[:2]
        tensor, r, dw, dh = self.preprocess(img_bgr)
        outputs = self.session.run([self.output_name], {self.input_name: tensor})
        return self.postprocess(outputs, r, dw, dh, orig_shape)


class YOLOAdaptiveDetector:
    """
    自适应百鬼夜行双模型协同检测器
    核心机制：
      1. 双模型协同融合 (Dual-Model Ensemble)：
         - 基准模型 (Baseline) 负责 219 类老式神与全部 7 类增益 BUFF
         - 自定义模型 (Custom YOLO11s) 负责用户自主标注与训练的 34 类新式神
         - 多线程并行推理与空间去重合并，真正实现“用户只需补充新式神，老式神免标免管”！
      2. 独立运行保障：未放置自定义模型时，透明平滑仅运行基准模型。
    """
    def __init__(self, model_path: str = None, conf_thresh: float = 0.5, iou_thresh: float = 0.6):
        self.conf_thresh = float(conf_thresh)
        self.iou_thresh = float(iou_thresh)
        self.custom_engine: SingleDetectorEngine | None = None
        self.baseline_engine: SingleDetectorEngine | None = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self._init_engines(model_path)

    def _init_engines(self, model_path: str = None):
        """寻找可用模型并初始化 ONNX Runtime Engines"""
        available = ort.get_available_providers()
        providers = []
        if 'DmlExecutionProvider' in available:
            providers.append('DmlExecutionProvider')
            logger.info('ONNXRuntime DirectML GPU Acceleration Enabled')
        if 'CUDAExecutionProvider' in available:
            providers.append('CUDAExecutionProvider')
            logger.info('ONNXRuntime CUDA GPU Acceleration Enabled')
        providers.append('CPUExecutionProvider')

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 4

        # 1. 优先探测自定义模型
        candidate_paths = [
            model_path,
            'models/hyakki/yolo11s.onnx',
            'models/hyakki/best.onnx',
            'tasks/Hyakkiyakou/models/yolo11s.onnx',
            'tasks/Hyakkiyakou/models/best.onnx',
        ]
        target_path = None
        for p in candidate_paths:
            if p and Path(p).exists() and Path(p).is_file():
                target_path = Path(p)
                break

        if target_path:
            logger.info(f'Loading custom Hyakki model from: {target_path}')
            try:
                sess = ort.InferenceSession(str(target_path), sess_options, providers=providers)
                self.custom_engine = SingleDetectorEngine(sess, is_legacy_baseline=False,
                                                          conf_thresh=self.conf_thresh, iou_thresh=self.iou_thresh)
            except Exception as e:
                logger.error(f'Failed to load custom model: {e}')

        # 2. 加载基准模型作为 219 类老式神与 BUFF 的兜底保障
        baseline_path = Path('toolkit/Lib/site-packages/oashya/oashya_fp32.onnx')
        if baseline_path.exists():
            try:
                from cryptography.fernet import Fernet
                f = Fernet(_FERNET_KEY)
                with open(baseline_path, 'rb') as fp:
                    decrypted_bytes = f.decrypt(fp.read())
                sess = ort.InferenceSession(decrypted_bytes, sess_options, providers=providers)
                self.baseline_engine = SingleDetectorEngine(sess, is_legacy_baseline=True,
                                                            conf_thresh=self.conf_thresh, iou_thresh=self.iou_thresh)
                logger.info('Loaded baseline model (oashya_fp32.onnx) for 219 legacy classes & BUFFs')
            except Exception as e:
                logger.error(f'Failed to decrypt baseline model: {e}')

        if not self.custom_engine and not self.baseline_engine:
            raise RequestHumanTakeover(
                '百鬼夜行模型未找到！请将训练导出的 yolo11s.onnx 放置在 models/hyakki/ 目录下，或确保 oashya 安装完整。'
            )

        if self.custom_engine and self.baseline_engine:
            logger.info('[Ensemble] Hyakki Dual-Model Ensemble Active: Custom model (new shiki) + Baseline model (219 legacy & BUFFs)')

    @property
    def is_legacy_baseline(self) -> bool:
        return self.custom_engine is None and self.baseline_engine is not None

    @property
    def session(self):
        engine = self.custom_engine or self.baseline_engine
        return engine.session if engine else None

    @property
    def input_w(self):
        engine = self.custom_engine or self.baseline_engine
        return engine.input_w if engine else 640

    @property
    def input_h(self):
        engine = self.custom_engine or self.baseline_engine
        return engine.input_h if engine else 384

    def detect(self, img_bgr: np.ndarray) -> list[dict]:
        """单帧多模型融合检测入口"""
        if self.custom_engine and self.baseline_engine:
            # 双模型多线程并行推理
            fut_base = self.executor.submit(self.baseline_engine.detect, img_bgr)
            fut_custom = self.executor.submit(self.custom_engine.detect, img_bgr)
            base_dets = fut_base.result()
            custom_dets = fut_custom.result()
            return self._merge_detections(base_dets, custom_dets)
        elif self.custom_engine:
            return self.custom_engine.detect(img_bgr)
        elif self.baseline_engine:
            return self.baseline_engine.detect(img_bgr)
        return []

    def _merge_detections(self, base_dets: list[dict], custom_dets: list[dict]) -> list[dict]:
        """融合基准模型(老式神+BUFF)与自定义模型(新式神)的检测结果"""
        if not custom_dets:
            return base_dets
        if not base_dets:
            return custom_dets

        merged = list(base_dets)
        for cd in custom_dets:
            is_new = cd['class'] in _NEW_CLASS_IDS
            matched_idx = -1
            for idx, bd in enumerate(merged):
                dist = np.hypot(cd['cx'] - bd['cx'], cd['cy'] - bd['cy'])
                if dist < 60.0:
                    matched_idx = idx
                    break
            
            if matched_idx >= 0:
                # 产生位置重叠：
                # 1. 若自定义模型判定为新式神，由自定义新模型优先取代；
                # 2. 或者自定义模型置信度更高时取代
                bd = merged[matched_idx]
                if is_new or cd['conf'] >= bd['conf']:
                    merged[matched_idx] = cd
            else:
                merged.append(cd)

        return merged


class SingleTrack:
    """百鬼夜行单一目标追踪轨迹"""
    def __init__(self, track_id: int, class_id: int, conf: float, cx: float, cy: float, w: float, h: float):
        self.id = track_id
        self.class_id = class_id
        self.conf = conf
        self.cx = cx
        self.cy = cy
        self.w = w
        self.h = h
        self.vx = 0.0      # 水平速度 (像素/帧)
        self.missed = 0    # 连续丢失计数
        self.hit_count = 1

    def update(self, class_id: int, conf: float, cx: float, cy: float, w: float, h: float):
        # 推算水平运动瞬时速度
        instant_vx = cx - self.cx
        if self.hit_count == 1:
            self.vx = instant_vx
        else:
            # 指数移动平均平滑滤波 (EMA)
            self.vx = 0.7 * self.vx + 0.3 * instant_vx

        self.class_id = class_id
        self.conf = conf
        self.cx = cx
        self.cy = cy
        self.w = w
        self.h = h
        self.missed = 0
        self.hit_count += 1

    def predict(self):
        """按照水平速度向前预测下一帧位置"""
        self.cx += self.vx
        self.missed += 1


class Tracker:
    """
    OAS 纯 Python 开源多目标跟踪器
    完全兼容原版闭源 Tracker 接口与数据契约
    """
    def __init__(self, args: dict = None):
        args = args or {}
        conf = args.get('conf_threshold', 0.5)
        iou = args.get('iou_threshold', 0.6)
        model_path = args.get('model_path', None)

        self.detector = YOLOAdaptiveDetector(model_path=model_path, conf_thresh=conf, iou_thresh=iou)
        self.tracks: list[SingleTrack] = []
        self._next_id = 1
        self.max_missed = 2   # 允许连续丢失帧数容限 (防偶发漏检或受击遮挡)

    def clear_tracks(self):
        """重置所有跟踪轨迹 (单局结束时调用)"""
        self.tracks.clear()
        self._next_id = 1

    def __call__(self, image: np.ndarray, response=None) -> list[tuple]:
        """
        核心追踪调用
        @param image: 原图 BGR numpy.ndarray (720, 1280, 3)
        @param response: 上一步动作 [x, y, throw, bean]，保持与原接口完全一致
        @return: tracks 列表，格式: [(_id, _class, _conf, _cx, _cy, _w, _h, _vx), ...]
        """
        if image is None:
            return []

        # 1. 目标检测
        detections = self.detector.detect(image)

        # 2. 预测已有轨迹位置
        for t in self.tracks:
            t.predict()

        # 3. 关联匹配 (空间距离 + 类别匹配)
        unmatched_dets = list(range(len(detections)))
        matched_tracks = []

        for t in self.tracks:
            best_det_idx = -1
            min_dist = 90.0  # 像素容差阈值
            
            for d_idx in unmatched_dets:
                d = detections[d_idx]
                dcx = d['cx']
                dcy = d['cy']
                dist = np.hypot(t.cx - dcx, t.cy - dcy)
                
                # 同类优先，或同为目标且距离极近
                if dist < min_dist:
                    if d['class'] == t.class_id or dist < 40.0:
                        min_dist = dist
                        best_det_idx = d_idx

            if best_det_idx != -1:
                det = detections[best_det_idx]
                t.update(det['class'], det['conf'], det['cx'], det['cy'], det['w'], det['h'])
                matched_tracks.append(t)
                unmatched_dets.remove(best_det_idx)
            elif t.missed <= self.max_missed:
                # 暂时漏检，在容忍期内保留
                matched_tracks.append(t)

        # 4. 新目标分配 ID
        for d_idx in unmatched_dets:
            d = detections[d_idx]
            new_track = SingleTrack(self._next_id, d['class'], d['conf'],
                                    d['cx'], d['cy'], d['w'], d['h'])
            self._next_id += 1
            matched_tracks.append(new_track)

        self.tracks = matched_tracks

        # 5. 组装标准元组输出
        results = []
        for t in self.tracks:
            # 允许容忍 1 帧内的偶发遮挡，平滑预测输出
            if t.missed <= 1:
                # 速度按毫秒归一化 (px/ms)，匹配 focus.py 中 `_v * 100` 的 100ms 弹道前瞻算法
                # 正常移动速度约为 -0.2 ~ -0.6 px/ms，限幅在 [-2.0, 2.0]
                norm_vx = float(np.clip(t.vx / 100.0, -2.0, 2.0))
                results.append((int(t.id), int(t.class_id), float(t.conf),
                                int(round(t.cx)), int(round(t.cy)),
                                int(round(t.w)), int(round(t.h)), norm_vx))
        return results
