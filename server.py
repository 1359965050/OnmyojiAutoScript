# This Python file uses the following encoding: utf-8
# Copy from https://github.com/LmeSzinc/AzurLaneAutoScript/gui.py


"""
在任何平台把当前 Python 进程（含子线程、子进程）切到北京时间。
• Linux/macOS/WSL 及 Win-Py 3.11+ → TZ='Asia/Shanghai' + time.tzset()
• Win-Py ≤ 3.10            → TZ='CST-8'       + _tzset()（POSIX 语法）
"""
import os, sys, time

if hasattr(time, "tzset"):
    # Unix 全系  /  Windows 3.11+ 走这条
    os.environ["TZ"] = "Asia/Shanghai"     # IANA 名称，glibc/Apple libc 都认识
    time.tzset()
else:
    # 只有旧 Windows 才会落到这里
    import ctypes
    os.environ["TZ"] = "CST-8"             # POSIX 字符串：UTC+8 且无 DST
    for dll in ("ucrtbase", "msvcrt"):     # 新旧 CRT 都试一遍
        try:
            ctypes.CDLL(dll)._tzset()
            break
        except (OSError, AttributeError):
            continue
        
import threading

from module.logger import logger, set_file_logger
from module.image.rpc import ensure_image_server_ready, shutdown_image_server
from module.server.setting import State
from module.ocr.rpc import ensure_ocr_server_ready, shutdown_ocr_server

# 让 server 主进程日志写入 oas1.txt，避免单独生成 server.txt
set_file_logger('oas1')


def fun(ev: threading.Event):
    import argparse
    import asyncio
    import sys

    import uvicorn

    # 不知道干啥的照着抄就行了
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    State.restart_event = ev

    parser = argparse.ArgumentParser(description="Alas web service")
    parser.add_argument(
        "--host",
        type=str,
        help="Host to listen. Default to WebuiHost in deploy setting",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        help="Port to listen. Default to WebuiPort in deploy setting",
    )
    parser.add_argument(
        "-k", "--key", type=str, help="Password of alas. No password by default"
    )
    parser.add_argument(
        "--cdn",
        action="store_true",
        help="Use jsdelivr cdn for pywebio static files (css, js). Self host cdn by default.",
    )
    parser.add_argument(
        "--run",
        nargs="+",
        type=str,
        help="Run alas by config names on startup",
    )
    args, _ = parser.parse_known_args()

    host = args.host or State.deploy_config.WebuiHost or "0.0.0.0"
    port = args.port or int(State.deploy_config.WebuiPort) or 7788

    logger.hr("Launcher config")
    logger.attr("Host", host)
    logger.attr("Port", port)
    logger.attr("Reload", ev is not None)

    # 并发预热核心后台服务（图像服务 + OCR 服务与权重预热）
    from concurrent.futures import ThreadPoolExecutor, wait
    t_start = time.perf_counter()
    logger.hr("Pre-warming background services", 1)

    def _warmup_image():
        t0 = time.perf_counter()
        ensure_image_server_ready()
        logger.info(f"Image Server pre-warmed in {time.perf_counter() - t0:.3f}s")

    def _warmup_ocr():
        t0 = time.perf_counter()
        ensure_ocr_server_ready(warmup=True)
        logger.info(f"OCR Server & Model pre-warmed in {time.perf_counter() - t0:.3f}s")

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="prewarm") as executor:
        f_img = executor.submit(_warmup_image)
        f_ocr = executor.submit(_warmup_ocr)
        wait([f_img, f_ocr])

    logger.info(f"All core background services fully pre-warmed in {time.perf_counter() - t_start:.3f}s")

    try:
        uvicorn.run("module.server.app:fastapi_app",
                    host=host,
                    port=port,
                    factory=True,
                    log_config=None)
    finally:
        shutdown_image_server()
        shutdown_ocr_server()


if __name__ == "__main__":
    fun(None)
