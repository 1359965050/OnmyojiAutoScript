# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
import numpy as np
from module.base.timer import Timer
from module.exception import RequestHumanTakeover, GameTooManyClickError, GameStuckError
from module.logger import logger
from tasks.GameUi.assets import GameUiAssets
from tasks.Restart.assets import RestartAssets
from tasks.base_task import BaseTask
from module.device.handle import EmulatorFamily


class LoginService(BaseTask, RestartAssets, GameUiAssets):
    character: str

    def __init__(self, *wargs, **kwargs):
        super().__init__(*wargs, **kwargs)
        self.character = self.config.restart.login_character_config.character
        self.O_LOGIN_SPECIFIC_SERVE.keyword = self.character

    def _app_handle_login(self) -> bool:
        """
        最终是在庭院界面
        :return:
        """
        logger.hr('App login')
        self.device.stuck_record_add('LOGIN_CHECK')

        confirm_timer = Timer(1.5, count=2).start()
        orientation_timer = Timer(10)
        skip_login_animation = True
        skip_click_mx_cnt = 5
        login_success = False
        anim_skip_first_wait = True

        if hasattr(self.device, 'bring_to_front'):
            self.device.bring_to_front()

        while True:
            if not login_success and orientation_timer.reached():
                self.device.get_orientation()
                orientation_timer.reset()

            self.screenshot()

            # 游戏启动初期或场景切换可能存在纯黑屏加载阶段，避免在未完成渲染时过早触发 OCR 或误操作
            if hasattr(self.device, 'image') and self.device.image is not None:
                if float(np.mean(self.device.image)) < 12:
                    logger.info('Game window is loading (black screen), waiting for rendering...')
                    time.sleep(0.5)
                    continue

            if self.appear_then_click(self.I_CANCEL_BATTLE, interval=0.8):
                logger.info('Cancel continue battle')
                continue
            if self.appear(self.I_CHECK_MAIN, interval=0.2) and not self.appear(self.I_MAIN_GOTO_SHIKIGAMI_RECORDS):
                logger.info('The main had already appeared, but shikigami records had not yet appeared')
                skip_login_animation = False
                if self.click(self.C_LOGIN_SCROLL_CLOSE_AREA, interval=2):
                    continue
            if self.appear(self.I_MAIN_GOTO_SHIKIGAMI_RECORDS, interval=0.2):
                if confirm_timer.reached():
                    logger.info('Login to main confirm (shikigami records button appears)')
                    break
            else:
                confirm_timer.reset()
            if self.appear(self.I_MAIN_GOTO_SHIKIGAMI_RECORDS, interval=0.5):
                logger.info('Login success: shikigami records button appears')
                login_success = True
                skip_login_animation = False
                continue
            if self.appear(self.I_HARVEST_ZIDU, interval=1):
                self.I_HARVEST_ZIDU.roi_front[0] -= 200
                self.I_HARVEST_ZIDU.roi_front[1] -= 200
                if self.click(self.I_HARVEST_ZIDU, interval=2):
                    logger.info('Close zidu')
                continue
            if self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=2.5):
                logger.info('Soul overflow confirm')
                continue
            if self.appear_then_click(self.I_LOGIN_LOAD_DOWN, interval=1):
                logger.info('Download inbetweening')
                continue
            if self.appear_then_click(self.I_WATCH_VIDEO_CANCEL, interval=0.6):
                logger.info('Close video')
                continue
            if self.appear_then_click(self.I_LOGIN_RED_CLOSE, interval=0.6):
                logger.info('Close red close')
                continue
            if self.appear_then_click(self.I_LOGIN_YELLOW_CLOSE, interval=0.6):
                logger.info('Close yellow close')
                continue
            if self.appear_then_click(self.I_LOGIN_LOGIN_GOTO_BIND_PHONE):
                while True:
                    self.screenshot()
                    if self.appear_then_click(self.I_LOGIN_LOGIN_CANCEL_BIND_PHONE):
                        logger.info("Close bind phone")
                        break
                continue
            from tasks.Component.GeneralInvite.assets import GeneralInviteAssets as gia
            if self.appear_then_click(gia.I_I_REJECT, interval=0.8):
                logger.info("reject invites")
                continue
            if self.appear_then_click(self.I_LOGIN_LOGIN_ONMYOJI_GENIE):
                logger.info("click onmyoji genie")
                continue
            if self.appear(self.I_LOGIN_SPECIFIC_SERVE, interval=0.6) \
                    and self.ocr_appear_click(self.O_LOGIN_SPECIFIC_SERVE, interval=0.6):
                while True:
                    self.screenshot()
                    if self.appear(self.I_LOGIN_SPECIFIC_SERVE):
                        self.click(self.C_LOGIN_ENSURE_LOGIN_CHARACTER_IN_SAME_SVR, interval=2)
                        continue
                    break
                logger.info('login specific user')
                continue

            if self.appear(self.I_CREATE_ACCOUNT):
                logger.warning('Appear create account')
                raise GameStuckError('Appear create account')

            if self.appear(self.I_CHARACTARS, interval=1):
                logger.info('误入区服设置')
                self.device.click(x=106, y=535)
                continue

            if self.appear(self.I_EARLY_SERVER) and self.appear_then_click(self.I_EARLY_SERVER_CANCEL):
                logger.info('Cancel switch from early server to normal server')
                continue

            # 已进入庭院或登录成功后，不再执行任何登录/进入游戏逻辑
            if not login_success and not self.appear(self.I_CHECK_MAIN):
                # 检测到登录页面标志后，立即终止登录动画逻辑
                if (self.appear(self.I_LOGIN_8)
                        or self.appear(self.I_LOGIN_CADPA_RIGHT)
                        or skip_click_mx_cnt <= 0):
                    skip_login_animation = False

                if skip_login_animation:
                    if anim_skip_first_wait:
                        logger.info('Wait 2s before checking LOGIN_ANIMATION_SKIP...')
                        time.sleep(2.0)
                        anim_skip_first_wait = False
                        self.screenshot()

                    if self.ocr_appear_click(self.O_LOGIN_ANIMATION_SKIP, interval=3):  # 点击跳过登录动画
                        continue
                    if self.ocr_appear_click(self.O_LOGIN_SKIP_1, interval=3):  # 点击屏幕跳过
                        continue
                    is_win_client = (getattr(self.device, 'emulator_family', None) == EmulatorFamily.FAMILY_WINDOWS_CLIENT)
                    if is_win_client:
                        if self.click_foreground(self.C_LOGIN_ANIMATION_CENTER, interval=3.0):
                            skip_click_mx_cnt -= 1
                    else:
                        if self.click(self.C_LOGIN_ANIMATION_CENTER, interval=3.5):  # 点击安全区域触发跳过显示或跳过CG
                            skip_click_mx_cnt -= 1
                else:
                    # 选区界面：优先使用 OCR 点击金色【进入游戏】按钮
                    if self.ocr_appear_click(self.O_LOGIN_ENTER_GAME, interval=2):
                        logger.info('Click enter game via OCR')
                        self.wait_until_appear(self.I_LOGIN_SPECIFIC_SERVE, True, wait_time=3, log_level='info')
                        continue

                    # 若在选区界面检测到适龄提示（支持左下角 I_LOGIN_8 与右下角 I_LOGIN_CADPA_RIGHT），点击进入游戏
                    if self.appear(self.I_LOGIN_8, interval=2.5) or self.appear(self.I_LOGIN_CADPA_RIGHT, interval=2.5):
                        logger.info('Click screen to enter game on server select page')
                        self.device.click(x=636, y=595, control_name='login_enter_game_fallback')
                        continue

        return login_success

    def app_handle_login(self) -> bool:
        self.device.stuck_record_clear()
        self.device.click_record_clear()
        try:
            self._app_handle_login()
            return True
        except (GameTooManyClickError, GameStuckError) as e:
            logger.warning(e)
            self.device.app_stop()
            self.device.app_start()

        logger.critical('Login failed')
        logger.critical('Onmyoji server may be under maintenance, or you may lost network connection')
        raise RequestHumanTakeover

    def set_specific_usr(self, character: str):
        self.character = character
        self.O_LOGIN_SPECIFIC_SERVE.keyword = character
