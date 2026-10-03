# This Python file uses the following encoding: utf-8
# @author runhey
import time
from datetime import datetime, timedelta
from typing import Optional

from module.base.timer import Timer
from module.exception import TaskEnd
from module.logger import logger

from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.RightActivity.right_activity import RightActivity
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.BaseActivity.assets import BaseActivityAssets
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.AbyssIllusion.assets import AbyssIllusionAssets
from tasks.AbyssIllusion.config import AbyssIllusion
from tasks.AbyssIllusion.page import create_abyss_illusion_pages
from tasks.base_task import BaseTask


class ScriptTask(GeneralBattle, RightActivity, SwitchSoul, AbyssIllusionAssets):
    """狭间幻境限时活动任务"""

    limit_count: int = 0

    def run(self):
        cfg: AbyssIllusion = self.config.abyss_illusion
        self.limit_count = cfg.abyss_illusion_config.limit_count

        # 1. 先注册页面，保证断点续跑时（停留在活动总览/伊吹之擂）当前页可被识别
        self.pages = create_abyss_illusion_pages(self.navigator)

        # 2. 强制刷新首帧：避免复用上一任务残留的陈旧截图，导致首次页面识别全部 miss
        self.screenshot()

        # 3. 换御魂（未启用时不导航，保留断点现场）
        self._switch_soul(cfg.switch_soul_config)

        # 4. 导航到活动页面（navigator 依据当前所在页自动选择最短路径，支持断点续跑）
        self.goto_page(self.pages['page_act'], skip_first_screenshot=False)
        self.goto_page(self.pages['page_abyss_illusion'], skip_first_screenshot=False)

        # 5. 循环战斗
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

        # 6. 收尾
        self.goto_page(page_main)
        self.set_next_run(task='AbyssIllusion', success=True, finish=True)
        raise TaskEnd('AbyssIllusion')

    def _switch_soul(self, switch_soul_config):
        """根据配置切换御魂。

        未启用换御魂时不做任何导航，从而保留断点续跑现场（停留在活动总览/伊吹之擂）。
        """
        switched = False
        if switch_soul_config.enable:
            self.get_current_page()
            self.goto_page(page_shikigami_records)
            self.run_switch_soul(switch_soul_config.switch_group_team)
            switched = True
        if switch_soul_config.enable_switch_by_name:
            self.get_current_page()
            self.goto_page(page_shikigami_records)
            self.run_switch_soul_by_name(
                switch_soul_config.group_name,
                switch_soul_config.team_name
            )
            switched = True
        if switched:
            self.get_current_page()
            self.goto_page(page_main)

    # ------------------------------------------------------------------
    # 活动总览寻径（庭院 -> 活动总览 -> 滑屏找伊吹之擂 -> 前往活动）
    # ------------------------------------------------------------------
    def enter_ibuki_via_overview(self, timeout: float = 20.0) -> bool:
        """通过常驻『活动总览』免更寻径进入『伊吹之擂』主界面。

        阶段划分：
            0. 幂等自检：若已在伊吹之擂主界面（I_CHECK_ACT_MAIN）直接返回；
            1. 进入活动总览：展开右侧栏并点击常驻『活动』图标；
            2. 滑屏寻找：在左侧活动列表向上滑动翻出『伊吹之擂』并点击（max_swipes 熔断）；
            3. 点击『前往活动』；
            4. 确认进场：轮询 I_CHECK_ACT_MAIN。

        Args:
            timeout: 总超时时间（秒），默认 20 秒。

        Returns:
            bool: 成功进入伊吹之擂主界面返回 True，否则返回 False。
        """
        logger.hr("开始执行活动总览寻径进入伊吹之擂", 2)

        # 阶段 0：幂等自检，避免断点续跑时重复寻径
        self.screenshot()
        if self.appear(self.I_CHECK_ACT_MAIN):
            logger.info("当前已处于伊吹之擂主界面，无需重复寻径")
            return True

        # 阶段 1：确保处于『活动总览』界面
        if self.ocr_appear(BaseActivityAssets.O_OVERVIEW_TITLE):
            logger.info("当前已处于『活动总览』界面，跳过庭院入场")
        else:
            if not self.ensure_sidebar_open(timeout=min(6.0, timeout)):
                logger.warning("展开庭院右侧活动侧边栏超时")
                return False
            if not self._step_click_sidebar_activity(timeout=min(6.0, timeout)):
                logger.warning("未能点击庭院侧边栏『活动』图标")
                return False
            if not self._step_wait_activity_overview(timeout=min(6.0, timeout)):
                logger.warning("未能进入『活动总览』界面")
                return False

        # 阶段 2：滑屏寻找『伊吹之擂』选项卡
        if not self._step_swipe_find_ibuki(max_swipes=4, timeout=min(8.0, timeout)):
            logger.warning("滑屏 4 次仍未定位到『伊吹之擂』选项卡")
            return False

        # 阶段 3：点击右下角『前往活动』
        if not self._step_click_goto_activity(timeout=min(5.0, timeout)):
            logger.warning("未能点击『前往活动』按钮")
            return False

        # 阶段 4：确认进入伊吹之擂主界面
        if not self._step_wait_ibuki_main(timeout=min(7.0, timeout)):
            logger.warning("未能确认进入伊吹之擂主界面")
            return False

        logger.info("已成功通过活动总览寻径进入伊吹之擂")
        return True

    def _step_click_sidebar_activity(self, timeout: float = 6.0) -> bool:
        """展开庭院右侧栏并点击常驻『活动』图标，进入『活动总览』。"""
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            # 1. 优先模板匹配常驻『活动』图标
            if self.appear_then_click(GameUiAssets.I_ACT_LIST_EXPAND, interval=1.0):
                logger.info("检测到庭院侧边栏『活动』图标 (模板匹配)，正在点击")
                time.sleep(0.6)
                return True
            # 2. OCR 回退：识别『活动』文字并点击
            if self.ocr_appear_click(BaseActivityAssets.O_SIDEBAR_ACTIVITY, interval=1.0):
                logger.info("OCR 识别到庭院侧边栏『活动』图标并点击")
                time.sleep(0.6)
                return True
            time.sleep(0.3)
        return False

    def _step_wait_activity_overview(self, timeout: float = 6.0) -> bool:
        """轮询等待进入『活动总览』界面。"""
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            if self.ocr_appear(BaseActivityAssets.O_OVERVIEW_TITLE):
                logger.info("成功确认进入『活动总览』界面")
                return True
            time.sleep(0.4)
        return False

    def _step_swipe_find_ibuki(self, max_swipes: int = 4, timeout: float = 8.0) -> bool:
        """在『活动总览』左侧列表向上滑屏，翻出并点击『伊吹之擂』选项卡。

        Args:
            max_swipes: 最大滑动次数（死锁熔断上限）。
            timeout: 该阶段总超时时间（秒）。
        """
        timer = Timer(timeout).start()
        for swipe_idx in range(max_swipes + 1):
            if timer.reached():
                logger.warning("滑屏寻找『伊吹之擂』总超时")
                return False
            self.screenshot()
            # 命中：OCR 定位『伊吹之擂』文字区域并点击（Full 模式 coord 落在匹配框内）
            if self.ocr_appear_click(self.O_ACT_LIST_IBUKI, interval=1.0):
                logger.info("已定位并点击『伊吹之擂』选项卡")
                time.sleep(0.8)  # 等待右侧活动面板刷新稳定
                return True
            # 未命中：向上滑动翻页（滑到底部仍未命中则由 max_swipes 熔断）
            if swipe_idx < max_swipes:
                logger.info(f"未发现『伊吹之擂』，向上滑动列表 ({swipe_idx + 1}/{max_swipes})")
                self.swipe(self.S_SWIPE_LIST_UP)
                time.sleep(0.6)  # 滑动动效静止防抖
        logger.warning(f"滑屏 {max_swipes} 次后仍未找到『伊吹之擂』选项卡")
        return False

    def _step_click_goto_activity(self, timeout: float = 5.0) -> bool:
        """点击『活动总览』右下角『前往活动』按钮。"""
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            # 1. 优先 OCR 识别『前往活动』
            if self.ocr_appear_click(BaseActivityAssets.O_OVERVIEW_GOTO_ACT, interval=1.0):
                logger.info("检测到并点击『前往活动』按钮 (OCR)")
                time.sleep(1.0)  # 预留场景转场过渡
                return True
            # 2. 模板匹配回退
            if self.appear_then_click(GameUiAssets.I_ACT_LIST_GOTO_ACT, interval=1.0):
                logger.info("检测到并点击『前往活动』按钮 (模板匹配)")
                time.sleep(1.0)
                return True
            # 3. 固定区域兜底
            if self.click(BaseActivityAssets.C_OVERVIEW_GOTO_ACT, interval=1.0):
                logger.info("通过预设区域 C_OVERVIEW_GOTO_ACT 点击『前往活动』")
                time.sleep(1.0)
                return True
            time.sleep(0.3)
        return False

    def _step_wait_ibuki_main(self, timeout: float = 7.0) -> bool:
        """轮询确认已进入『伊吹之擂』主界面。"""
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            if self.appear(self.I_CHECK_ACT_MAIN):
                logger.info("检测到活动主界面特征，确认已进入伊吹之擂")
                return True
            time.sleep(0.4)
        return False

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

    def _enter_battle(self, timeout: float = 30.0):
        """点击挑战按钮进入战斗。

        盲点熔断（skill.md §3.2）：除点击次数上限 max_times 外，额外设置总超时，
        杜绝挑战按钮识别失败时的无响应死循环。
        """
        click_times, max_times = 0, 5
        from tasks.GlobalGame.assets import GlobalGameAssets
        timer = Timer(timeout).start()
        while not timer.reached():
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
                if click_times >= max_times:
                    logger.warning('Cannot enter battle, click reach max times')
                    raise TaskEnd('AbyssIllusion enter battle failed')
                continue
            time.sleep(0.3)
        logger.warning(f'Cannot enter battle, timeout({timeout}s)')
        raise TaskEnd('AbyssIllusion enter battle timeout')

    def _ensure_at_page(self, target_page, timeout: int = 30):
        """战斗结束后确保回到目标页面，处理结算、奖励弹窗"""
        time.sleep(1.5)
        timer = Timer(timeout).start()
        from tasks.GlobalGame.assets import GlobalGameAssets
        while not timer.reached():
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
