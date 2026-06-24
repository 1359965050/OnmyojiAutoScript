import hashlib
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from module.base.utils import is_approx_rectangle


class FrameCache:
    def __init__(self, max_size: int = 5) -> None:
        self.cache: OrderedDict[int, np.ndarray] = OrderedDict()
        self.max_size = max_size
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _compute_hash(self, image: np.ndarray) -> int:
        return hash(image.tobytes())

    def get(self, image: np.ndarray) -> Optional[np.ndarray]:
        img_hash = self._compute_hash(image)
        with self.lock:
            if img_hash in self.cache:
                self.cache.move_to_end(img_hash)
                self.hits += 1
                return self.cache[img_hash]
            self.misses += 1
            return None

    def put(self, image: np.ndarray) -> int:
        img_hash = self._compute_hash(image)
        with self.lock:
            if img_hash in self.cache:
                self.cache.move_to_end(img_hash)
            else:
                self.cache[img_hash] = image.copy()
                if len(self.cache) > self.max_size:
                    self.cache.popitem(last=False)
        return img_hash

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0.0,
            }


class TemplateCache:
    def __init__(self, max_size: int = 100) -> None:
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.max_size = max_size
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _compute_key(self, template: np.ndarray) -> str:
        return hashlib.md5(template.tobytes()).hexdigest()

    def get(self, template: np.ndarray) -> Optional[Dict[str, Any]]:
        key = self._compute_key(template)
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                self.hits += 1
                return self.cache[key]
            self.misses += 1
            return None

    def put(self, template: np.ndarray) -> str:
        key = self._compute_key(template)
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                sift = cv2.SIFT_create()
                kp, des = sift.detectAndCompute(template, None)
                self.cache[key] = {
                    "template": template.copy(),
                    "kp": kp,
                    "des": des,
                }
                if len(self.cache) > self.max_size:
                    self.cache.popitem(last=False)
        return key

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0.0,
            }


class ImageRuntime:
    def __init__(self, thread_pool_size: int = 4) -> None:
        self.frame_cache = FrameCache()
        self.template_cache = TemplateCache()
        self.executor = ThreadPoolExecutor(max_workers=thread_pool_size)
        self.sift = cv2.SIFT_create()
        self.match_count = 0
        self.match_time = 0.0

    def _crop(self, image: np.ndarray, roi: Tuple[int, int, int, int]) -> np.ndarray:
        x, y, w, h = int(roi[0]), int(roi[1]), int(roi[2]), int(roi[3])
        return image[y:y + h, x:x + w]

    def match(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
        threshold: float,
        method: str = "Template matching",
    ) -> Dict[str, Any]:
        self.match_count += 1

        if method != "Template matching":
            return self.match_sift(image, template, roi_front, roi_back)

        source = self._crop(image, roi_back)
        mat = template

        if mat is None or mat.shape[0] == 0 or mat.shape[1] == 0:
            return {"success": False, "roi_front": list(roi_front), "score": None}

        res = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val > threshold:
            new_roi_front = [
                max_loc[0] + roi_back[0],
                max_loc[1] + roi_back[1],
                roi_front[2],
                roi_front[3],
            ]
            return {"success": True, "roi_front": new_roi_front, "score": float(max_val)}
        else:
            return {"success": False, "roi_front": list(roi_front), "score": float(max_val)}

    def match_multi_scale(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
        threshold: float,
        scales: Optional[List[float]] = None,
        scale_range: Optional[Tuple[float, float, float]] = None,
        method: str = "Template matching",
    ) -> Dict[str, Any]:
        self.match_count += 1

        if scales is None:
            scales = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]

        if scale_range is not None:
            start, end = scale_range[:2]
            step = scale_range[2] if len(scale_range) > 2 else 0.1
            scales = sorted(set(round(x, 1) for x in np.arange(start, end + step, step)))

        source = self._crop(image, roi_back)
        mat = template

        if mat is None or mat.shape[0] == 0 or mat.shape[1] == 0:
            return {"success": False, "roi_front": list(roi_front), "score": None, "scale": None}

        mat_h, mat_w = mat.shape[:2]
        source_h, source_w = source.shape[:2]

        best_score = 0.0
        best_loc = None
        best_scale = 1.0

        for scale in scales:
            scaled_w = int(mat_w * scale)
            scaled_h = int(mat_h * scale)

            if scaled_w < 10 or scaled_h < 10:
                continue

            try:
                scaled_mat = cv2.resize(mat, (scaled_w, scaled_h))
                res = cv2.matchTemplate(source, scaled_mat, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                if max_val > best_score:
                    best_score = max_val
                    best_loc = max_loc
                    best_scale = scale
            except Exception:
                continue

        if best_score > threshold and best_loc is not None:
            new_roi_front = [
                best_loc[0] + roi_back[0],
                best_loc[1] + roi_back[1],
                int(mat_w * best_scale),
                int(mat_h * best_scale),
            ]
            return {
                "success": True,
                "roi_front": new_roi_front,
                "score": float(best_score),
                "scale": float(best_scale),
            }
        else:
            return {
                "success": False,
                "roi_front": list(roi_front),
                "score": float(best_score),
                "scale": float(best_scale),
            }

    def match_all(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
        threshold: float,
        method: str = "Template matching",
    ) -> List[Tuple[float, int, int, int, int]]:
        self.match_count += 1

        if method != "Template matching":
            return []

        source = self._crop(image, roi_back)
        mat = template

        if mat is None or mat.shape[0] == 0 or mat.shape[1] == 0:
            return []

        results = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED)
        locations = np.where(results >= threshold)
        matches = []
        for pt in zip(*locations[::-1]):
            score = float(results[pt[1], pt[0]])
            x = int(roi_back[0] + pt[0])
            y = int(roi_back[1] + pt[1])
            w = int(mat.shape[1])
            h = int(mat.shape[0])
            matches.append((score, x, y, w, h))

        return matches

    def match_all_any(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
        threshold: float,
        nms_threshold: float = 0.3,
        method: str = "Template matching",
    ) -> List[Tuple[float, int, int, int, int]]:
        self.match_count += 1

        if method != "Template matching":
            return []

        matches = self.match_all(image, template, roi_front, roi_back, threshold, method)

        if len(matches) > 0:
            scores = np.array([m[0] for m in matches])
            boxes = np.array([[m[1], m[2], m[3], m[4]] for m in matches])

            try:
                indices = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), score_threshold=threshold, nms_threshold=nms_threshold)
                if isinstance(indices, (list, tuple)):
                    indices = [i[0] for i in indices]
                else:
                    indices = indices.flatten().tolist()
                filtered_matches = [matches[i] for i in indices]
                return filtered_matches
            except Exception:
                pass

        return matches

    def match_sift(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
    ) -> Dict[str, Any]:
        self.match_count += 1

        source = self._crop(image, roi_back)
        kp, des = self.sift.detectAndCompute(source, None)

        cached = self.template_cache.get(template)
        if cached:
            template_kp, template_des = cached["kp"], cached["des"]
        else:
            template_kp, template_des = self.sift.detectAndCompute(template, None)
            self.template_cache.put(template)

        if des is None or template_des is None:
            return {"success": False, "roi_front": list(roi_front)}

        index_params = dict(algorithm=1, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)

        try:
            matches = flann.knnMatch(template_des, des, k=2)
        except Exception:
            return {"success": False, "roi_front": list(roi_front)}

        good = []
        for m, n in matches:
            if m.distance < 0.6 * n.distance:
                good.append(m)

        if len(good) >= 10:
            src_pts = np.float32([template_kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

            m, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            w, h = roi_front[2], roi_front[3]
            pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)

            if m is None:
                return {"success": False, "roi_front": list(roi_front)}

            dst = np.int32(cv2.perspectiveTransform(pts, m))
            new_roi_front = [
                int(dst[0, 0, 0] + roi_back[0]),
                int(dst[0, 0, 1] + roi_back[1]),
                roi_front[2],
                roi_front[3],
            ]

            if not is_approx_rectangle(np.array([pos[0] for pos in dst])):
                return {"success": False, "roi_front": list(roi_front)}

            return {"success": True, "roi_front": new_roi_front}
        else:
            return {"success": False, "roi_front": list(roi_front)}

    def match_mean_color(
        self,
        image: np.ndarray,
        roi_back: Tuple[int, int, int, int],
        color: Tuple[int, int, int],
        bias: int = 10,
    ) -> bool:
        source = self._crop(image, roi_back)
        average_color = cv2.mean(source)
        for i in range(3):
            if abs(average_color[i] - color[i]) > bias:
                return False
        return True

    def match_brightness(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_back: Tuple[int, int, int, int],
        threshold: float = 0.9,
        gray: bool = False,
    ) -> bool:
        source = self._crop(image, roi_back)

        if len(source.shape) != 3:
            return False
        source_gray = cv2.cvtColor(source, cv2.COLOR_RGB2GRAY)
        source_hsv = cv2.cvtColor(source, cv2.COLOR_RGB2HSV)

        if len(template.shape) != 3:
            return False
        template_gray = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)
        template_hsv = cv2.cvtColor(template, cv2.COLOR_RGB2HSV)

        source_value = float(source_gray.mean()) if gray else float(source_hsv[:, :, 2].mean())
        template_value = float(template_gray.mean()) if gray else float(template_hsv[:, :, 2].mean())
        score = 1.0 - abs(source_value - template_value) / 255.0
        score = max(0.0, min(1.0, score))

        return score >= threshold

    def match_saturation(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_back: Tuple[int, int, int, int],
        threshold: float = 0.9,
    ) -> bool:
        source = self._crop(image, roi_back)

        if len(source.shape) != 3:
            return False
        source_hsv = cv2.cvtColor(source, cv2.COLOR_RGB2HSV)

        if len(template.shape) != 3:
            return False
        template_hsv = cv2.cvtColor(template, cv2.COLOR_RGB2HSV)

        source_value = float(source_hsv[:, :, 1].mean())
        template_value = float(template_hsv[:, :, 1].mean())
        score = 1.0 - abs(source_value - template_value) / 255.0
        score = max(0.0, min(1.0, score))

        return score >= threshold

    def get_cache_stats(self) -> Dict[str, Any]:
        return {
            "frame_cache": self.frame_cache.get_stats(),
            "template_cache": self.template_cache.get_stats(),
            "match_count": self.match_count,
            "thread_pool_size": self.executor._max_workers,
        }

    def clear_cache(self) -> None:
        self.frame_cache.clear()
        self.template_cache.clear()

    def shutdown(self) -> None:
        self.executor.shutdown(wait=True)
        self.clear_cache()