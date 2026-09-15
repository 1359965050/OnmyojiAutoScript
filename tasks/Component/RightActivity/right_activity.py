# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from __future__ import annotations

import time
from typing import Sequence

from module.atom.image import RuleImage
from module.base.timer import Timer
from module.logger import logger
from tasks.Component.RightActivity.assets import RightActivityAssets
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main


class RightActivity(GameUi, RightActivityAssets):
    """通用庭院右侧活动侧边栏组件 (SidebarSwitch)。

    核心功能：
    1. 侧边栏折叠/展开自检与自愈守护 (ensure_sidebar_open / right_open / right_close)；
    2. 侧边栏单次安全翻页切换 (toggle_sidebar)；
    3. 支持单目标/多候选目标的智能寻点与进场 (find_and_click_right_activity / enter_right_activity)；
    4. 供 GameUi / Navigator 页面路由调用的标准化失败 Hook (sidebar_switch_hook)。
    """

    def ensure_sidebar_open(self, timeout: float = 5.0) -> bool:
        """确保右侧侧边栏处于展开状态。

        若检测到侧边栏被收起折叠（出现 I_RA_OPEN），自动点击展开；
        若已展开则立即返回 True。

        Args:
            timeout: 等待展开的最长时间（秒）

        Returns:
            bool: 展开成功返回 True，超时返回 False
        """
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            if not self.appear(self.I_RA_OPEN):
                return True
            logger.info("检测到右侧活动侧边栏处于折叠状态，正在展开...")
            self.appear_then_click(self.I_RA_OPEN, interval=1.2)
            time.sleep(0.5)

        logger.warning(f"右侧活动侧边栏展开超时 ({timeout}s)")
        return False

    def toggle_sidebar(self, interval: float = 1.0) -> bool:
        """执行一次侧边栏翻页切换。

        Returns:
            bool: 成功点击切换按钮返回 True，否则返回 False
        """
        if not self.ensure_sidebar_open():
            return False

        self.screenshot()
        if self.appear(self.I_TOGGLE_BUTTON):
            logger.info("点击侧边栏切换翻页按钮 (I_TOGGLE_BUTTON)")
            clicked = self.appear_then_click(self.I_TOGGLE_BUTTON, interval=interval)
            time.sleep(0.6)  # 翻页旋转微动防抖
            return clicked

        logger.warning("未能在侧边栏找到切换翻页按钮 (I_TOGGLE_BUTTON)")
        return False

    def find_and_click_right_activity(
        self,
        targets: RuleImage | Sequence[RuleImage],
        max_toggles: int = 5,
        interval: float = 1.0,
    ) -> bool:
        """在侧边栏中智能寻找并点击目标活动入口图标。

        支持单个或多个候选图标（如活动有主副图标），若当前页未找到则自动翻页寻找，
        达到最大翻页次数后安全熔断退出，杜绝死循环。

        Args:
            targets: 单个 RuleImage 或 RuleImage 列表/元组
            max_toggles: 最大翻页切换尝试次数，默认 5 次
            interval: 点击间隔（秒）

        Returns:
            bool: 成功找到并点击目标返回 True，未找到返回 False
        """
        if isinstance(targets, RuleImage):
            target_list: list[RuleImage] = [targets]
        else:
            target_list = [t for t in targets if isinstance(t, RuleImage)]

        if not target_list:
            logger.error("find_and_click_right_activity 未提供有效的目标图标")
            return False

        if not self.ensure_sidebar_open():
            return False

        for toggle_idx in range(max_toggles + 1):
            self.screenshot()
            # 优先检测候选目标列表中是否有任何一个可见
            for t in target_list:
                if self.appear(t):
                    target_name = getattr(t, 'name', str(t))
                    logger.info(f"成功定位到右侧活动入口图标: {target_name}，执行点击")
                    self.click(t, interval=interval)
                    return True

            # 当前页未发现目标，尝试翻页
            if toggle_idx < max_toggles:
                if self.appear(self.I_TOGGLE_BUTTON):
                    logger.debug(f"当前页面未发现目标活动，切换侧边栏 ({toggle_idx + 1}/{max_toggles})")
                    self.appear_then_click(self.I_TOGGLE_BUTTON, interval=interval)
                    time.sleep(0.8)  # 等待列表旋转动画完成
                else:
                    logger.debug("翻页按钮不可见，重新检查侧边栏展开状态")
                    self.ensure_sidebar_open(timeout=2.0)

        target_names = [getattr(t, 'name', str(t)) for t in target_list]
        logger.warning(f"侧边栏翻页切换 {max_toggles} 次后，仍未找到目标活动: {target_names}")
        return False

    def enter_right_activity(
        self,
        target: RuleImage | Sequence[RuleImage],
        max_toggles: int = 5,
        timeout: float = 10.0,
    ) -> bool:
        """从庭院进入右侧活动主界面。

        自动导航回庭院主页（若不在庭院），然后智能翻页查找目标并点击，
        最后等待目标入口响应（目标消失或页面离开庭院）。

        Args:
            target: 目标活动图标（支持单个或候选列表）
            max_toggles: 最大翻页尝试次数
            timeout: 等待进场响应超时时间（秒）

        Returns:
            bool: 进入成功返回 True，失败返回 False
        """
        logger.hr("进入右侧活动", 2)
        self.goto_page(page_main)

        clicked = self.find_and_click_right_activity(target, max_toggles=max_toggles)
        if not clicked:
            logger.warning("未能点击右侧活动入口")
            return False

        # 等待进场响应（目标消失或页面发生迁移）
        if isinstance(target, RuleImage):
            target_list = [target]
        else:
            target_list = [t for t in target if isinstance(t, RuleImage)]

        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            # 任何目标依然可见说明还在点击过渡，持续重试消除微延迟
            if not any(self.appear(t) for t in target_list):
                logger.info("右侧活动入口响应成功，已离开入口界面")
                return True
            time.sleep(0.4)

        logger.warning(f"等待右侧活动入口响应超时 ({timeout}s)")
        return False

    def enter(self, target: RuleImage):
        """兼容老版本接口：从庭院进入右侧活动"""
        self.enter_right_activity(target)

    def right_open(self) -> bool:
        """展开右侧活动侧边栏（修复历史逻辑反转）"""
        self.screenshot()
        if not self.appear(self.I_RA_OPEN):
            return True
        return self.ui_click(self.I_RA_OPEN, stop=self.I_RA_CLOSE, interval=1.2, timeout=6.0)

    def right_close(self) -> bool:
        """收起右侧活动侧边栏（修复历史逻辑反转）"""
        self.screenshot()
        if not self.appear(self.I_RA_CLOSE):
            return True
        return self.ui_click(self.I_RA_CLOSE, stop=self.I_RA_OPEN, interval=1.2, timeout=6.0)

    @staticmethod
    def sidebar_switch_hook(task) -> bool:
        """标准化页面路由失败 Hook (供 Page.add_enter_failure_hooks 调用)。

        当从 page_main 进入目标页面因图标在次页而失败时：
        1. 检查侧边栏是否折叠，若折叠则自动展开；
        2. 若出现翻页按钮，则触发一次翻页，为下一次重试准备好页面视图。

        Args:
            task: 当前执行任务实例 (BaseTask / GameUi)

        Returns:
            bool: 是否成功执行了展开或翻页动作
        """
        try:
            task.screenshot()
            if task.appear(RightActivityAssets.I_RA_OPEN):
                logger.info("[Hook] 侧边栏处于折叠状态，执行展开")
                task.appear_then_click(RightActivityAssets.I_RA_OPEN, interval=1.0)
                return True
            if task.appear(RightActivityAssets.I_TOGGLE_BUTTON):
                logger.info("[Hook] 未发现目标活动入口，执行侧边栏翻页切换")
                return task.appear_then_click(RightActivityAssets.I_TOGGLE_BUTTON, interval=1.0)
        except Exception as err:
            logger.warning(f"[Hook] 侧边栏切换 Hook 异常: {err}")
        return False


# 语义别名，增强可读性
SidebarSwitch = RightActivity
