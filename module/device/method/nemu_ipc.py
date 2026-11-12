import asyncio
import contextlib
import ctypes
import io
import os
import random
import re
import sys
import threading
from functools import partial, wraps
from pathlib import Path

import cv2
import numpy as np

from module.base.decorator import cached_property, del_cached_property, has_cached_property
from module.base.utils import ensure_time
from module.device.method.minitouch import insert_swipe, random_rectangle_point
from module.device.method.utils import RETRY_TRIES, retry_sleep
from module.exception import RequestHumanTakeover
from module.logger import logger


class NemuIpcIncompatible(Exception):
    pass


class NemuIpcError(Exception):
    pass


_capture_std_lock = threading.RLock()


class CaptureStd:
    """线程安全的标准输出/错误捕获器。

    - 通过全局可重入锁串行化对进程级 FD1/FD2 的重定向，避免多线程并发写管道或关闭已替换流对象；
    - 当宿主环境无底层文件描述符（如 StringIO 或无控制台窗口的 GUI 进程）时自动降级为 Python 级重定向。
    """

    def __init__(self):
        self.stdout = b''
        self.stderr = b''
        self._lock_acquired = False
        self._fd_mode = False
        self._py_mode = False
        self._old_py_stdout = None
        self._old_py_stderr = None
        self._buf_out: io.StringIO | None = None
        self._buf_err: io.StringIO | None = None
        self.fdout: int | None = None
        self.fderr: int | None = None
        self.old_stdout: int | None = None
        self.old_stderr: int | None = None
        self.reader_out: int | None = None
        self.writer_out: int | None = None
        self.reader_err: int | None = None
        self.writer_err: int | None = None

    @staticmethod
    def _try_fileno(stream) -> int | None:
        if stream is None:
            return None
        try:
            return stream.fileno()
        except (AttributeError, ValueError, OSError, io.UnsupportedOperation):
            return None

    def _redirect_stdout(self, to: int):
        sys.stdout.flush()
        sys.stdout.close()
        os.dup2(to, self.fdout)
        sys.stdout = os.fdopen(self.fdout, 'w')

    def _redirect_stderr(self, to: int):
        sys.stderr.flush()
        sys.stderr.close()
        os.dup2(to, self.fderr)
        sys.stderr = os.fdopen(self.fderr, 'w')

    def __enter__(self):
        _capture_std_lock.acquire()
        self._lock_acquired = True
        try:
            self.fdout = self._try_fileno(sys.stdout)
            self.fderr = self._try_fileno(sys.stderr)
            if self.fdout is None or self.fderr is None:
                # 降级为 Python 级流捕获，避免 StringIO / pythonw 触发 UnsupportedOperation
                self._py_mode = True
                self._old_py_stdout = sys.stdout
                self._old_py_stderr = sys.stderr
                self._buf_out = io.StringIO()
                self._buf_err = io.StringIO()
                sys.stdout = self._buf_out
                sys.stderr = self._buf_err
                return self

            self.reader_out, self.writer_out = os.pipe()
            self.reader_err, self.writer_err = os.pipe()
            self.old_stdout = os.dup(self.fdout)
            self.old_stderr = os.dup(self.fderr)

            file_out = os.fdopen(self.writer_out, 'w')
            file_err = os.fdopen(self.writer_err, 'w')
            self._redirect_stdout(to=file_out.fileno())
            self._redirect_stderr(to=file_err.fileno())
            with contextlib.suppress(Exception):
                file_out.close()
            with contextlib.suppress(Exception):
                file_err.close()
            self._fd_mode = True
            return self
        except Exception:
            self._cleanup_on_exit()
            raise

    def _cleanup_on_exit(self):
        try:
            if self._py_mode:
                if self._old_py_stdout is not None:
                    sys.stdout = self._old_py_stdout
                if self._old_py_stderr is not None:
                    sys.stderr = self._old_py_stderr
                self.stdout = (self._buf_out.getvalue() if self._buf_out else '').encode('utf-8', errors='replace')
                self.stderr = (self._buf_err.getvalue() if self._buf_err else '').encode('utf-8', errors='replace')
                return

            if self._fd_mode:
                if self.old_stdout is not None:
                    with contextlib.suppress(Exception):
                        self._redirect_stdout(to=self.old_stdout)
                    with contextlib.suppress(OSError):
                        os.close(self.old_stdout)
                    self.old_stdout = None
                if self.old_stderr is not None:
                    with contextlib.suppress(Exception):
                        self._redirect_stderr(to=self.old_stderr)
                    with contextlib.suppress(OSError):
                        os.close(self.old_stderr)
                    self.old_stderr = None
                if self.reader_out is not None:
                    self.stdout = self.recvall(self.reader_out)
                if self.reader_err is not None:
                    self.stderr = self.recvall(self.reader_err)
            else:
                for fd_name in ('old_stdout', 'old_stderr', 'writer_out', 'writer_err'):
                    fd = getattr(self, fd_name, None)
                    if fd is not None:
                        with contextlib.suppress(OSError):
                            os.close(fd)
                        setattr(self, fd_name, None)
            for fd_name in ('reader_out', 'reader_err'):
                fd = getattr(self, fd_name, None)
                if fd is not None:
                    with contextlib.suppress(OSError):
                        os.close(fd)
                    setattr(self, fd_name, None)
        finally:
            if self._lock_acquired:
                self._lock_acquired = False
                _capture_std_lock.release()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup_on_exit()

    @staticmethod
    def recvall(reader, length=1024) -> bytes:
        fragments = []
        while 1:
            chunk = os.read(reader, length)
            if chunk:
                fragments.append(chunk)
            else:
                break
        output = b''.join(fragments)
        return output


class CaptureNemuIpc(CaptureStd):
    _capture_depth: int = 0
    _owner_thread_id: int | None = None

    def is_capturing(self):
        """Only skip redundant FD capture when already nested on the same thread."""
        cls = self.__class__
        return cls._capture_depth > 0 and cls._owner_thread_id == threading.get_ident()

    def __enter__(self):
        _capture_std_lock.acquire()
        self._skip_exit = False
        if self.is_capturing():
            self._skip_exit = True
            _capture_std_lock.release()
            return self

        CaptureNemuIpc._owner_thread_id = threading.get_ident()
        CaptureNemuIpc._capture_depth += 1
        try:
            super().__enter__()
        except Exception:
            CaptureNemuIpc._capture_depth = max(0, CaptureNemuIpc._capture_depth - 1)
            if CaptureNemuIpc._capture_depth == 0:
                CaptureNemuIpc._owner_thread_id = None
            _capture_std_lock.release()
            raise
        # super().__enter__() 已额外持有一把 RLock，这里归还外层提前获取的那一次
        _capture_std_lock.release()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if getattr(self, '_skip_exit', False):
            return

        with _capture_std_lock:
            try:
                super().__exit__(exc_type, exc_val, exc_tb)
            finally:
                CaptureNemuIpc._capture_depth = max(0, CaptureNemuIpc._capture_depth - 1)
                if CaptureNemuIpc._capture_depth == 0:
                    CaptureNemuIpc._owner_thread_id = None

        self.check_stdout()
        self.check_stderr()

    def check_stdout(self):
        if not self.stdout:
            return
        logger.info(f'NemuIpc stdout: {self.stdout}')

    def check_stderr(self):
        if not self.stderr:
            return
        logger.error(f'NemuIpc stderr: {self.stderr}')

        # Calling an old MuMu12 player
        # Tested on 3.4.0
        # b'nemu_capture_display rpc error: 1783\r\n'
        # Tested on 3.7.3
        # b'nemu_capture_display rpc error: 1745\r\n'
        if b'error: 1783' in self.stderr or b'error: 1745' in self.stderr:
            raise NemuIpcIncompatible(
                f'NemuIpc requires MuMu12 version >= 3.8.13, please check your version')
        # contact_id incorrect
        # b'nemu_capture_display cannot find rpc connection\r\n'
        if b'cannot find rpc connection' in self.stderr:
            raise NemuIpcError(self.stderr)
        # Emulator died
        # b'nemu_capture_display rpc error: 1722\r\n'
        # MuMuVMMSVC.exe died
        # b'nemu_capture_display rpc error: 1726\r\n'
        # No idea how to handle yet
        if b'error: 1722' in self.stderr or b'error: 1726' in self.stderr:
            raise NemuIpcError('Emulator instance is probably dead')


def retry(func):
    @wraps(func)
    def retry_wrapper(self, *args, **kwargs):
        """
        Args:
            self (NemuIpcImpl):
        """
        init = None
        for _ in range(RETRY_TRIES):
            try:
                if callable(init):
                    retry_sleep(_)
                    init()
                return func(self, *args, **kwargs)
            # Can't handle
            except RequestHumanTakeover:
                break
            # Can't handle
            except NemuIpcIncompatible as e:
                logger.error(e)
                break
            # Function call timeout
            except asyncio.TimeoutError:
                logger.warning(f'Func {func.__name__}() call timeout, retrying: {_}')

                def init():
                    self.reconnect()
            # NemuIpcError
            except NemuIpcError as e:
                logger.error(e)

                def init():
                    self.reconnect()
            # Unknown, probably a trucked image
            except Exception as e:
                logger.exception(e)

                def init():
                    pass

        logger.critical(f'Retry {func.__name__}() failed')
        raise RequestHumanTakeover

    return retry_wrapper


class NemuIpcImpl:
    def __init__(self, nemu_folder: str, instance_id: int, display_id: int = 0):
        """
        Args:
            nemu_folder: Installation path of MuMu12, e.g. E:/ProgramFiles/MuMuPlayer-12.0
            instance_id: Emulator instance ID, starting from 0
            display_id: Always 0 if keep app alive was disabled
        """
        self.nemu_folder: str = nemu_folder
        self.instance_id: int = instance_id
        self.display_id: int = display_id

        list_dll = [
            # MuMuPlayer12
            os.path.abspath(os.path.join(nemu_folder, './shell/sdk/external_renderer_ipc.dll')),
            # MuMuPlayer12 5.0
            os.path.abspath(os.path.join(nemu_folder, './nx_device/12.0/shell/sdk/external_renderer_ipc.dll')),
            # MuMuPlayer15
            os.path.abspath(os.path.join(nemu_folder, './nx_device/15.0/shell/sdk/external_renderer_ipc.dll')),
        ]
        self.lib = None
        for ipc_dll in list_dll:
            if not os.path.exists(ipc_dll):
                continue
            try:
                self.lib = ctypes.CDLL(ipc_dll)
                break
            except OSError as e:
                logger.error(e)
                logger.error(f'ipc_dll={ipc_dll} exists, but cannot be loaded')
                continue
        if self.lib is None:
            # not found
            raise NemuIpcIncompatible(
                f'NemuIpc requires MuMu12 version >= 3.8.13, please check your version. '
                f'None of the following path exists: {list_dll}')
        # success
        logger.info(
            f'NemuIpcImpl init, '
            f'nemu_folder={nemu_folder}, '
            f'ipc_dll={ipc_dll}, '
            f'instance_id={instance_id}, '
            f'display_id={display_id}'
        )

        self.connect_id: int = 0
        self.width = 0
        self.height = 0

    def connect(self):
        if self.connect_id > 0:
            return

        connect_id = self.ev_run_sync(
            self.lib.nemu_connect,
            self.nemu_folder, self.instance_id
        )
        if connect_id == 0:
            raise NemuIpcError(
                'Connection failed, please check if nemu_folder is correct and emulator is running'
            )

        self.connect_id = connect_id
        # logger.info(f'NemuIpc connected: {self.connect_id}')

    def disconnect(self):
        if self.connect_id == 0:
            return

        self.ev_run_sync(
            self.lib.nemu_disconnect,
            self.connect_id
        )

        # logger.info(f'NemuIpc disconnected: {self.connect_id}')
        self.connect_id = 0

    def reconnect(self):
        self.disconnect()
        self.connect()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    @cached_property
    def _ev(self):
        return asyncio.new_event_loop()

    async def ev_run_async(self, func, *args, **kwargs):
        """
        Args:
            func: Sync function to call
            *args:
            **kwargs:

        Raises:
            asyncio.TimeoutError: If function call timeout
        """
        func_wrapped = partial(func, *args, **kwargs)
        # Increased timeout for slow PCs
        # Default screenshot interval is 0.2s, so a 0.15s timeout would have a fast retry without extra time costs
        result = await asyncio.wait_for(self._ev.run_in_executor(None, func_wrapped), timeout=0.15)
        return result

    def ev_run_sync(self, func, *args, **kwargs):
        """
        Args:
            func: Sync function to call
            *args:
            **kwargs:

        Raises:
            asyncio.TimeoutError: If function call timeout
            NemuIpcIncompatible:
            NemuIpcError
        """
        result = self._ev.run_until_complete(self.ev_run_async(func, *args, **kwargs))

        err = False
        if func.__name__ == 'nemu_connect':
            if result == 0:
                err = True
        else:
            if result > 0:
                err = True
        # Get to actual error message printed in std
        if err:
            logger.warning(f'Failed to call {func.__name__}, result={result}')
            with CaptureNemuIpc():
                result = self._ev.run_until_complete(self.ev_run_async(func, *args, **kwargs))

        return result

    def get_resolution(self):
        """
        Get emulator resolution, `self.width` and `self.height` will be set
        """
        if self.connect_id == 0:
            self.connect()

        width_ptr = ctypes.pointer(ctypes.c_int(0))
        height_ptr = ctypes.pointer(ctypes.c_int(0))
        nullptr = ctypes.POINTER(ctypes.c_int)()

        ret = self.ev_run_sync(
            self.lib.nemu_capture_display,
            self.connect_id, self.display_id, 0, width_ptr, height_ptr, nullptr
        )
        if ret > 0:
            raise NemuIpcError('nemu_capture_display failed during get_resolution()')
        self.width = width_ptr.contents.value
        self.height = height_ptr.contents.value

    @retry
    def screenshot(self):
        """
        Returns:
            np.ndarray: Image array in RGBA color space
                Note that image is upside down
        """
        if self.connect_id == 0:
            self.connect()

        self.get_resolution()

        width_ptr = ctypes.pointer(ctypes.c_int(self.width))
        height_ptr = ctypes.pointer(ctypes.c_int(self.height))
        length = self.width * self.height * 4
        pixels_pointer = ctypes.pointer((ctypes.c_ubyte * length)())

        ret = self.ev_run_sync(
            self.lib.nemu_capture_display,
            self.connect_id, self.display_id, length, width_ptr, height_ptr, pixels_pointer
        )
        if ret > 0:
            raise NemuIpcError('nemu_capture_display failed during screenshot()')

        # image = np.ctypeslib.as_array(pixels_pointer, shape=(self.height, self.width, 4))
        image = np.ctypeslib.as_array(pixels_pointer.contents).reshape((self.height, self.width, 4))
        return image

    def convert_xy(self, x, y):
        """
        Convert classic ADB coordinates to Nemu's
        `self.height` must be updated before calling this method

        Returns:
            int, int
        """
        x, y = int(x), int(y)
        x, y = self.height - y, x
        return x, y

    @retry
    def down(self, x, y):
        """
        Contact down, continuous contact down will be considered as swipe
        """
        if self.connect_id == 0:
            self.connect()
        if self.height == 0:
            self.get_resolution()

        x, y = self.convert_xy(x, y)

        ret = self.ev_run_sync(
            self.lib.nemu_input_event_touch_down,
            self.connect_id, self.display_id, x, y
        )
        if ret > 0:
            raise NemuIpcError('nemu_input_event_touch_down failed')

    @retry
    def up(self):
        """
        Contact up
        """
        if self.connect_id == 0:
            self.connect()

        ret = self.ev_run_sync(
            self.lib.nemu_input_event_touch_up,
            self.connect_id, self.display_id
        )
        if ret > 0:
            raise NemuIpcError('nemu_input_event_touch_up failed')


def serial_to_id(serial: str):
    """
    Predict instance ID from serial
    E.g.
        "127.0.0.1:16384" -> 0
        "127.0.0.1:16416" -> 1

    Returns:
        int: instance_id, or None if failed to predict
    """
    try:
        port = int(serial.split(':')[1])
    except (IndexError, ValueError):
        return None
    index, offset = divmod(port - 16384, 32)
    if 0 <= index < 32 and offset in [0, 1, 2]:
        return index
    else:
        return None


class NemuIpc():
    _display_id_checked = False

    def detect_display_id(self, package_name: str | None = None) -> int:
        """
        Detect virtual display ID where target package is running in MuMu Player.
        Returns 0 as default if keep-alive is disabled, not running, or detection fails.
        """
        pkg = package_name or getattr(self, 'package_name', '')
        if not pkg and hasattr(self, 'config'):
            pkg = getattr(self.config.script.device, 'package_name', '')
        if not pkg or not hasattr(self, 'adb_shell'):
            return 0

        try:
            out = self.adb_shell(['dumpsys', 'activity', 'activities'])
            for m in re.finditer(r'Display #(\d+).*?(?=Display #|\Z)', out, re.DOTALL):
                disp_id = int(m.group(1))
                chunk = m.group(0)
                if pkg in chunk:
                    if disp_id != 0:
                        logger.info(f'Detected MuMu keep-alive/multi-display: package {pkg} on Display {disp_id}')
                    return disp_id
        except Exception as e:
            logger.debug(f'detect_display_id failed: {e}')

        return 0

    def sync_display_id(self) -> int:
        """
        Synchronize display_id onto existing nemu_ipc instance if connected.
        """
        if not has_cached_property(self, 'nemu_ipc'):
            return 0
        target_display = self.detect_display_id()
        if self.nemu_ipc.display_id != target_display:
            logger.info(f'Switching nemu_ipc display_id from {self.nemu_ipc.display_id} to {target_display}')
            self.nemu_ipc.display_id = target_display
        return self.nemu_ipc.display_id

    @cached_property
    def nemu_ipc(self) -> NemuIpcImpl:
        """
        Initialize a nemu ipc implementation
        """
        display_id = self.detect_display_id()
        # Try existing settings first
        if self.config.script.device.emulatorinfo_path:
            folder = str(Path(self.config.script.device.emulatorinfo_path).parent.parent)
            index = serial_to_id(self.serial)
            if index is not None:
                try:
                    return NemuIpcImpl(
                        nemu_folder=folder,
                        instance_id=index,
                        display_id=display_id
                    ).__enter__()
                except (NemuIpcIncompatible, NemuIpcError) as e:
                    logger.error(e)
                    logger.error('Emulator info incorrect')

        # Search emulator instance
        # with E:\ProgramFiles\MuMuPlayer-12.0\shell\MuMuPlayer.exe
        # installation path is E:\ProgramFiles\MuMuPlayer-12.0
        if self.emulator_instance is None:
            logger.error('Unable to use NemuIpc because emulator instance not found')
            raise RequestHumanTakeover
        try:
            return NemuIpcImpl(
                nemu_folder=self.emulator_instance.emulator.abspath('../'),
                instance_id=self.emulator_instance.MuMuPlayer12_id,
                display_id=display_id
            ).__enter__()
        except (NemuIpcIncompatible, NemuIpcError) as e:
            logger.error(e)
            logger.error('Unable to initialize NemuIpc')
            raise RequestHumanTakeover

    def nemu_ipc_available(self) -> bool:
        if not self.is_mumu_family:
            return False
        if self.nemud_app_keep_alive == '':
            return False
        try:
            _ = self.nemu_ipc
        except RequestHumanTakeover:
            return False
        return True

    def nemu_ipc_release(self):
        self._display_id_checked = False
        if has_cached_property(self, 'nemu_ipc'):
            self.nemu_ipc.disconnect()
        del_cached_property(self, 'nemu_ipc')
        logger.info('nemu_ipc released')

    def screenshot_nemu_ipc(self):
        if not self._display_id_checked:
            self.sync_display_id()
            self._display_id_checked = True

        image = self.nemu_ipc.screenshot()

        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        cv2.flip(image, 0, dst=image)
        return image

    def click_nemu_ipc(self, x, y):
        self.nemu_ipc.down(x, y)
        self.sleep(ensure_time((0.050, 0.110)))
        self.nemu_ipc.down(x + random.randint(-2, 2), y + random.randint(-2, 2))
        self.sleep(ensure_time((0.008, 0.020)))
        self.nemu_ipc.up()
        self.sleep(ensure_time((0.020, 0.045)))

    def long_click_nemu_ipc(self, x, y, duration=1.0):
        self.nemu_ipc.down(x, y)
        self.sleep(duration)
        self.nemu_ipc.up()
        self.sleep(0.050)

    def swipe_nemu_ipc(self, p1, p2):
        points = insert_swipe(p0=p1, p3=p2)

        for point in points:
            self.nemu_ipc.down(*point)
            self.sleep(ensure_time((0.006, 0.015)))

        self.nemu_ipc.up()
        self.sleep(0.050)

    def drag_nemu_ipc(self, p1, p2, point_random=(-10, -10, 10, 10)):
        p1 = np.array(p1) - random_rectangle_point(point_random)
        p2 = np.array(p2) - random_rectangle_point(point_random)
        points = insert_swipe(p0=p1, p3=p2, speed=20)

        for point in points:
            self.nemu_ipc.down(*point)
            self.sleep(0.010)

        self.nemu_ipc.down(*p2)
        self.sleep(0.140)
        self.nemu_ipc.down(*p2)
        self.sleep(0.140)

        self.nemu_ipc.up()
        self.sleep(0.050)
