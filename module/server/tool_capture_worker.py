from __future__ import annotations

import cv2
import multiprocessing
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from module.config.config import Config
from module.device.device import Device


class CaptureCommand(Enum):
    START = "start"
    STOP = "stop"
    STATUS = "status"


@dataclass
class CaptureRequest:
    command: CaptureCommand
    config_name: str = ""
    frame_rate: int = 2


@dataclass
class CaptureResponse:
    state: str = "stopped"
    error: str = ""
    frame_data: Optional[bytes] = None
    retry_count: int = 0
    updated_at: float = 0.0


def capture_worker(request_queue: multiprocessing.Queue, response_queue: multiprocessing.Queue) -> None:
    device: Optional[Device] = None
    config_name = ""
    frame_rate = 2
    interval = 0.5
    state = "stopped"
    error = ""
    retry_count = 0
    max_retries = 3
    stop_event = multiprocessing.Event()

    def send_response(frame_data: Optional[bytes] = None):
        response = CaptureResponse(
            state=state,
            error=error,
            frame_data=frame_data,
            retry_count=retry_count,
            updated_at=time.time(),
        )
        try:
            response_queue.put_nowait(response)
        except Exception:
            pass

    def release_device():
        nonlocal device
        if device is None:
            return
        try:
            device.release_during_wait()
        except Exception:
            pass
        device = None

    def build_device(config: Config, interval_val: float) -> Device:
        dev = Device(config=config)
        dev.disable_stuck_detection()
        dev.screenshot_interval_set(interval_val)
        return dev

    while not stop_event.is_set():
        try:
            request = request_queue.get(timeout=0.5)
        except Exception:
            if state == "running" and device:
                try:
                    frame = device.screenshot()
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    ok, buf = cv2.imencode(".jpg", frame_bgr)
                    if ok:
                        send_response(buf.tobytes())
                        error = ""
                        retry_count = 0
                except Exception as e:
                    release_device()
                    device = None
                    retry_count += 1
                    error = str(e)
                    if retry_count > max_retries:
                        state = "error"
                        send_response()
                    else:
                        state = "starting"
                        send_response()
            continue

        if request.command == CaptureCommand.STOP:
            stop_event.set()
            release_device()
            state = "stopped"
            error = ""
            retry_count = 0
            send_response()
            break

        elif request.command == CaptureCommand.START:
            release_device()
            config_name = request.config_name
            frame_rate = max(1, min(request.frame_rate, 10))
            interval = max(0.1, 1.0 / float(frame_rate))
            state = "starting"
            error = ""
            retry_count = 0
            send_response()

            try:
                config = Config(config_name=config_name)
                device = build_device(config, interval)
                state = "running"
                error = ""
                retry_count = 0
                send_response()
            except Exception as e:
                error = str(e)
                retry_count += 1
                if retry_count > max_retries:
                    state = "error"
                else:
                    state = "starting"
                send_response()

        elif request.command == CaptureCommand.STATUS:
            send_response()

    release_device()