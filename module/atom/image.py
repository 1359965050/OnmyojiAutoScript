# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import cv2  # type: ignore
import numpy as np

from numpy import uint8, fromfile
from pathlib import Path

from module.base.decorator import cached_property
from module.image.rpc import get_image_client
from module.logger import logger
from module.base.utils import is_approx_rectangle
from module.base.utils.utils import random_normal_distribution_int


class RuleImage:
    debug_mode: bool = False
    METHOD_TEMPLATE_MATCH = "Template matching"
    METHOD_MASKED_TEMPLATE_MATCH = "Masked template matching"
    METHOD_MULTI_SCALE_TEMPLATE_MATCH = "Multi-scale template matching"
    METHOD_SIFT_FLANN = "Sift Flann"
    DEFAULT_MULTI_SCALE_RANGE = (0.6, 1.2)
    DEFAULT_MULTI_SCALE_STEP = 0.1

    def __init__(self, roi_front: tuple, roi_back: tuple, method: str, threshold: float, file: str) -> None:
        """
        初始化
        :param roi_front: 前置roi
        :param roi_back: 后置roi 用于匹配的区域
        :param method: 匹配方法 "Template matching" / "Masked template matching" / "Multi-scale template matching" / "Sift Flann"
        :param threshold: 阈值  0.8
        :param file: 相对路径, 带后缀
        """
        self._match_init = False  # 这个是给后面的 等待图片稳定
        self._image = None  # 这个是匹配的目标
        self._kp = None  #
        self._des = None
        self._mask_loaded = False  # 掩码懒加载标记: False=未加载, 加载后看 _mask
        self._mask = None  # 掩码图, None 表示无掩码(回退普通匹配)
        self.last_score = -1.0  # 最近一次匹配的真实分数, -1 表示本次未产生分数
        self.last_scale = None  # 最近一次多尺度匹配命中的缩放倍数, 仅 Multi-scale 方法写入
        self.method = method

        self.roi_front: list = list(roi_front)
        self.roi_back = roi_back
        self.threshold = threshold
        self.file = file
        self.scale_range: tuple[float, float] | tuple[float, float, float] | None = None
        self.scale_step: float = self.DEFAULT_MULTI_SCALE_STEP

    @cached_property
    def name(self) -> str:
        """

        :return:
        """
        return Path(self.file).stem.upper()

    def __str__(self):
        return self.name

    __repr__ = __str__

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(self.name)

    def __bool__(self):
        return True

    def load_image(self) -> None:
        """
        加载图片
        :return:
        """
        if self._image is not None:
            return
        img = cv2.imdecode(fromfile(self.file, dtype=uint8), -1)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self._image = img

        height, width, channels = self._image.shape
        if height != self.roi_front[3] or width != self.roi_front[2]:
            self.roi_front[2] = width
            self.roi_front[3] = height
            logger.debug(f"{self.name} roi_front size changed to {width}x{height}")

    def load_kp_des(self) -> None:
        if self._kp is not None and self._des is not None:
            return
        self._kp, self._des = self.sift.detectAndCompute(self.image, None)

    @property
    def image(self):
        """
        获取图片
        :return:
        """
        if self._image is None:
            self.load_image()
        return self._image

    @property
    def is_template_match(self) -> bool:
        """
        是否是模板匹配
        :return:
        """
        return self.method == self.METHOD_TEMPLATE_MATCH

    @property
    def is_masked_template_match(self) -> bool:
        """
        是否是掩码模板匹配，掩码取自同目录下 `xxx_mask.png`
        :return:
        """
        return self.method == self.METHOD_MASKED_TEMPLATE_MATCH

    @property
    def is_multi_scale_template_match(self) -> bool:
        return self.method == self.METHOD_MULTI_SCALE_TEMPLATE_MATCH

    @property
    def is_sift_flann(self) -> bool:
        return self.method == self.METHOD_SIFT_FLANN

    @property
    def mask(self):
        """
        掩码图，取模板同目录下 `xxx_mask.png`（`xxx.png` -> `xxx_mask.png`）。
        语义为「非零参与匹配，零忽略」。文件缺失、读取失败或尺寸与模板不一致时
        返回 None，由调用方回退到普通匹配，避免一张画错尺寸的掩码直接让规则报错。
        :return:
        """
        if not self._mask_loaded:
            self._mask_loaded = True
            path = Path(self.file)
            mask_path = path.with_name(f"{path.stem}_mask{path.suffix}")
            try:
                mask = cv2.imdecode(fromfile(str(mask_path), dtype=uint8), cv2.IMREAD_GRAYSCALE)
            except Exception:
                mask = None
            if mask is None:
                logger.debug(f"{self.name} template mask unavailable, fallback to plain matching: {mask_path}")
            elif mask.shape[:2] != self.image.shape[:2]:
                logger.error(
                    f"{self.name} template mask size mismatch "
                    f"{mask.shape[:2]} != {self.image.shape[:2]}, fallback to plain matching"
                )
            else:
                self._mask = mask
        return self._mask

    @staticmethod
    def _template_is_degenerate(template: np.ndarray, mask: np.ndarray | None = None) -> bool:
        """
        判断模板在参与匹配的区域内是否逐通道恒为常量。

        CCOEFF_NORMED 归一化时分母来自各通道的方差，参与区域内所有通道都完全没有起伏时，
        分母才是 0，OpenCV 会走特判：无掩码时整张结果矩阵被填成 1.0（恒假阳性，且落点固定
        在 roi_back 左上角），带掩码时整张变成 0/0 的 nan。两种都让这条规则失去意义，
        这里提前拦掉，而不是把异常数值当成命中。
        """
        if template is None or template.size == 0:
            return True
        region = template if mask is None else template[mask > 0]
        if region.size == 0:
            return True
        channels = 1 if template.ndim == 2 else template.shape[-1]
        samples = region.reshape(-1, channels)
        return all(float(samples[:, channel].std()) == 0.0 for channel in range(channels))

    @staticmethod
    def _sanitize_match_result(result: np.ndarray) -> np.ndarray:
        """
        压掉匹配结果矩阵里的非有限值。

        源图窗口整块同色时 CCOEFF_NORMED 会算出 nan/inf：nan 会让
        `max_val > threshold` 恒为假而静默漏检，inf 则会越过阈值并把命中位置指到随机
        坐标（假阳性，点错位置）。这里统一替换为 -1.0，等价于「该位置判不匹配」。
        """
        if np.isfinite(result).all():
            return result
        logger.error("match result contains nan/inf (solid-color region), treated as not matched")
        return np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)

    @cached_property
    def sift(self):
        return cv2.SIFT_create()

    @cached_property
    def kp(self):
        if self._kp is None:
            self.load_kp_des()
        return self._kp

    @cached_property
    def des(self):
        if self._des is None:
            self.load_kp_des()
        return self._des

    def corp(self, image: np.ndarray, roi: list | tuple | None = None) -> np.ndarray:
        """
        截取图片
        :param image:
        :param roi
        :return:
        """
        if roi is None:
            x, y, w, h = self.roi_back
        else:
            x, y, w, h = roi
        x, y, w, h = int(x), int(y), int(w), int(h)
        return image[y:y + h, x:x + w]

    def _template_image_invalid(self, mat: np.ndarray | None) -> bool:
        if mat is None or mat.shape[0] == 0 or mat.shape[1] == 0:
            mat_shape = None if mat is None else mat.shape
            logger.error(f"Template image is invalid: {mat_shape}")  # 检测模板尺寸，避免非法模板参与匹配
            return True
        return False

    def _update_roi_front(self, loc: tuple[int, int], size: tuple[int, int]) -> None:
        self.roi_front[0] = loc[0] + self.roi_back[0]
        self.roi_front[1] = loc[1] + self.roi_back[1]
        self.roi_front[2] = size[0]
        self.roi_front[3] = size[1]

    def to_service_payload(self) -> dict:
        file_path = ""
        if self.file:
            file_path = str(Path(self.file).resolve())
        scale_range = None
        if self.scale_range is not None:
            scale_range = list(self.scale_range)
        return {
            "name": self.name,
            "file": file_path,
            "method": self.method,
            "threshold": self.threshold,
            "roi_front": list(self.roi_front),
            "roi_back": list(self.roi_back),
            "scale_range": scale_range,
            "scale_step": self.scale_step,
        }

    def _apply_match_result(self, result: dict) -> bool:
        if "score" in result:
            self.last_score = float(result["score"])
        if "scale" in result and result["scale"] is not None:
            self.last_scale = float(result["scale"])
        if result.get("matched"):
            roi_front = result.get("roi_front")
            if roi_front is not None:
                self.roi_front = [int(v) for v in roi_front]
            return True
        return False

    def template_match(self, image: np.ndarray, threshold: float | None = None) -> bool:
        if threshold is None:
            threshold = self.threshold
        source = self.corp(image)
        mat = self.image

        if mat is None or self._template_image_invalid(mat):
            return True  # 如果模板图像无效，直接返回 True

        if source.shape[0] < mat.shape[0] or source.shape[1] < mat.shape[1]:
            self.last_score = -1.0
            return False

        mask = self.mask if self.is_masked_template_match else None
        if self._template_is_degenerate(mat, mask):
            logger.error(f"{self.name} template is flat (no variance in matching area), treated as not matched")
            self.last_score = -1.0
            return False

        if mask is None:
            res = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED)
        else:
            res = cv2.matchTemplate(source, mat, cv2.TM_CCOEFF_NORMED, mask=mask)
        res = self._sanitize_match_result(res)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        self.last_score = float(max_val)
        if self.debug_mode:
            logger.attr(self.name, f'matching score {max_val:.5f}')

        if max_val > threshold:
            self._update_roi_front(max_loc, (mat.shape[1], mat.shape[0]))
            return True
        return False

    def _get_multi_scale_range(self) -> tuple[float, float, float]:
        active_scale_range = self.scale_range
        if active_scale_range is None:
            min_scale, max_scale = self.DEFAULT_MULTI_SCALE_RANGE
            step = self.DEFAULT_MULTI_SCALE_STEP
        elif len(active_scale_range) == 3:
            min_scale, max_scale, step = active_scale_range
        else:
            min_scale, max_scale = active_scale_range
            step = self.scale_step
        if min_scale > max_scale:
            min_scale, max_scale = max_scale, min_scale
        if step <= 0:
            step = self.DEFAULT_MULTI_SCALE_STEP
        return min_scale, max_scale, step

    def match_multi_scale(self, image: np.ndarray, threshold: float | None = None, scale_range=None) -> bool:
        old_scale_range = self.scale_range
        if scale_range is not None:
            self.scale_range = scale_range
        res = self.multi_scale_template_match(image, threshold=threshold)
        self.scale_range = old_scale_range
        return res

    def multi_scale_template_match(self, image: np.ndarray, threshold: float | None = None) -> bool:
        if threshold is None:
            threshold = self.threshold
        source = self.corp(image)
        mat = self.image

        if mat is None or self._template_image_invalid(mat):
            return True  # 如果模板图像无效，直接返回 True

        if self._template_is_degenerate(mat):
            logger.error(f"{self.name} template is flat (no variance), treated as not matched")
            self.last_score = -1.0
            self.last_scale = None
            return False

        min_scale, max_scale, step = self._get_multi_scale_range()
        best_val = -1.0
        best_loc = None
        best_shape = None
        best_scale = 1.0
        self.last_scale = None
        cur_scale = min_scale
        while cur_scale <= max_scale + 1e-8:
            scaled_w = max(1, int(mat.shape[1] * cur_scale))
            scaled_h = max(1, int(mat.shape[0] * cur_scale))
            if scaled_w > source.shape[1] or scaled_h > source.shape[0]:
                cur_scale += step
                continue
            scaled_mat = cv2.resize(mat, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)
            res = cv2.matchTemplate(source, scaled_mat, cv2.TM_CCOEFF_NORMED)
            res = self._sanitize_match_result(res)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_shape = (scaled_w, scaled_h)
                best_scale = cur_scale
            cur_scale += step
        if self.debug_mode:
            logger.attr(self.name, f'multi-scale matching score {best_val:.5f}')
        self.last_score = float(best_val)
        if best_loc is not None:
            self.last_scale = float(best_scale)
        if best_loc is not None and best_shape is not None and best_val > threshold:
            self._update_roi_front(best_loc, best_shape)
            return True
        return False

    def match(self, image: np.ndarray, threshold: float | None = None, frame_id: str | None = None) -> bool:
        """
        :param threshold:
        :param image:
        :return:
        """
        client = get_image_client()
        result = client.match_rule(
            rule_data=self.to_service_payload(),
            image=image,
            frame_id=frame_id,
            threshold=threshold,
        )
        return self._apply_match_result(result)

    def match_all(self, image: np.ndarray, threshold: float | None = None, roi: list | tuple | None = None, frame_id: str | None = None) -> list[tuple]:
        """
        区别于match，这个是返回所有的匹配结果
        :param roi:
        :param image:
        :param threshold:
        :return:
        """
        if roi is not None:
            self.roi_back = tuple(roi)
        client = get_image_client()
        roi_list = list(self.roi_back) if self.roi_back is not None else None
        result = client.match_all(
            rule_data=self.to_service_payload(),
            image=image,
            frame_id=frame_id,
            threshold=threshold,
            roi=roi_list,
        )
        return [tuple(item) for item in result.get("matches", [])]

    def match_all_any(self, image: np.ndarray, threshold: float | None = None, roi: list | tuple | None = None, nms_threshold: float = 0.3, frame_id: str | None = None) -> list[tuple]:
        """
        区别于match，这个是返回所有的匹配结果，去除冗余匹配项（例如：多个框选区域重叠的情况）时使用。
        :param roi:
        :param image:
        :param threshold:
        :return:
        """
        if roi is not None:
            self.roi_back = tuple(roi)
        client = get_image_client()
        roi_list = list(self.roi_back) if self.roi_back is not None else None
        result = client.match_all_any(
            rule_data=self.to_service_payload(),
            image=image,
            frame_id=frame_id,
            threshold=threshold,
            roi=roi_list,
            nms_threshold=nms_threshold,
        )
        return [tuple(item) for item in result.get("matches", [])]

    def coord(self) -> tuple:
        """
        获取roi_front的随机的点击的坐标
        :return:
        """
        x, y, w, h = self.roi_front
        return x + random_normal_distribution_int(0, w), y + random_normal_distribution_int(0, h)

    def coord_more(self) -> tuple:
        """
         获取roi_back的随机的点击的坐标
        :return:
        """
        x, y, w, h = self.roi_back
        return x + random_normal_distribution_int(0, w), y + random_normal_distribution_int(0, h)

    def front_center(self) -> tuple:
        """
        获取roi_front的中心坐标
        :return:
        """
        x, y, w, h = self.roi_front
        return int(x + w//2), int(y + h//2)

    def test_match(self, image: np.ndarray):
        self.debug_mode = True
        if self.is_template_match or self.is_masked_template_match:
            return self.template_match(image)
        if self.is_multi_scale_template_match:
            return self.multi_scale_template_match(image)
        if self.is_sift_flann:
            return self.sift_match(image, show=True)

    def sift_match(self, image: np.ndarray, show=False) -> bool:
        """
        特征匹配，同样会修改 roi_front
        :param image: 是游戏的截图，就是转通道后的截图
        :param show: 测试用的
        :return:
        """
        source = self.corp(image)
        kp, des = self.sift.detectAndCompute(source, None)
        # 参数1：index_params
        #    对于SIFT和SURF，可以传入参数index_params=dict(algorithm=FLANN_INDEX_KDTREE, trees=5)。
        #    对于ORB，可以传入参数index_params=dict(algorithm=FLANN_INDEX_LSH, table_number=6, key_size=12）。
        index_params = dict(algorithm=1, trees=5)
        # 参数2：search_params 指定递归遍历的次数，值越高结果越准确，但是消耗的时间也越多。
        search_params = dict(checks=50)
        # 根据设置的参数创建特征匹配器 指定匹配的算法和kd树的层数,指定返回的个数
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        # 利用创建好的特征匹配器利用k近邻算法来用模板的特征描述符去匹配图像的特征描述符，k指的是返回前k个最匹配的特征区域
        # 返回的是最匹配的两个特征点的信息，返回的类型是一个列表，列表元素的类型是Dmatch数据类型，具体是什么我也不知道
        # 第一个参数是小图的des, 第二个参数是大图的des
        kp_self, des_self = self.kp, self.des
        if kp_self is None or des_self is None:
            return False
        matches = flann.knnMatch(des_self, des, k=2)

        good = []
        result = True
        for i, (m, n) in enumerate(matches):
            # 设定阈值, 距离小于对方的距离的0.7倍我们认为是好的匹配点.
            if m.distance < 0.6 * n.distance:
                good.append(m)
        if len(good) >= 10:
            src_pts = np.array([kp_self[m.queryIdx].pt for m in good], dtype=np.float32).reshape(-1, 1, 2)
            dst_pts = np.array([kp[m.trainIdx].pt for m in good], dtype=np.float32).reshape(-1, 1, 2)

            # 计算透视变换矩阵m， 要求点的数量>=4
            m, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            # 创建一个包含模板图像四个角坐标的数组
            w, h = self.roi_front[2], self.roi_front[3]
            pts = np.array([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]], dtype=np.float32).reshape(-1, 1, 2)
            if m is None:
                result = False
            else:
                dst = np.array(cv2.perspectiveTransform(pts, m), dtype=np.int32)
                self.roi_front[0] = int(dst[0, 0, 0]) + self.roi_back[0]
                self.roi_front[1] = int(dst[0, 0, 1]) + self.roi_back[1]
                if show:
                    cv2.polylines(source, [dst], isClosed=True, color=(0, 0, 255), thickness=2)
                if not is_approx_rectangle(np.array([pos[0] for pos in dst])):
                    result = False
        else:
            result = False

        # https://blog.csdn.net/cungudafa/article/details/105399278
        # https://blog.csdn.net/qq_45832961/article/details/122776322
        if show:
            # 准备一个空的掩膜来绘制好的匹配
            mask_matches = [[0, 0] for i in range(len(matches))]
            # 向掩膜中添加数据
            for i, (m, n) in enumerate(matches):
                if m.distance < 0.6 * n.distance:  # 理论上0.7最好
                    mask_matches[i] = [1, 0]
            img_matches = cv2.drawMatchesKnn(self.image, self.kp, source, kp, matches, None,
                                             matchColor=(0, 255, 0), singlePointColor=(255, 0, 0),
                                             matchesMask=mask_matches, flags=0)
            cv2.imshow(f'Sift Flann: {self.name}', img_matches)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        return result

    def match_mean_color(self, image, color: tuple, bias=10) -> bool:
        """

        :param image:
        :param color:  rgb
        :param bias:
        :return:
        """
        image = self.corp(image)
        average_color = cv2.mean(image)
        # logger.info(f'{self.name} average_color: {average_color}')
        for i in range(3):
            if abs(average_color[i] - color[i]) > bias:
                return False
        return True


if __name__ == "__main__":
    from dev_tools.assets_test import detect_image

    IMAGE_FILE = './log/test/QQ截图20240223151924.png'
    from tasks.Restart.assets import RestartAssets
    jade = RestartAssets.I_HARVEST_JADE
    jade.method = 'Sift Flann'
    sign = RestartAssets.I_HARVEST_SIGN
    sign.method = 'Sift Flann'
    print(jade.roi_front)

    detect_image(IMAGE_FILE, jade)
    detect_image(IMAGE_FILE, sign)
    print(jade.roi_front)
