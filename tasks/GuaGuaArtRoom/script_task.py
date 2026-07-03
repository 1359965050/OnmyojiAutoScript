# This Python file uses the following encoding: utf-8
# @author AzurTian
import time
from datetime import datetime, timedelta
from typing import Optional

from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.GuaGuaArtRoom.assets import GuaGuaArtRoomAssets
from tasks.GuaGuaArtRoom.config import GuaGuaArtRoom
from tasks.GuaGuaArtRoom.page import create_gua_gua_pages
from tasks.base_task import BaseTask


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, GuaGuaArtRoomAssets):
    """呱呱画室限时活动任务"""

    limit_count: int = 0
    _remain_reward: Optional[int] = None
    _stop_reason: Optional[str] = None  # 'limit' 或 'exhausted'

    def run(self):
        cfg: GuaGuaArtRoom = self.config.gua_gua_art_room
        self.limit_count = cfg.gua_gua_art_room_config.limit_count

        # 1. 换御魂
        self._switch_soul(cfg.switch_soul_config)

        # 2. 注册并导航到活动页面
        self.pages = create_gua_gua_pages(self.navigator)
        self.goto_page(self.pages['page_act'])
        self.goto_page(self.pages['page_paint_collection'])

        # 3. 循环战斗
        battle_count = 0
        start_time = datetime.now()
        while True:
            self._check_timeout(start_time)
            self.screenshot()
            current = self.get_current_page()

            if current is None:
                time.sleep(0.5)
                continue

            if current.key == 'page_paint_collection':
                if not self._can_continue(battle_count):
                    logger.info('Stop condition reached')
                    self._submit_reward()
                    break
                self._enter_battle()
                battle_count += 1
                logger.info(f'Battle #{battle_count}')
                self.run_general_battle(cfg.general_battle_config)
                # 战斗结束，「今日可得」减少 10（每次挑战固定扣 10）
                if self._remain_reward is not None:
                    self._remain_reward -= 10
                    logger.info(f'今日可得更新: {self._remain_reward}')
                self._ensure_at_page(self.pages['page_paint_collection'])
                # 战斗结算后短暂休息，降低截图频率
                time.sleep(0.5)
            elif current.key == 'page_act':
                self.goto_page(self.pages['page_paint_collection'])
            else:
                logger.warning(f'Unknown page {current.key}, go back to page_act')
                self.goto_page(self.pages['page_act'])

        # 4. 收尾
        self.goto_page(page_main)
        self.set_next_run(task='GuaGuaArtRoom', success=True, finish=True)
        raise TaskEnd('GuaGuaArtRoom')

    def _switch_soul(self, switch_soul_config):
        """根据配置切换御魂"""
        if switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(switch_soul_config.switch_group_team)
        if switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(
                switch_soul_config.group_name,
                switch_soul_config.team_name
            )
        self.ui_get_current_page()
        self.ui_goto(page_main)

    def _check_timeout(self, start_time: datetime):
        """运行超过 1 小时强制退出，防止异常死循环"""
        if datetime.now() - start_time >= timedelta(hours=1):
            logger.warning('GuaGuaArtRoom run timeout, exit')
            raise TaskEnd('GuaGuaArtRoom timeout')

    def _can_continue(self, battle_count: int) -> bool:
        """判断是否可以继续挑战

        优先级：
        1. 用户配置的次数上限
        2. 今日可得 OCR 数值（首次读取后按每次 -10 缓存，降低 OCR 频率）
        """
        if self.limit_count > 0 and battle_count >= self.limit_count:
            self._stop_reason = 'limit'
            logger.info(f'Reach user limit: {self.limit_count}')
            return False

        # 首次或缓存异常时读取 OCR，后续按固定 10 点/次递减
        if self._remain_reward is None:
            remain = self._read_remain_reward()
            if remain is None:
                return True
            self._remain_reward = remain
        if self._remain_reward <= 0:
            self._stop_reason = 'exhausted'
            logger.info(f'Remain reward exhausted: {self._remain_reward}')
            return False
        return True

    def _read_remain_reward(self) -> Optional[int]:
        """OCR 识别左下角「今日可得」数值"""
        self.screenshot()
        value = self.O_REMAIN_REWARD.ocr_digit(self.device.image)
        return value

    def _enter_battle(self):
        """点击挑战按钮进入战斗"""
        click_times, max_times = 0, 5
        while True:
            self.check_stop()
            self.screenshot()
            if self.is_in_battle(False):
                return True
            if self.appear(self.I_UI_BACK_RED, interval=1):
                logger.warning('Appear red close button, maybe no tickets left')
                raise TaskEnd('GuaGuaArtRoom no tickets')
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                continue
            if self.appear_then_click(self.I_PAINT_CHALLENGE, interval=1.5):
                click_times += 1
                logger.info(f'Try click challenge, remain times[{max_times - click_times}]')
                continue
            if click_times >= max_times:
                logger.warning('Cannot enter battle, click reach max times')
                raise TaskEnd('GuaGuaArtRoom enter battle failed')
            time.sleep(0.3)

    def _ensure_at_page(self, target_page, timeout: int = 30):
        """战斗结束后确保回到目标页面，处理结算、奖励弹窗"""
        # 先等待结算动画/奖励弹窗稳定
        time.sleep(1.5)
        timer = Timer(timeout).start()
        while not timer.reached():
            self.check_stop()
            self.screenshot()
            if self.ui_reward_appear_click():
                continue
            current = self.get_current_page()
            if current is not None and current.key == target_page.key:
                return True
            # 当前在未知页面，先尝试关闭可能残留的弹窗/返回按钮
            if self.appear_then_click(self.I_UI_BACK_RED, interval=1):
                continue
            if self.appear_then_click(self.I_UI_BACK_YELLOW, interval=1):
                time.sleep(0.5)
                continue
            self.goto_page(target_page)
            time.sleep(0.5)
        logger.warning(f'Ensure at page {target_page.key} timeout')
        return False

    def _submit_reward(self):
        """任务结束时提交颜料奖励

        先检测/处理「前往提交」弹窗（今日可得耗尽时弹窗可能已出现），
        然后统一回到 page_act 点击「提交颜料」。
        """
        logger.info(f'Try submit paint reward, stop reason: {self._stop_reason}')

        # 1. 若已出现「前往提交」弹窗，点击前往活动主页面
        timer = Timer(5).start()
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_GO_SUBMIT):
                self.appear_then_click(self.I_GO_SUBMIT, interval=1)
                time.sleep(1)
                break
            time.sleep(0.3)

        # 2. 统一回到活动主页面（page_act）
        self.goto_page(self.pages['page_act'])

        # 3. 点击「提交颜料」
        timer = Timer(10).start()
        while not timer.reached():
            self.screenshot()
            if self.appear_then_click(self.I_SUBMIT_PAINT, interval=1):
                break
            time.sleep(0.3)
        else:
            logger.warning('Submit paint button not found')

        # 4. 处理可能的确认弹窗
        time.sleep(1)
        timer = Timer(5).start()
        while not timer.reached():
            self.screenshot()
            if self.appear_then_click(self.I_UI_CONFIRM, interval=1):
                break
            time.sleep(0.3)

        logger.info('Submit paint reward done')


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()
