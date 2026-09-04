
from collections import deque
from datetime import datetime
import time
import numpy as np

# Patch pkg_resources before importing adbutils and uiautomator2
from module.device.pkg_resources import get_distribution
# Just avoid being removed by import optimization
_ = get_distribution

from module.base.utils import get_color
from module.device.env import IS_WINDOWS
from module.base.timer import Timer
from module.config.utils import get_server_next_update
from module.device.app_control import AppControl
from module.device.control import Control
from module.device.platform2 import Platform
from module.device.screenshot import Screenshot
from module.exception import (GameNotRunningError,
                              GameStuckError,
                              GameTooManyClickError,
                              RequestHumanTakeover,
                              EmulatorNotRunningError)
from module.base.decorator import del_cached_property
from module.logger import logger


class Device(Platform, Screenshot, Control, AppControl):
    _screen_size_checked = False
    detect_record = set()
    click_record = deque(maxlen=15)
    stuck_timer = Timer(60, count=60).start()
    stuck_timer_long = Timer(300, count=300).start()
    stuck_long_wait_list = ['BATTLE_STATUS_S', 'PAUSE', 'LOGIN_CHECK', 'PREPARE_BEFORE_BATTLE']

    def __init__(self, *args, **kwargs):
        # 预先探测是否为 Windows 桌面版渠道
        config_obj = args[0] if args else kwargs.get('config', None)
        is_pc = False
        if config_obj:
            try:
                device_cfg = getattr(config_obj.script, 'device', None)
                if device_cfg:
                    emu_type = getattr(device_cfg, 'emulatorinfo_type', '')
                    emu_val = getattr(emu_type, 'value', emu_type)
                    emu_str = f"{emu_type} {emu_val}".lower()
                    pkg = getattr(device_cfg, 'package_name', '')
                    pkg_val = getattr(pkg, 'value', pkg)
                    pkg_str = f"{pkg} {pkg_val}".lower()
                    serial = str(getattr(device_cfg, 'serial', '')).lower()
                    if ('windowsclient' in emu_str or 'windows_client' in emu_str or emu_str.strip() == 'pc'
                            or 'windows-0' in serial or serial in ('pc', 'windows')
                            or 'onmyoji.exe' in pkg_str or 'windows_onmyoji' in pkg_str):
                        is_pc = True
            except Exception:
                pass

        if is_pc:
            super().__init__(*args, **kwargs)
            from tasks.Script.config_device import ScreenshotMethod, ControlMethod
            self.config.script.device.screenshot_method = ScreenshotMethod.WINDOW_BACKGROUND
            self.config.script.device.control_method = ControlMethod.WINDOW_MESSAGE
            self.screenshot_interval_set()
            self._image_batch_cache_frame_id: str | None = None
            self._image_batch_cache: dict[int, dict] = {}
            from module.device.handle import is_handle_valid, Handle
            need_login = False
            if not self.app_is_alive():
                logger.info('Onmyoji PC client is not running, launching...')
                self.app_start()
                need_login = True
            # 无论是刚拉起还是已在拉起中，轮询等待直到有效窗口句柄被成功捕获（最长等待 25s）
            hwnd = getattr(self, 'screenshot_handle_num', 0)
            if not hwnd or not is_handle_valid(hwnd):
                for wait_i in range(50):
                    time.sleep(0.5)
                    # 轻量检查是否有阴阳师可见窗口，避免在等待期间刷屏产生 ERROR
                    win_list = Handle.all_windows()
                    has_yys = any('阴阳师' in w or 'Onmyoji' in w for w in win_list)
                    if has_yys:
                        if hasattr(self, 'init_handle'):
                            self.init_handle()
                        hwnd = getattr(self, 'screenshot_handle_num', 0)
                        if hwnd and is_handle_valid(hwnd):
                            logger.info(f'Onmyoji PC client window ready after {(wait_i + 1) * 0.5:.1f}s.')
                            if hasattr(self, 'bring_to_front'):
                                self.bring_to_front()
                            break
                    if (wait_i + 1) % 4 == 0:  # 每 2 秒提示一次
                        logger.info(f'Waiting for Onmyoji PC client window to appear (elapsed: {(wait_i + 1) * 0.5:.1f}s)...')
                else:
                    logger.warning('Timeout waiting for Onmyoji PC client window to appear.')
                    if hasattr(self, 'init_handle'):
                        self.init_handle()
            logger.info('Device initialized successfully for Windows Native Client.')

            # 关键等待：等待客户端窗口脱离启动黑屏阶段，确保游戏画面渲染就绪
            self.wait_app_start_ready(timeout=25.0)

            # 将游戏主窗口置于前台激活
            if hasattr(self, 'bring_to_front'):
                self.bring_to_front()

            # 若新拉起客户端或当前停留在登录界面，在进入业务功能任务前先完成登录进入庭院
            try:
                from module.image.rpc import ensure_image_server_ready
                ensure_image_server_ready()
                from tasks.Restart.assets import RestartAssets
                from tasks.Component.Login.service import LoginService
                self.screenshot()
                is_at_login = (
                    need_login
                    or RestartAssets.I_LOGIN_PC_ENTER_GAME.match(self.image)
                    or RestartAssets.I_LOGIN_CADPA_RIGHT.match(self.image)
                )
                if is_at_login:
                    logger.info('Detected login screen on PC client, handling login to enter courtyard first...')
                    LoginService(config=self.config, device=self).app_handle_login()
            except Exception as e:
                logger.warning(f'Auto login in Device init: {e}')
            return

        for trial in range(4):
            try:
                super().__init__(*args, **kwargs)
                break
            except EmulatorNotRunningError:
                if trial >= 3:
                    logger.critical('Failed to start emulator after 3 trial')
                    raise RequestHumanTakeover
                # Try to start emulator
                if self.emulator_instance is not None:
                    self.emulator_start()
                else:
                    logger.critical(
                        f'未检测到模拟器实例，无法自动拉起模拟器，连接设备 "{self.serial}" 失败。\n'
                        f'==================== [排查建议] ====================\n'
                        f'1. 模拟器是否未启动？请先手动启动模拟器（如 MuMu 12），确认进入安卓桌面后再运行脚本。\n'
                        f'2. 端口是否一致？当前设置连接端口为 {self.serial}，请确认模拟器设置中的 ADB 端口是否与之一致。\n'
                        f'3. 若端口经常变化或多开，可在前端 [设置 -> 模拟器设置 -> 模拟器 Serial] 填写 "auto" 尝试自动检测。\n'
                        f'===================================================='
                    )
                    raise RequestHumanTakeover

        # Auto-fill emulator info
        if IS_WINDOWS and self.config.script.device.emulatorinfo_type == 'auto':
            _ = self.emulator_instance

        self.screenshot_interval_set()
        self._image_batch_cache_frame_id: str | None = None
        self._image_batch_cache: dict[int, dict] = {}

        # Auto-select the fastest screenshot method
        if self.config.script.device.screenshot_method == 'auto':
            self.run_simple_screenshot_benchmark()

    def reset_image_batch_cache(self, frame_id: str | None = None) -> None:
        self._image_batch_cache_frame_id = frame_id
        self._image_batch_cache = {}

    def invalidate_image_batch_cache(self) -> None:
        self.reset_image_batch_cache()

    def get_image_batch_cache(self, target, frame_id: str | None = None) -> dict | None:
        active_frame_id = self.image_frame_id if frame_id is None else frame_id
        if active_frame_id is None:
            return None
        if self._image_batch_cache_frame_id != active_frame_id:
            return None
        return self._image_batch_cache.get(id(target))

    def update_image_batch_cache(self, targets: list, results: list[dict], frame_id: str | None = None) -> None:
        active_frame_id = self.image_frame_id if frame_id is None else frame_id
        if active_frame_id is None:
            return
        if self._image_batch_cache_frame_id != active_frame_id:
            self.reset_image_batch_cache(active_frame_id)
        for target, result in zip(targets, results):
            self._image_batch_cache[id(target)] = dict(result)

    def run_simple_screenshot_benchmark(self):
        """
        Perform a screenshot method benchmark, test 3 times on each method.
        The fastest one will be set into config.
        """
        logger.info('run_simple_screenshot_benchmark')
        # Check resolution first
        # self.resolution_check_uiautomator2()
        # Perform benchmark
        from module.daemon.benchmark import Benchmark
        bench = Benchmark(config=self.config, device=self)
        method = bench.run_simple_screenshot_benchmark()
        # Set
        self.config.script.device.screenshot_method = method
        self.config.save()

    def handle_night_commission(self, daily_trigger='21:00', threshold=30):
        """
        Args:
            daily_trigger (int): Time for commission refresh.
            threshold (int): Seconds around refresh time.

        Returns:
            bool: If handled.
        """
        update = get_server_next_update(daily_trigger=daily_trigger)
        now = datetime.now()
        diff = (update.timestamp() - now.timestamp()) % 86400
        if threshold < diff < 86400 - threshold:
            return False

        # if GET_MISSION.match(self.image, offset=True):
        #     logger.info('Night commission appear.')
        #     self.click(GET_MISSION)
        #     return True

        return False

    def screenshot(self):
        """
        Returns:
            np.ndarray:
        """
        self.stuck_record_check()

        if getattr(self, 'is_windows_client', False):
            from module.device.handle import is_handle_valid, Handle
            hwnd = getattr(self, 'screenshot_handle_num', 0)
            if not hwnd or not is_handle_valid(hwnd):
                for retry in range(6):
                    win_list = Handle.all_windows()
                    if any('阴阳师' in w or 'Onmyoji' in w for w in win_list):
                        if hasattr(self, 'init_handle'):
                            self.init_handle()
                        hwnd = getattr(self, 'screenshot_handle_num', 0)
                        if hwnd and is_handle_valid(hwnd):
                            break
                    time.sleep(0.5)
                if not hwnd or not is_handle_valid(hwnd):
                    raise GameNotRunningError('Onmyoji PC client window not found')

        try:
            super().screenshot()
        except RequestHumanTakeover as e:
            raise RequestHumanTakeover

        if self.handle_night_commission():
            super().screenshot()

        self.reset_image_batch_cache(self.image_frame_id)
        return self.image

    def release_during_wait(self):
        # Scrcpy server is still sending video stream,
        # stop it during wait
        # self.config.script.device.screenshot_method = 'scrcpy'
        if self.config.script.device.screenshot_method == 'scrcpy':
            self._scrcpy_server_stop()
        if self.config.Emulator_ScreenshotMethod == 'nemu_ipc':
            self.nemu_ipc_release()

    def stuck_record_add(self, button):
        """
        当你要设置这个时候检测为长时间的时候，你需要在这里添加
        如果取消后，需要在`stuck_record_clear`中清除
        :param button:
        :return:
        """
        self.detect_record.add(str(button))
        logger.info(f'Add stuck record: {button}')

    def stuck_record_clear(self):
        self.detect_record = set()
        self.stuck_timer.reset()
        self.stuck_timer_long.reset()

    def stuck_record_check(self):
        """
        Raises:
            GameStuckError:
        """
        reached = self.stuck_timer.reached()
        reached_long = self.stuck_timer_long.reached()

        if not reached:
            return False
        if not reached_long:
            for button in self.stuck_long_wait_list:
                if button in self.detect_record:
                    return False

        logger.warning('Wait too long')
        logger.warning(f'Waiting for {self.detect_record}')
        self.stuck_record_clear()

        if self.app_is_running():
            raise GameStuckError(f'Wait too long')
        else:
            raise GameNotRunningError('Game died')

    def handle_control_check(self, button):
        self.stuck_record_clear()
        self.click_record_add(button)
        self.click_record_check()

    def click_record_add(self, button):
        self.click_record.append(str(button))

    def click_record_clear(self):
        self.click_record.clear()

    def click_record_remove(self, button):
        """
        Remove a button from `click_record`

        Args:
            button (Button):

        Returns:
            int: Number of button removed
        """
        removed = 0
        for _ in range(self.click_record.maxlen):
            try:
                self.click_record.remove(str(button))
                removed += 1
            except ValueError:
                # Value not in queue
                break

        return removed

    def click_record_check(self):
        """
        Raises:
            GameTooManyClickError:
        """
        count = {}
        for key in self.click_record:
            count[key] = count.get(key, 0) + 1
        count = sorted(count.items(), key=lambda item: item[1], reverse=True)
        if count[0][1] >= 10:
            logger.warning(f'Too many click for a button: {count[0][0]}')
            logger.warning(f'History click: {[str(prev) for prev in self.click_record]}')
            self.click_record_clear()
            raise GameTooManyClickError(f'Too many click for a button: {count[0][0]}')
        if len(count) >= 2 and count[0][1] >= 6 and count[1][1] >= 6:
            logger.warning(f'Too many click between 2 buttons: {count[0][0]}, {count[1][0]}')
            logger.warning(f'History click: {[str(prev) for prev in self.click_record]}')
            self.click_record_clear()
            raise GameTooManyClickError(f'Too many click between 2 buttons: {count[0][0]}, {count[1][0]}')

    def disable_stuck_detection(self):
        """
        Disable stuck detection and its handler. Usually uses in semi auto and debugging.
        """
        logger.info('Disable stuck detection')

        def empty_function(*arg, **kwargs):
            return False

        self.click_record_check = empty_function
        self.stuck_record_check = empty_function

    def app_start(self):
        if not self.config.script.error.handle_error:
            logger.critical('No app stop/start, because HandleError disabled')
            logger.critical('Please enable script.error.handle_error or manually login to Onmyoji')
            raise RequestHumanTakeover
        super().app_start()
        self.stuck_record_clear()
        self.click_record_clear()

    def app_stop(self):
        if not self.config.script.error.handle_error:
            logger.critical('No app stop/start, because HandleError disabled')
            logger.critical('Please enable script.error.handle_error or manually login to Onmyoji')
            raise RequestHumanTakeover
        super().app_stop()
        self.stuck_record_clear()
        self.click_record_clear()

    def wait_app_start_ready(self, timeout: float = 15.0, interval: float = 0.5) -> None:
        """
        在启动app后，等待包名切换成功且画面脱离纯黑状态。

        这里直接调用底层截图方法做静默探测，避免app刚启动时首屏黑场造成成批告警。

        Args:
            timeout: 最大等待秒数。
            interval: 每轮探测的间隔秒数。
        """
        deadline = time.time() + timeout
        screenshot_method = self.screenshot_methods.get(
            self.config.script.device.screenshot_method,
            self.screenshot_adb
        )

        while time.time() < deadline:
            if not self.app_is_running():
                time.sleep(interval)
                continue

            try:
                image = screenshot_method()
            except Exception as e:
                logger.info(f'Wait game start ready: screenshot probe failed: {e}')
                time.sleep(interval)
                continue

            color = get_color(image, area=(0, 0, 1280, 720))
            mean_brightness = float(np.mean(image)) if hasattr(image, 'mean') else sum(color) / 3.0
            if mean_brightness >= 12 and sum(color) >= 30:
                logger.info(f'Game start ready, frame mean brightness: {mean_brightness:.1f}, color: {color}')
                # 给予游戏首屏渲染与 CEF 控件就绪的稳定缓冲时间
                time.sleep(1.0)
                return

            time.sleep(interval)

        logger.info('Wait game start ready timeout, continue with login flow')

    def emulator_restart(self) -> bool:
        """
        重启模拟器：优雅释放截屏/触控资源，停止模拟器，重新拉起并刷新句柄与截屏缓存。
        """
        logger.hr('Emulator restart', level=1)
        if self.emulator_instance is None:
            logger.warning('No emulator instance detected, cannot restart emulator')
            return False

        self.release_during_wait()
        if not self.emulator_stop():
            logger.warning('Emulator stop returned False, proceeding to start attempt')

        time.sleep(2)

        if not self.emulator_start():
            logger.error('Failed to start emulator during restart')
            return False

        # 清理由于窗口重新创建导致的句柄与截图尺寸缓存
        del_cached_property(self, 'root_node')
        del_cached_property(self, 'screenshot_handle_num')
        del_cached_property(self, 'screenshot_size')
        self._screen_size_checked = False
        self._screen_black_checked = False
        logger.info('Emulator restart completed successfully')
        return True



if __name__ == "__main__":
    device = Device(config="oas1")
    # cv2.imshow("imgSrceen", device.screenshot())  # 显示
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()
