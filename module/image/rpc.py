import atexit
import multiprocessing
import pickle
import socket
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import zerorpc

from module.exception import ScriptError
from module.logger import logger

_IMAGE_SERVER_PROCESS: Optional[multiprocessing.Process] = None


def _normalize_address(address: str) -> str:
    if address.startswith("tcp://"):
        return address
    return f"tcp://{address}"


def _split_host_port(address: str) -> tuple[str, int]:
    addr = address.replace("tcp://", "")
    if ":" not in addr:
        return addr, 22278
    host, port = addr.rsplit(":", 1)
    return host, int(port)


def _is_port_in_use(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.5)
        s.connect((host, port))
        s.shutdown(2)
        return True
    except Exception:
        return False
    finally:
        s.close()


def ensure_image_server_started() -> bool:
    from module.server.setting import State

    deploy_config = State.deploy_config
    if not deploy_config.StartImageServer:
        return False

    if deploy_config.ImageServerPort:
        port = int(deploy_config.ImageServerPort)
    else:
        _, port = _split_host_port(str(deploy_config.ImageClientAddress))
    host = "0.0.0.0"

    if _is_port_in_use("127.0.0.1", port):
        logger.info(f"Image server already running on port {port}")
        return True

    global _IMAGE_SERVER_PROCESS
    if _IMAGE_SERVER_PROCESS is not None and _IMAGE_SERVER_PROCESS.is_alive():
        logger.info("Image server process already started")
        return True

    _IMAGE_SERVER_PROCESS = multiprocessing.Process(
        target=run_image_server,
        args=(host, port),
        name="image_server",
        daemon=True,
    )
    _IMAGE_SERVER_PROCESS.start()
    logger.info(f"Start image server on {host}:{port}")
    for _ in range(50):
        if _is_port_in_use("127.0.0.1", port):
            return True
        time.sleep(0.1)
    logger.error(f"Image server is not ready on port {port}")
    return False


def shutdown_image_server(timeout: float = 2.0) -> bool:
    global _IMAGE_SERVER_PROCESS

    process = _IMAGE_SERVER_PROCESS
    if process is None:
        return False

    if not process.is_alive():
        _IMAGE_SERVER_PROCESS = None
        return False

    logger.info("Stopping image server process")
    try:
        process.terminate()
        process.join(timeout=timeout)
        if process.is_alive():
            logger.warning("Image server process did not exit in time, force killing")
            process.kill()
            process.join(timeout=1.0)
        logger.info("Image server process stopped")
        return True
    except Exception as e:
        logger.exception(e)
        return False
    finally:
        _IMAGE_SERVER_PROCESS = None


def run_image_server(host: str, port: int) -> None:
    server = zerorpc.Server(ImageServer())
    server.bind(f"tcp://{host}:{port}")
    server.run()


class ImageServer:
    def __init__(self) -> None:
        from module.image.runtime import ImageRuntime
        self.runtime = ImageRuntime()

    def ping(self) -> bool:
        return True

    def match(
        self,
        image_bytes: bytes,
        template_bytes: bytes,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
        threshold: float,
        method: str = "Template matching",
    ) -> Dict[str, Any]:
        image = pickle.loads(image_bytes)
        template = pickle.loads(template_bytes)
        result = self.runtime.match(image, template, roi_front, roi_back, threshold, method)
        return {
            "success": result["success"],
            "roi_front": result["roi_front"],
            "score": float(result["score"]) if result["score"] is not None else None,
        }

    def match_multi_scale(
        self,
        image_bytes: bytes,
        template_bytes: bytes,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
        threshold: float,
        scales: Optional[List[float]] = None,
        scale_range: Optional[Tuple[float, float, float]] = None,
        method: str = "Template matching",
    ) -> Dict[str, Any]:
        image = pickle.loads(image_bytes)
        template = pickle.loads(template_bytes)
        result = self.runtime.match_multi_scale(
            image, template, roi_front, roi_back, threshold, scales, scale_range, method
        )
        return {
            "success": result["success"],
            "roi_front": result["roi_front"],
            "score": float(result["score"]) if result["score"] is not None else None,
            "scale": float(result["scale"]) if result["scale"] is not None else None,
        }

    def match_all(
        self,
        image_bytes: bytes,
        template_bytes: bytes,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
        threshold: float,
        method: str = "Template matching",
    ) -> List[Dict[str, Any]]:
        image = pickle.loads(image_bytes)
        template = pickle.loads(template_bytes)
        matches = self.runtime.match_all(image, template, roi_front, roi_back, threshold, method)
        return [
            {
                "score": float(match[0]),
                "x": int(match[1]),
                "y": int(match[2]),
                "w": int(match[3]),
                "h": int(match[4]),
            }
            for match in matches
        ]

    def match_all_any(
        self,
        image_bytes: bytes,
        template_bytes: bytes,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
        threshold: float,
        nms_threshold: float = 0.3,
        method: str = "Template matching",
    ) -> List[Dict[str, Any]]:
        image = pickle.loads(image_bytes)
        template = pickle.loads(template_bytes)
        matches = self.runtime.match_all_any(
            image, template, roi_front, roi_back, threshold, nms_threshold, method
        )
        return [
            {
                "score": float(match[0]),
                "x": int(match[1]),
                "y": int(match[2]),
                "w": int(match[3]),
                "h": int(match[4]),
            }
            for match in matches
        ]

    def match_sift(
        self,
        image_bytes: bytes,
        template_bytes: bytes,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
    ) -> Dict[str, Any]:
        image = pickle.loads(image_bytes)
        template = pickle.loads(template_bytes)
        result = self.runtime.match_sift(image, template, roi_front, roi_back)
        return {
            "success": result["success"],
            "roi_front": result["roi_front"],
        }

    def match_mean_color(
        self,
        image_bytes: bytes,
        roi_back: Tuple[int, int, int, int],
        color: Tuple[int, int, int],
        bias: int = 10,
    ) -> bool:
        image = pickle.loads(image_bytes)
        return self.runtime.match_mean_color(image, roi_back, color, bias)

    def match_brightness(
        self,
        image_bytes: bytes,
        template_bytes: bytes,
        roi_back: Tuple[int, int, int, int],
        threshold: float = 0.9,
        gray: bool = False,
    ) -> bool:
        image = pickle.loads(image_bytes)
        template = pickle.loads(template_bytes)
        return self.runtime.match_brightness(image, template, roi_back, threshold, gray)

    def match_saturation(
        self,
        image_bytes: bytes,
        template_bytes: bytes,
        roi_back: Tuple[int, int, int, int],
        threshold: float = 0.9,
    ) -> bool:
        image = pickle.loads(image_bytes)
        template = pickle.loads(template_bytes)
        return self.runtime.match_saturation(image, template, roi_back, threshold)

    def get_cache_stats(self) -> Dict[str, Any]:
        return self.runtime.get_cache_stats()

    def clear_cache(self) -> None:
        self.runtime.clear_cache()


class ImageProxy:
    is_proxy = True

    def __init__(self, address: str) -> None:
        self.address = _normalize_address(address)
        self.client = zerorpc.Client()
        try:
            self.client.connect(self.address)
            self.client.ping()
        except Exception as e:
            raise ScriptError(f"Image server connection failed: {self.address}") from e

    def match(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
        threshold: float,
        method: str = "Template matching",
    ) -> Dict[str, Any]:
        image_bytes = pickle.dumps(image, protocol=4)
        template_bytes = pickle.dumps(template, protocol=4)
        return self.client.match(image_bytes, template_bytes, roi_front, roi_back, threshold, method)

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
        image_bytes = pickle.dumps(image, protocol=4)
        template_bytes = pickle.dumps(template, protocol=4)
        return self.client.match_multi_scale(
            image_bytes, template_bytes, roi_front, roi_back, threshold, scales, scale_range, method
        )

    def match_all(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
        threshold: float,
        method: str = "Template matching",
    ) -> List[Dict[str, Any]]:
        image_bytes = pickle.dumps(image, protocol=4)
        template_bytes = pickle.dumps(template, protocol=4)
        return self.client.match_all(image_bytes, template_bytes, roi_front, roi_back, threshold, method)

    def match_all_any(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
        threshold: float,
        nms_threshold: float = 0.3,
        method: str = "Template matching",
    ) -> List[Dict[str, Any]]:
        image_bytes = pickle.dumps(image, protocol=4)
        template_bytes = pickle.dumps(template, protocol=4)
        return self.client.match_all_any(
            image_bytes, template_bytes, roi_front, roi_back, threshold, nms_threshold, method
        )

    def match_sift(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_front: Tuple[int, int, int, int],
        roi_back: Tuple[int, int, int, int],
    ) -> Dict[str, Any]:
        image_bytes = pickle.dumps(image, protocol=4)
        template_bytes = pickle.dumps(template, protocol=4)
        return self.client.match_sift(image_bytes, template_bytes, roi_front, roi_back)

    def match_mean_color(
        self,
        image: np.ndarray,
        roi_back: Tuple[int, int, int, int],
        color: Tuple[int, int, int],
        bias: int = 10,
    ) -> bool:
        image_bytes = pickle.dumps(image, protocol=4)
        return self.client.match_mean_color(image_bytes, roi_back, color, bias)

    def match_brightness(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_back: Tuple[int, int, int, int],
        threshold: float = 0.9,
        gray: bool = False,
    ) -> bool:
        image_bytes = pickle.dumps(image, protocol=4)
        template_bytes = pickle.dumps(template, protocol=4)
        return self.client.match_brightness(image_bytes, template_bytes, roi_back, threshold, gray)

    def match_saturation(
        self,
        image: np.ndarray,
        template: np.ndarray,
        roi_back: Tuple[int, int, int, int],
        threshold: float = 0.9,
    ) -> bool:
        image_bytes = pickle.dumps(image, protocol=4)
        template_bytes = pickle.dumps(template, protocol=4)
        return self.client.match_saturation(image_bytes, template_bytes, roi_back, threshold)

    def get_cache_stats(self) -> Dict[str, Any]:
        return self.client.get_cache_stats()

    def clear_cache(self) -> None:
        self.client.clear_cache()


atexit.register(shutdown_image_server)