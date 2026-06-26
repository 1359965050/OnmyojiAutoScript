import timeit
import numpy as np
from datetime import datetime

from module.base.timer import Timer
from module.logger import logger
from module.base.utils import point2str
from module.exception import RequestHumanTakeover, GameStuckError
from tasks.base_task import BaseTask

from tasks.Hyakkiyakou.config import ScreenshotMethod, ControlMethod

def image_black(img) -> bool:
    if img is None or img.size == 0:
        return True
    h, w = img.shape[:2]
    if h < 720 or w < 1280:
        return True
    for y, x in [(0, 0), (719, 1279), (719, 0), (0, 1279)]:
        if np.all(img[y, x] != 0):
            return False
    return True


class HyaDevice(BaseTask):
    """
    这个类主要是是优化截屏点击速度
    1. 使用特别的method
    2. 扔掉中间的冗余校验
    3. 考虑JIT加速
    我宣布世界上最好的 Linux 系统是 Windows
    """
    hya_screenshot_interval = Timer(0.2)  # 300ms
    hya_fs_check_timer = Timer(3 * 60)  # 五分钟跑不完就应该是出问题了

    def fast_screenshot(self, screenshot: ScreenshotMethod):
        self.hya_screenshot_interval.wait()
        self.hya_screenshot_interval.reset()

        def _fallback_uiautomator2():
            logger.warning('Fallback to uiautomator2 screenshot')
            self.device.image = self.device.screenshot_uiautomator2()

        root_handle_valid = hasattr(self.device, 'root_handle_num') and self.device.root_handle_num != 0

        try:
            if screenshot == ScreenshotMethod.WINDOW_BACKGROUND and root_handle_valid:
                self.device.image = self.device.screenshot_window_background()
            elif screenshot == ScreenshotMethod.NEMU_IPC and hasattr(self.device, 'screenshot_nemu_ipc'):
                self.device.image = self.device.screenshot_nemu_ipc()
            else:
                if screenshot == ScreenshotMethod.WINDOW_BACKGROUND and not root_handle_valid:
                    logger.warning('window_background screenshot requires valid handle')
                self.device.image = self.device.screenshot_uiautomator2()
        except Exception as e:
            logger.warning(f'{screenshot} screenshot failed: {e}, fallback to uiautomator2')
            _fallback_uiautomator2()

        # 如果截到的图异常（黑屏/空/尺寸不对），回退到 uiautomator2 再试一次
        if image_black(self.device.image):
            logger.warning('Screenshot image is black or empty, fallback to uiautomator2')
            _fallback_uiautomator2()

        if image_black(self.device.image):
            logger.error('Screenshot image is still black or empty after fallback')
            raise RequestHumanTakeover('Screenshot image is black, try again')

        if self.hya_fs_check_timer.reached():
            logger.error('Fast screenshot check timer reached')
            logger.error('Five minutes have not ended, the game is probably stuck, please check the game')
            raise GameStuckError
        if self.config.script.error.save_error:
            self.device.screenshot_deque.append({'time': datetime.now(), 'image': self.device.image})
        return self.device.image

    def fast_click(self, x: int, y: int, control_method: ControlMethod = ControlMethod.WINDOW_MESSAGE) -> None:
        logger.info(
            'Click %s @ %s' % (point2str(x, y), 'Click')
        )
        if control_method == ControlMethod.MINITOUCH:
            self.device.click_minitouch(x=x, y=y)
            return

        control_handle_valid = (
            hasattr(self.device, 'root_node')
            and self.device.root_node is not None
            and self.device.root_node.children
        )

        if control_method == ControlMethod.WINDOW_MESSAGE and control_handle_valid:
            try:
                self.device.click_window_message(x=x, y=y, fast=True)
            except Exception as e:
                logger.warning(f'window_message click failed: {e}, fallback to minitouch')
                self.device.click_minitouch(x=x, y=y)
        else:
            if control_method == ControlMethod.WINDOW_MESSAGE and not control_handle_valid:
                logger.warning('window_message click requires valid control handle list, fallback to minitouch')
            self.device.click_minitouch(x=x, y=y)

    def set_fast_screenshot_interval(self, interval: float):
        """

        @param interval: ms
        @return:
        """
        self.hya_screenshot_interval = Timer(interval / 1000.)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    hd = HyaDevice(c, d)

    # def screenshot():
    #     global hd
    #     # hd.fast_screenshot()
    #     hd.fast_click(420, 370)
    #     hd.fast_click(750, 400)
    # execution_time = timeit.timeit(screenshot, number=50)
    # print(f"执行总的时间: {execution_time * 1000} ms")

    hd.fast_screenshot()

