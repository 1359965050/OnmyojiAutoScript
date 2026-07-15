# This Python file uses the following encoding: utf-8
# @author runhey
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
from tasks.AbyssIllusion.assets import AbyssIllusionAssets
from tasks.AbyssIllusion.config import AbyssIllusion
from tasks.AbyssIllusion.page import create_abyss_illusion_pages
from tasks.base_task import BaseTask


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, AbyssIllusionAssets):
    """狭间幻境限时活动任务"""

    limit_count: int = 0

    def run(self):
        cfg: AbyssIllusion = self.config.abyss_illusion
        self.limit_count = cfg.abyss_illusion_config.limit_count

        # 1. 换御魂
        self._switch_soul(cfg.switch_soul_config)

        # 2. 注册并导航到活动页面
        self.pages = create_abyss_illusion_pages(self.navigator)
        self.goto_page(self.pages['page_act'])
        self.goto_page(self.pages['page_abyss_illusion'])

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

            if current.key == 'page_abyss_illusion':
                # 检查是否可以继续
                if not self._can_continue(battle_count):
                    logger.info('Stop condition reached')
                    break

                # 进入战斗
                self._enter_battle()
                battle_count += 1
                logger.info(f'Battle #{battle_count}')
                self.run_general_battle(cfg.general_battle_config)

                # 确保回到挑战页面
                self._ensure_at_page(self.pages['page_abyss_illusion'])
                time.sleep(0.5)
            elif current.key == 'page_act':
                self.goto_page(self.pages['page_abyss_illusion'])
            else:
                logger.warning(f'Unknown page {current.key}, go back to page_act')
                self.goto_page(self.pages['page_act'])

        # 4. 收尾
        self.goto_page(page_main)
        self.set_next_run(task='AbyssIllusion', success=True, finish=True)
        raise TaskEnd('AbyssIllusion')

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
        """超时检测，运行超过 1 小时强制退出"""
        if datetime.now() - start_time >= timedelta(hours=1):
            logger.warning('AbyssIllusion run timeout, exit')
            raise TaskEnd('AbyssIllusion timeout')

    def _can_continue(self, battle_count: int) -> bool:
        """检查是否满足继续挑战条件"""
        if self.limit_count > 0 and battle_count >= self.limit_count:
            logger.info(f'Reach user limit: {self.limit_count}')
            return False

        # 检查票数
        tickets = self._get_tickets()
        logger.info(f'Current remain tickets: {tickets}')
        if tickets <= 0:
            logger.info('No tickets left, stop task')
            return False

        return True

    def _get_tickets(self) -> int:
        """OCR 识别剩余票数"""
        for _ in range(3):
            self.screenshot()
            cu, res, total = self.O_REMAIN_TICKETS.ocr(self.device.image)
            if cu > 0 or total > 0:
                return cu
            time.sleep(0.2)
        return 0

    def _enter_battle(self):
        """点击挑战按钮进入战斗"""
        click_times, max_times = 0, 5
        from tasks.GlobalGame.assets import GlobalGameAssets
        while True:
            self.check_stop()
            self.screenshot()
            if self.is_in_battle(False):
                return True
            if self.appear(GlobalGameAssets.I_UI_BACK_RED, interval=1):
                logger.warning('Appear red close button, maybe no tickets left')
                raise TaskEnd('AbyssIllusion no tickets')
            if self.appear_then_click(GlobalGameAssets.I_UI_CONFIRM, interval=1):
                continue
            if self.appear_then_click(self.I_CHALLENGE, interval=1.5):
                click_times += 1
                logger.info(f'Try click challenge, remain times[{max_times - click_times}]')
                continue
            if click_times >= max_times:
                logger.warning('Cannot enter battle, click reach max times')
                raise TaskEnd('AbyssIllusion enter battle failed')
            time.sleep(0.3)

    def _ensure_at_page(self, target_page, timeout: int = 30):
        """战斗结束后确保回到目标页面，处理结算、奖励弹窗"""
        time.sleep(1.5)
        timer = Timer(timeout).start()
        from tasks.GlobalGame.assets import GlobalGameAssets
        while not timer.reached():
            self.check_stop()
            self.screenshot()
            if self.ui_reward_appear_click():
                continue
            current = self.get_current_page()
            if current is not None and current.key == target_page.key:
                return True
            if self.appear_then_click(GlobalGameAssets.I_UI_BACK_RED, interval=1):
                continue
            if self.appear_then_click(GlobalGameAssets.I_UI_BACK_YELLOW, interval=1):
                time.sleep(0.5)
                continue
            self.goto_page(target_page)
            time.sleep(0.5)
        logger.warning(f'Ensure at page {target_page.key} timeout')
        return False
