# This Python file uses the following encoding: utf-8
from __future__ import annotations

import random
import time
from datetime import datetime
from functools import cached_property
from typing import Callable, Optional, Sequence

from module.atom.click import RuleClick
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr, OcrMode
from module.base.protect import random_sleep
from module.base.timer import Timer
from module.logger import logger
from tasks.Component.BaseActivity.assets import BaseActivityAssets
from tasks.Component.BaseActivity.exceptions import LimitCountOut, LimitTimeOut, TicketsNotEnough
from tasks.Component.BuyWindow.buy_window import BuyWindow
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.GeneralBattle.general_battle import ExitMatcher, GeneralBattle
from tasks.Component.RightActivity import RightActivity
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.UsedTicketsCount.used_tickets_count import UsedTicketsCount
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import Page, page_main
from tasks.GlobalGame.assets import GlobalGameAssets


class BaseActivity(GeneralBattle, RightActivity, SwitchSoul, UsedTicketsCount, BuyWindow, BaseActivityAssets):
    """通用活动爬塔基类组件。

    设计职责：
    1. 连通独立原子组件：
       - RightActivity（右侧活动侧边栏自检、翻页切换与智能寻点独立组件）
       - BuyWindow（购买弹窗识别与安全关闭独立组件，门票耗尽直切）
       - UsedTicketsCount（已使用门票计数独立组件，精准记录应用运行使用次数）
       - SwitchSoul（御魂切换独立组件）
       - GeneralBattle（通用战斗独立组件）
       - GameUi / Navigator（界面导航独立组件）
    2. 提供通用爬塔自动化流水线：
       - 多模式按序轮转 (pass -> ap -> ap100 -> boss)
       - 挑战前余票校验与应用限额检查
       - 智能阵容锁定与御魂自适应切换
       - 战斗进入与结果处理闭环
       - 超时、限额与防卡屏死锁熔断保护
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_climb_type: str = 'pass'
        self._switch_souled_map: dict[str, bool] = {}

    @property
    def current_climb_type(self) -> str:
        """当前正在执行的爬塔模式类型。"""
        return getattr(self, '_current_climb_type', 'pass')

    @current_climb_type.setter
    def current_climb_type(self, value: str):
        self._current_climb_type = str(value).strip()

    def before_run(self):
        """活动执行前的预处理钩子，子类可覆写扩展。"""
        pass

    def get_current_climb_mode(self, image=None) -> Optional[str]:
        """自适应判断当前游戏界面处于哪个爬塔消耗模式 ('pass' 或 'ap')。

        判断逻辑：
        1. 优先兼容特定活动的专有图标规则（若定义了 I_CLIMB_MODE_AP / I_CLIMB_MODE_PASS）；
        2. 爬塔房间环境前置校验：
           必须确认处于爬塔房间（具备阵容锁定锁图标或右下角挑战火/文字特征），
           避免在活动大厅、庭院或地图等背景误判。
        3. 自适应模式胶囊检测：
           - 现代爬塔活动（挑战按钮上方胶囊 x: 1110~1265, y: 540~585）：
             * 切换图标检测：(1215, 542, 45, 36) 区域存在 ⇄ 双向箭头高亮图标；
             * 消耗图标特征：(1115, 542, 45, 36) 区域进行寿司橙红鱼子色彩分析：
               - 若存在高饱和橙红色鱼子 (H: 6~13, S>=160, V>=150) 像素达阈值 (>=15)，判定为 'ap' (寿司体力消耗)；
               - 若无鱼子橙红特征（为暗色/金色门票卡片），判定为 'pass' (活动门票消耗)。
           - 传统双态水平胶囊兜底：在 (845, 555, 145, 45) 分析左右两半高亮亮度。

        Args:
            image: 目标图像，默认使用 self.device.image

        Returns:
            Optional[str]: 'ap' (体力模式)、'pass' (门票模式)，若无法确定返回 None
        """
        # 1. 专有切图规则兼容
        if hasattr(self, 'I_CLIMB_MODE_AP') and self.appear(self.I_CLIMB_MODE_AP):
            return 'ap'
        if hasattr(self, 'I_CLIMB_MODE_PASS') and self.appear(self.I_CLIMB_MODE_PASS):
            return 'pass'

        # 2. 图像获取
        if image is None:
            image = getattr(self.device, 'image', None)
        if image is None:
            return None

        import cv2
        import numpy as np

        # 3. 爬塔房间环境前置校验 (设置 1.2s CD 缓存机制)：
        # 必须确认处于爬塔房间（具备右下角挑战火/文字特征，或阵容锁定/解锁图标），
        # 严格排除在庭院（右下角为式神录）、活动大厅或中转地图等非房间界面误判。
        now = time.time()
        last_check = getattr(self, '_room_env_last_time', 0.0)
        if (now - last_check < 1.2) and hasattr(self, '_room_env_last_result'):
            is_in_room = self._room_env_last_result
        else:
            from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
            is_in_room = bool(self.appear(ActivityShikigamiAssets.I_LOCK) or self.appear(ActivityShikigamiAssets.I_UNLOCK))
            if not is_in_room:
                is_in_room = bool(
                    (hasattr(self, 'I_ACT_FIRE') and self.appear(self.I_ACT_FIRE))
                    or (hasattr(self, 'I_CLIMB_FIRE') and self.appear(self.I_CLIMB_FIRE))
                    or (hasattr(self, 'O_GENERIC_FIRE') and self.ocr_appear(self.O_GENERIC_FIRE))
                )
            self._room_env_last_time = now
            self._room_env_last_result = is_in_room

        if not is_in_room:
            return None

        # 4. 胶囊区域消耗数字权威 OCR 区分凭证：
        # 体力爬塔模式消耗固定为 6 点体力，右下角展示：寿司 + ×6 + 灵符 + ×1 + ⇄
        # 活动门票模式消耗固定为 1 张门票，右下角展示：门票 + ×1 + ⇄
        # 因此右下角 OCR 识别结果：
        # - 出现 '6' (如 '×6'、'x6'、'6')：100% 判定为体力模式 ('ap')
        # - 出现 '1' (如 '×1'、'x1'、'1') 且无 '6'：100% 判定为活动门票模式 ('pass')
        if hasattr(self, 'O_GENERIC_FIRE'):
            try:
                ocr_results = self.O_GENERIC_FIRE.detect_and_ocr(image, logDisplay=False)
                all_text = ''.join([r.ocr_text for r in ocr_results])
                if '6' in all_text:
                    return 'ap'
                elif '1' in all_text:
                    return 'pass'
            except Exception:
                pass

        # 5. 现代爬塔切换按键检测 (1210, 535, 55, 50)
        switch_crop = image[535:585, 1210:1265]
        has_switch = False
        if switch_crop.size > 0:
            gray_switch = cv2.cvtColor(switch_crop, cv2.COLOR_BGR2GRAY) if len(switch_crop.shape) == 3 else switch_crop
            # ⇄ 切换图标由白色高亮像素构成 (>175)
            has_switch = bool(np.sum(gray_switch > 175) >= 20)

        # 6. 胶囊区域自适应视觉分析兜底
        # A. 现代爬塔活动视觉分析：检测消耗图标区域 (1070, 535, 95, 45) 的寿司鱼子橙红特征
        if has_switch:
            icon_crop = image[535:580, 1070:1165]
            if icon_crop.size > 0:
                hsv = cv2.cvtColor(icon_crop, cv2.COLOR_BGR2HSV)
                roe_mask = (hsv[:, :, 0] >= 5) & (hsv[:, :, 0] <= 14) & (hsv[:, :, 1] >= 140) & (hsv[:, :, 2] >= 130)
                roe_pixels = int(np.sum(roe_mask))
                if roe_pixels >= 15:
                    return 'ap'
            return 'pass'

        # B. 传统双态水平胶囊兜底分析 (845, 555, 145, 45)
        x, y, w, h = 845, 555, 145, 45
        crop = image[y:y+h, x:x+w]
        if crop.size > 0:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
            mid_x = w // 2
            left_brightness = float(np.mean(gray[:, :mid_x]))
            right_brightness = float(np.mean(gray[:, mid_x:]))

            if left_brightness > right_brightness + 10:
                return 'ap'
            elif right_brightness > left_brightness + 10:
                return 'pass'

        return None

    def is_climb_mode_ap(self) -> bool:
        """判定当前是否处于体力爬塔模式。"""
        return self.get_current_climb_mode() == 'ap'

    def is_climb_mode_pass(self) -> bool:
        """判定当前是否处于门票爬塔模式。"""
        return self.get_current_climb_mode() == 'pass'

    def toggle_climb_mode(self, task_or_interval=None, interval: float = 1.5) -> bool:
        """点击模式切换胶囊按钮进行体力与门票模式互相切换（默认等待 1.5s 动画完成）。"""
        if isinstance(task_or_interval, (int, float)):
            interval = float(task_or_interval)
        elif not isinstance(interval, (int, float)):
            interval = 1.5

        # 优先使用专有切换按钮（若有）
        if hasattr(self, 'I_CLIMB_MODE_SWITCH') and self.appear(self.I_CLIMB_MODE_SWITCH):
            res = self.appear_then_click(self.I_CLIMB_MODE_SWITCH, interval=interval)
            time.sleep(1.5)
            return res

        # 默认点击通用切换按键区域 (1220, 545, 38, 30)
        self.click(self.C_GENERIC_MODE_SWITCH, interval=interval)
        time.sleep(1.5)
        return True

    def ensure_climb_mode(self, target_mode: str, max_retries: int = 3) -> bool:
        """自适应确保当前界面处于目标爬塔模式 ('pass' 或 'ap')。

        若当前模式与目标模式不符，自动触发切换并复验，具备重试熔断。

        Args:
            target_mode: 目标模式 ('pass' 或 'ap')
            max_retries: 最大尝试切换次数

        Returns:
            bool: 最终是否成功匹配目标模式
        """
        if target_mode not in ('pass', 'ap'):
            return True

        for i in range(max_retries):
            self.screenshot()
            current = self.get_current_climb_mode()
            if current == target_mode:
                logger.info(f"爬塔模式匹配就绪: [{target_mode}]")
                return True

            if current is not None:
                logger.info(f"当前爬塔模式为 [{current}]，正在切换至目标模式 [{target_mode}] (尝试第 {i+1}/{max_retries} 次)...")
                self.toggle_climb_mode(interval=1.5)
            else:
                logger.debug(f"未明确识别到当前模式，尝试点击切换至 [{target_mode}]...")
                self.toggle_climb_mode(interval=1.5)
                self.screenshot()
                if self.get_current_climb_mode() == target_mode:
                    logger.info(f"爬塔模式匹配就绪: [{target_mode}]")
                    return True
                break

        return False

    @staticmethod
    def get_climb_type_display_name(climb_type: str) -> str:
        """将爬塔英文标识转换为友好的中文展示名称。"""
        mapping = {
            'pass': '门票爬塔',
            'ap': '体力爬塔',
            'ap100': '100体爬塔',
            'boss': '首领挑战',
        }
        return mapping.get(str(climb_type).lower(), str(climb_type))

    def get_climb_target_limit(self, climb_type: str) -> int:
        """获取指定爬塔类型的配置运行限额。"""
        conf_obj = getattr(self.config.model, 'activity_shikigami', None)
        if conf_obj and hasattr(conf_obj, 'general_climb'):
            return getattr(conf_obj.general_climb, f'{climb_type}_limit', 0)
        return 0

    def check_activity_timeout(self):
        """检查全局活动是否达到总运行时间限制。"""
        conf_obj = getattr(self.config.model, 'activity_shikigami', None)
        if not conf_obj or not hasattr(conf_obj, 'general_climb'):
            return
        limit_time_v = conf_obj.general_climb.limit_time_v
        if datetime.now() - self.start_time >= limit_time_v:
            logger.info(f"活动爬塔总运行时间达到上限 ({limit_time_v})")
            raise LimitTimeOut

    def check_activity_limit(self, climb_type: str):
        """检查当前模式的应用运行使用次数是否达到配置限额。"""
        target_limit = self.get_climb_target_limit(climb_type)
        if self.is_app_limit_reached(climb_type, target_limit):
            raise LimitCountOut

    def switch_soul_for_climb(self, climb_type: str, enter_button: RuleImage, check_image: RuleImage):
        """为当前爬塔模式执行御魂切换（同一模式单次会话只切换一次）。

        Args:
            climb_type: 爬塔类型
            enter_button: 进入阵容/记录界面的按钮规则
            check_image: 阵容记录界面识别标志
        """
        if self._switch_souled_map.get(climb_type, False):
            return

        conf_obj = getattr(self.config.model, 'activity_shikigami', None)
        if not conf_obj or not hasattr(conf_obj, 'switch_soul_config'):
            return

        conf = conf_obj.switch_soul_config
        enable_switch = getattr(conf, f"enable_switch_{climb_type}", False)
        enable_by_name = getattr(conf, f"enable_switch_{climb_type}_by_name", False)
        if not enable_switch and not enable_by_name:
            self._switch_souled_map[climb_type] = True
            return

        climb_name = self.get_climb_type_display_name(climb_type)
        logger.hr(f'开始切换御魂: {climb_name}', 2)
        conf.validate_switch_soul()
        self.ui_click(enter_button, stop=check_image, interval=1.2)
        if enable_by_name:
            name_val = getattr(conf, f"{climb_type}_group_team_name", "")
            group, team = name_val.split(",")
            self.run_switch_soul_by_name(group.strip(), team.strip())
        elif enable_switch:
            group_team = getattr(conf, f"{climb_type}_group_team")
            self.run_switch_soul(group_team)

        self._switch_souled_map[climb_type] = True

    def lock_team(self, battle_conf: GeneralBattleConfig):
        """阵容锁定/解锁处理，子类根据各模式实际 UI 资产覆写或注入。"""
        pass

    def _exit_matcher(self) -> ExitMatcher | None:
        """默认以右下角通用挑战 OCR 作为战斗结算回房识别条件。"""
        return self.O_GENERIC_FIRE

    def find_fire_button(
        self,
        fire_ocr: Optional[RuleOcr] = None,
        candidates: Optional[Sequence[RuleOcr]] = None,
    ) -> Optional[tuple[int, int]]:
        """在右下角区域 (1073, 515, 199, 196) 自适应定位挑战按钮坐标。

        Args:
            fire_ocr: 显式指定的专用 RuleOcr 规则（若提供则优先使用）
            candidates: 自定义候选规则列表，默认为内置通用候选规则序列

        Returns:
            Optional[tuple[int, int]]: 命中的点击物理坐标 (x, y)，若未找到返回 None
        """
        if fire_ocr is not None and self.ocr_appear(fire_ocr):
            return fire_ocr.coord()

        rules = candidates if candidates is not None else (
            self.O_GENERIC_FIRE,
            self.O_GENERIC_FIRE_START,
            self.O_GENERIC_FIRE_ATTACK,
            self.O_GENERIC_FIRE_BATTLE,
            self.O_GENERIC_FIRE_CHAR,
        )
        for rule in rules:
            if rule and self.ocr_appear(rule):
                return rule.coord()

        return None

    def click_fire_button(
        self,
        fire_ocr: Optional[RuleOcr] = None,
        interval: float = 1.2,
    ) -> bool:
        """自适应识别并点击挑战按钮，具备优先匹配与全候选兜底。

        Args:
            fire_ocr: 可选的专用 RuleOcr 规则
            interval: 触发间隔保护（秒）

        Returns:
            bool: 是否成功找到并点击
        """
        if fire_ocr is not None and self.ocr_appear_click(fire_ocr, interval=interval):
            return True

        for rule in (
            self.O_GENERIC_FIRE,
            self.O_GENERIC_FIRE_START,
            self.O_GENERIC_FIRE_ATTACK,
            self.O_GENERIC_FIRE_BATTLE,
            self.O_GENERIC_FIRE_CHAR,
        ):
            if rule and self.ocr_appear_click(rule, interval=interval):
                return True

        return False

    def enter_battle_generic(
        self,
        fire_ocr: Optional[RuleOcr] = None,
        confirm_image: Optional[RuleImage] = None,
        confirm_small_image: Optional[RuleImage] = None,
        no_tickets_image: Optional[RuleImage] = None,
        max_clicks: int = 5,
    ) -> bool:
        """通用的点击挑战进入战斗流程，具备自适应识别、超时与盲点熔断防护。

        Args:
            fire_ocr: 挑战 OCR 规则，为 None 时使用右下角通用 OCR 识别 (1073, 515, 199, 196)
            confirm_image: 大确认按钮规则，默认使用 GlobalGameAssets.I_UI_CONFIRM
            confirm_small_image: 小确认按钮规则，默认使用 GlobalGameAssets.I_UI_CONFIRM_SAMLL
            no_tickets_image: 门票不足/红色弹窗标志，默认使用 GlobalGameAssets.I_UI_BACK_RED
            max_clicks: 最大连续点击挑战尝试次数

        Returns:
            bool: True 表示成功进入战斗，若次数耗尽或弹出无票弹窗则抛出 TicketsNotEnough
        """
        c_confirm = confirm_image if confirm_image is not None else GlobalGameAssets.I_UI_CONFIRM
        c_confirm_small = confirm_small_image if confirm_small_image is not None else GlobalGameAssets.I_UI_CONFIRM_SAMLL
        c_no_tickets = no_tickets_image if no_tickets_image is not None else GlobalGameAssets.I_UI_BACK_RED

        click_times = 0
        while True:
            self.screenshot()
            if self.is_in_battle(False):
                return True

            # 门票不足购买弹窗前置检测：若已弹出购买弹窗，绝不重试，直接关闭并切换
            if self.is_ticket_buy_window():
                self.handle_ticket_buy_window(self.current_climb_type)

            if click_times >= max_clicks:
                logger.warning(f"[{self.current_climb_type}] 点击挑战达到上限 [{max_clicks}] 次，可能无法进入战斗")
                raise TicketsNotEnough

            if c_no_tickets and self.appear(c_no_tickets, interval=1):
                logger.warning(f"[{self.current_climb_type}] 出现关闭/资源不足标志，判定门票耗尽")
                raise TicketsNotEnough

            if self.appear_then_click(c_confirm_small, interval=1) or \
               self.appear_then_click(c_confirm, interval=1):
                time.sleep(0.8)
                continue

            # OCR 识别挑战按钮前预留 0.3 秒缓冲等待，确保动态光效稳定
            time.sleep(0.3)
            if self.click_fire_button(fire_ocr, interval=1.2):
                self.device.click_record_clear()
                click_times += 1
                if click_times == 1:
                    logger.info(f"[{self.current_climb_type}] 点击挑战，等待进入战斗...")
                else:
                    logger.warning(
                        f"[{self.current_climb_type}] 未检测到进入战斗，第 {click_times} 次重试点击挑战 (剩余尝试次数 [{max_clicks - click_times}])"
                    )

                # 进场过渡等待：轮询检测战斗是否就绪（最多等待 3s，每 0.5s 检查一次）
                for _ in range(6):
                    time.sleep(0.5)
                    self.screenshot()
                    if self.is_in_battle(False):
                        return True
                    # 优先检测是否由于门票不足弹出购买弹窗，一旦发现立刻阻断重试并直接切换模式
                    if self.is_ticket_buy_window():
                        self.handle_ticket_buy_window(self.current_climb_type)
                    if self.appear_then_click(c_confirm_small, interval=0.5) or \
                       self.appear_then_click(c_confirm, interval=0.5):
                        continue
                    if c_no_tickets and self.appear(c_no_tickets, interval=0.5):
                        logger.warning(f"[{self.current_climb_type}] 出现关闭/资源不足标志，判定门票耗尽")
                        raise TicketsNotEnough

                continue

    def execute_climb_round(
        self,
        climb_type: str,
        ticket_ocr: Optional[RuleOcr] = None,
        battle_conf: Optional[GeneralBattleConfig] = None,
        fire_ocr: Optional[RuleOcr] = None,
        confirm_image: Optional[RuleImage] = None,
        confirm_small_image: Optional[RuleImage] = None,
        no_tickets_image: Optional[RuleImage] = None,
        soul_records_button: Optional[RuleImage] = None,
        soul_records_check: Optional[RuleImage] = None,
        random_sleep_enabled: bool = False,
    ):
        """执行单轮爬塔流程：余票检查 -> 换御魂 -> 自适应点击进入 -> 通用战斗 -> 应用门票计数递增。"""
        # 0. 轮次开始前等待 0.5 秒，确保刚退出战斗结算转场后房间 UI 与顶栏彻底稳定
        time.sleep(0.5)

        # 0. 防卡屏检测：如果意外处于购买弹窗中，立即关闭并切换模式
        if self.is_ticket_buy_window():
            self.handle_ticket_buy_window(climb_type)

        # 1. 检查游戏内门票是否足够
        if not self.check_game_tickets_available(climb_type, ticket_ocr):
            logger.warning(f"[{climb_type}] 游戏内门票不足，退出该模式")
            raise TicketsNotEnough

        # 2. 检查应用运行使用次数是否已达限额
        target_limit = self.get_climb_target_limit(climb_type)
        if self.is_app_limit_reached(climb_type, target_limit):
            raise LimitCountOut

        # 3. 换御魂
        if soul_records_button and soul_records_check:
            self.switch_soul_for_climb(climb_type, soul_records_button, soul_records_check)

        # 4. 拟人化随机等待
        if random_sleep_enabled:
            random_sleep(probability=0.2)

        # 5. 点击挑战进入战斗
        if self.enter_battle_generic(
            fire_ocr=fire_ocr,
            confirm_image=confirm_image,
            confirm_small_image=confirm_small_image,
            no_tickets_image=no_tickets_image,
        ):
            # 6. 执行通用战斗并处理结算
            if battle_conf is None:
                conf_obj = getattr(self.config.model, 'activity_shikigami', None)
                battle_conf = getattr(conf_obj, f'{climb_type}_battle_conf', None) if conf_obj else None
                if battle_conf is None:
                    battle_conf = GeneralBattleConfig()

            self.run_general_battle(battle_conf, battle_key=f"act_{climb_type}")
            # 7. 战斗完成，应用实际使用门票次数精确 +1
            self.record_ticket_used(climb_type, count=1, target_limit=target_limit)
            # 8. 校验是否达到目标限额
            if self.is_app_limit_reached(climb_type, target_limit):
                raise LimitCountOut

    def enter_activity_via_overview(self, timeout: float = 15.0) -> bool:
        """通过常驻的『庭院活动图标 -> 活动总览 -> 版本活动 -> 前往活动』通用免更流水线进入当期活动主界面。

        核心优势：
        1. 路径中所有图标与文字均为官方常驻系统组件，彻底消除随版本更换立绘与艺术字所带来的维护痛点；
        2. 自带多态兼容：若已经在活动主界面则快速透传，若在活动总览中则自动续跑，若在庭院则自启侧边栏寻找；
        3. 多级熔断与防抖：侧边栏自动展开、自动翻页重试、多帧稳定判定。

        Args:
            timeout: 总超时时间（秒），默认 15 秒。

        Returns:
            bool: 成功进入当期活动主界面返回 True，失败返回 False。
        """
        logger.hr("开始执行活动总览通用免更寻径入场", 2)
        start_timer = Timer(timeout).start()

        # 0. 快速检测：若当前已经在活动主界面，直接返回成功
        self.screenshot()
        if self._is_in_activity_main_page():
            logger.info("当前已处于活动主界面，无需重复寻径")
            return True

        # 0.1 若当前已经在活动总览界面，则直接跳到选项卡与前往步骤
        if not self._is_in_activity_overview():
            # 阶段 1：展开庭院侧边栏并点击“活动”图标
            if not self._step_click_sidebar_activity(timeout=min(6.0, timeout)):
                logger.warning("未能成功点击庭院侧边栏『活动』图标")
                return False

            # 阶段 2：等待进入『活动总览』界面
            if not self._step_wait_activity_overview(timeout=min(6.0, timeout)):
                logger.warning("未能成功进入『活动总览』界面")
                return False

        # 阶段 3：确保选中左侧『版本活动』选项卡
        if not self._step_select_version_activity(timeout=min(5.0, timeout)):
            logger.warning("未能在活动总览中定位/选中『版本活动』选项卡")
            return False

        # 阶段 4：点击右下角『前往活动』按钮
        if not self._step_click_goto_activity(timeout=min(5.0, timeout)):
            logger.warning("未能在活动总览中点击『前往活动』按钮")
            return False

        # 阶段 5：确认离开活动总览并成功进入当期活动主界面
        if not self._step_confirm_entered_activity(timeout=min(7.0, timeout)):
            logger.warning("未能确认成功进入当期活动主界面")
            return False

        logger.info("通用免更寻径成功：已到达当期活动主界面！")
        return True

    def _is_in_activity_overview(self) -> bool:
        """判断当前是否正处于『活动总览』界面（仅需依据顶部常驻标题即可精确判定）。"""
        return bool(self.ocr_appear(self.O_OVERVIEW_TITLE))

    def _is_in_activity_main_page(self) -> bool:
        """判断当前是否已脱离庭院与活动总览，处于活动主界面（有黄色返回键且非总览、非庭院）。"""
        has_yellow_back = self.appear(GlobalGameAssets.I_UI_BACK_YELLOW)
        if not has_yellow_back:
            return False
        # 如果有黄色返回键，但同时还在活动总览，则不是活动主界面
        if self._is_in_activity_overview():
            return False
        return True

    def _step_click_sidebar_activity(self, timeout: float = 6.0) -> bool:
        """展开庭院侧边栏并点击常驻『活动』图标。"""
        if not self.ensure_sidebar_open(timeout=timeout):
            logger.warning("展开庭院侧边栏超时")
            return False

        timer = Timer(timeout).start()
        toggled = False
        while not timer.reached():
            self.screenshot()
            # 1. 优先模板匹配：GameUiAssets.I_ACT_LIST_EXPAND
            if self.appear(GameUiAssets.I_ACT_LIST_EXPAND):
                logger.info("检测到庭院侧边栏『活动』图标 (模板匹配)，正在点击...")
                self.appear_then_click(GameUiAssets.I_ACT_LIST_EXPAND, interval=1.0)
                time.sleep(0.5)
                return True

            # 2. OCR 智能回退：O_SIDEBAR_ACTIVITY ("活动") - 单次识别并点击
            if self.ocr_appear_click(self.O_SIDEBAR_ACTIVITY, interval=1.0):
                logger.info("检测到庭院侧边栏『活动』图标 (OCR) 并点击")
                time.sleep(0.5)
                return True

            # 3. 兜底点击安全区域 C_SIDEBAR_ACTIVITY
            if self.click(self.C_SIDEBAR_ACTIVITY, interval=1.5):
                logger.info("尝试点击侧边栏『活动』图标预设区域 (C_SIDEBAR_ACTIVITY)")
                time.sleep(0.5)
                return True

            # 4. 若第一页未发现且尚未翻页，尝试翻页一次
            if not toggled and self.appear(self.I_TOGGLE_BUTTON):
                logger.info("侧边栏当前页未发现活动图标，尝试翻页...")
                self.toggle_sidebar()
                toggled = True
                time.sleep(0.5)
            else:
                time.sleep(0.3)

        return False

    def _step_wait_activity_overview(self, timeout: float = 6.0) -> bool:
        """等待并确认进入『活动总览』界面。"""
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            if self._is_in_activity_overview():
                logger.info("成功确认进入『活动总览』界面")
                return True
            time.sleep(0.4)
        return False

    def _step_select_version_activity(self, timeout: float = 5.0) -> bool:
        """确保选中活动总览左侧的『版本活动』选项卡。"""
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            # 单次 OCR 识别并点击
            if self.ocr_appear_click(self.O_OVERVIEW_VERSION_ACT, interval=1.0):
                logger.info("在活动总览中检测并点击『版本活动』选项卡")
                time.sleep(0.6)  # 等待右侧大图及前往活动按钮刷新稳定
                return True

            # 点击预设选项卡区域 C_OVERVIEW_VERSION_ACT 兜底
            if self.click(self.C_OVERVIEW_VERSION_ACT, interval=1.0):
                logger.info("通过 C_OVERVIEW_VERSION_ACT 点击『版本活动』选项卡")
                time.sleep(0.6)
                return True

            time.sleep(0.3)
        return False

    def _step_click_goto_activity(self, timeout: float = 5.0) -> bool:
        """点击右下角『前往活动』按钮。"""
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            # 单次 OCR 识别并点击
            if self.ocr_appear_click(self.O_OVERVIEW_GOTO_ACT, interval=1.0):
                logger.info("检测到并点击『前往活动』按钮")
                time.sleep(1.0)  # 等待转场动画
                return True

            # 点击固定区域 C_OVERVIEW_GOTO_ACT 兜底
            if self.click(self.C_OVERVIEW_GOTO_ACT, interval=1.0):
                logger.info("通过 C_OVERVIEW_GOTO_ACT 规则区域点击『前往活动』")
                time.sleep(1.0)
                return True

            time.sleep(0.3)
        return False

    def _step_confirm_entered_activity(self, timeout: float = 6.0) -> bool:
        """确认成功脱离活动总览并进入当期活动主界面。

        转场完成后直接依据通用的黄色返回键判定，彻底消除对每期变动活动标题（如『拾光永恒』）的无效 OCR。
        """
        # 为游戏转场动画预留过渡时间
        time.sleep(1.0)
        timer = Timer(timeout).start()
        while not timer.reached():
            self.screenshot()
            # 只要检测到左上角黄色返回键，即可确认已成功进入当期活动主界面
            if self.appear(GlobalGameAssets.I_UI_BACK_YELLOW):
                logger.info("检测到活动返回键，确认已成功到达当期活动主界面！")
                return True
            time.sleep(0.3)
        return False

    def find_configured_battle_name_box(self, roi: tuple[int, int, int, int] = (150, 100, 950, 500)) -> tuple[tuple[int, int, int, int], str] | None:
        """尝试在指定区域搜索配置的『战斗界面名称』（如『亘地回响』）。

        自适应容错定位层次：
        1. 完整词匹配：如『亘地回响』；
        2. 核心双字/形似字匹配：如『回响』、『亘地』、『日地』、『旦地』、『地回』等；
        3. 单字符合 + 包含『战斗』两个字：只要有一个字符合（含形似字如『地』、『日』）且存在『战斗』，即可复合定位。

        优化特性：
        - 仅执行 1 次全图 ROI OCR 检测，消除多轮候选词重复推理耗时；
        - 支持多文字框坐标联合包围盒计算，精准定位居中点击点；
        - 成功返回 ((x, y, w, h), matched_name)，未找到返回 None。
        """
        conf_obj = getattr(self.config.model, 'activity_shikigami', None)
        if not conf_obj or not hasattr(conf_obj, 'general_climb'):
            return None
        configured_name = getattr(conf_obj.general_climb, 'battle_page_name', '').strip()
        if not configured_name or not self.exist_image():
            return None

        # 1. 常见艺术字体形似字映射表（游戏美术字易识别形似字）
        alias_map = {
            '亘': ['日', '旦', '且'],
            '地': ['土'],
            '响': ['向', '晌'],
            '回': ['同', '口'],
        }

        # 2. 单次 OCR 检测整个 ROI 区域，获取所有文字识别框
        search_rule = RuleOcr(
            roi=roi,
            area=roi,
            mode="Full",
            method="Default",
            keyword=configured_name,
            name=f"O_SEARCH_BATTLE_{configured_name}",
        )
        boxed_results = search_rule.detect_and_ocr(self.device.image)
        if not boxed_results:
            return None

        def get_box_from_indices(indices: list[int]) -> tuple[int, int, int, int]:
            all_x = []
            all_y = []
            for idx in indices:
                b = boxed_results[idx].box
                for pt in b:
                    all_x.append(pt[0])
                    all_y.append(pt[1])
            min_x = min(all_x)
            min_y = min(all_y)
            max_x = max(all_x)
            max_y = max(all_y)
            x = int(min_x + roi[0])
            y = int(min_y + roi[1])
            w = int(max_x - min_x)
            h = int(max_y - min_y)
            return x, y, w, h

        # 层次 1：完整名称优先匹配
        hits = search_rule.filter(boxed_results, configured_name)
        if hits:
            box = get_box_from_indices(hits)
            logger.info(f"定向识别到完整战斗界面名称 [{configured_name}] 于 {box}")
            return box, configured_name

        # 层次 2：核心双字组合及形似字匹配
        chars = list(configured_name)
        candidates_2char: list[str] = []
        if len(chars) >= 2:
            candidates_2char.append(chars[-2] + chars[-1])
            candidates_2char.append(chars[0] + chars[1])
            if len(chars) >= 3:
                candidates_2char.append(chars[1] + chars[2])
            from itertools import combinations
            for c1, c2 in combinations(chars, 2):
                for p in (c1 + c2, c2 + c1):
                    if p not in candidates_2char:
                        candidates_2char.append(p)

            # 注入形似字候选（如 '日地'）
            expanded_candidates = list(candidates_2char)
            for p in candidates_2char:
                for src, aliases in alias_map.items():
                    if src in p:
                        for alias in aliases:
                            ap = p.replace(src, alias)
                            if ap not in expanded_candidates:
                                expanded_candidates.append(ap)
            candidates_2char = expanded_candidates

            for cand in candidates_2char:
                hits = search_rule.filter(boxed_results, cand)
                if hits:
                    box = get_box_from_indices(hits)
                    logger.info(f"定向两字符合识别到战斗界面名称 [{cand}] 于 {box}")
                    return box, cand

        # 层次 3：单字符合 + 存在『战斗』两个字复合匹配
        target_chars = set(chars)
        for c in list(target_chars):
            if c in alias_map:
                target_chars.update(alias_map[c])
        # 排除战斗字面本身，避免自我匹配
        name_chars_without_battle = target_chars - {'战', '斗'}
        if not name_chars_without_battle:
            name_chars_without_battle = target_chars

        # 查找是否存在『战斗』
        battle_indices = [i for i, r in enumerate(boxed_results) if '战斗' in r.ocr_text]
        if not battle_indices:
            hits_battle = search_rule.filter(boxed_results, '战斗')
            if hits_battle:
                battle_indices = hits_battle
        if not battle_indices:
            battle_indices = [i for i, r in enumerate(boxed_results) if '战' in r.ocr_text]

        if battle_indices:
            char_hits: list[tuple[int, str]] = []
            for i, r in enumerate(boxed_results):
                for c in name_chars_without_battle:
                    if c in r.ocr_text:
                        char_hits.append((i, c))
                        break

            if char_hits:
                # 寻找与『战斗』位置最近的单字框进行联合定位
                best_char_idx, best_char = char_hits[0]
                best_battle_idx = battle_indices[0]
                min_dist = float('inf')

                for c_idx, c_val in char_hits:
                    c_box = boxed_results[c_idx].box
                    c_center = (sum(pt[0] for pt in c_box) / len(c_box), sum(pt[1] for pt in c_box) / len(c_box))
                    for b_idx in battle_indices:
                        b_box = boxed_results[b_idx].box
                        b_center = (sum(pt[0] for pt in b_box) / len(b_box), sum(pt[1] for pt in b_box) / len(b_box))
                        dist = ((c_center[0] - b_center[0]) ** 2 + (c_center[1] - b_center[1]) ** 2) ** 0.5
                        if dist < min_dist:
                            min_dist = dist
                            best_char_idx, best_char = c_idx, c_val
                            best_battle_idx = b_idx

                # 合并单字框与战斗框为统一入口卡片点击区域
                combined_indices = list(set([best_char_idx, best_battle_idx]))
                box = get_box_from_indices(combined_indices)
                matched_desc = f"{best_char}+战斗"
                logger.info(f"定向单字+战斗复合识别成功 [{matched_desc}] 于 {box} (距战斗标签={min_dist:.1f}px)")
                return box, matched_desc

        return None

    def find_and_click_act_battle(self, specific_rule=None, interval: float = 1.0) -> bool:
        """自适应寻找活动主界面中的『战斗』/『爬塔』核心玩法入口并点击。

        自适应策略：
        0. 优先尝试定向识别用户配置的『战斗界面名称』（如『亘地回响』）并居中点击；
        1. 尝试自适应 OCR 搜索包含『战斗』/『爬塔』/『战』的文字并动态居中点击；
        2. 若提供了专有规则（如特定切图 I_TO_BATTLE_MAIN）且当前可见，执行回退点击。
        """
        self.screenshot()

        # 0. 优先尝试定向搜索并居中点击用户配置的『战斗界面名称』
        found = self.find_configured_battle_name_box()
        if found:
            box, matched_name = found
            x, y, w, h = box
            cx = int(x + w / 2)
            cy = int(y + h / 2)
            logger.info(f"成功定向定位到配置战斗入口 [{matched_name}] 于 ({cx}, {cy})，执行居中点击")
            click_rule = RuleClick(
                roi_front=(max(0, cx - 20), max(0, cy - 20), 40, 40),
                roi_back=(max(0, cx - 20), max(0, cy - 20), 40, 40),
                name=f"click_configured_{matched_name}",
            )
            return bool(self.click(click_rule, interval=interval))

        # 1. 尝试自适应 OCR 语义定位
        for rule in (
            self.O_ACT_BATTLE_ENTRANCE,        # '战斗'
            self.O_ACT_BATTLE_ENTRANCE_CLIMB,  # '爬塔'
            self.O_ACT_BATTLE_ENTRANCE_CHAR,   # '战'
        ):
            if not rule:
                continue
            box = rule.ocr(self.device.image)
            if box and box != (0, 0, 0, 0):
                x, y, w, h = box
                cx = int(x + w / 2)
                cy = int(y + h / 2)
                logger.info(f"自适应定位到活动主界面战斗入口 [{rule.keyword}] 于 ({cx}, {cy})，执行居中点击")
                click_rule = RuleClick(
                    roi_front=(max(0, cx - 15), max(0, cy - 15), 30, 30),
                    roi_back=(max(0, cx - 15), max(0, cy - 15), 30, 30),
                    name=f"generic_{rule.name}",
                )
                return bool(self.click(click_rule, interval=interval))

        # 2. 尝试专有切图回退
        target_rule = specific_rule or getattr(self, "I_TO_BATTLE_MAIN", None)
        if target_rule and self.appear(target_rule):
            logger.info("自适应未命中，使用专有切图回退点击活动战斗入口")
            return bool(self.appear_then_click(target_rule, interval=interval))

        logger.warning("未能在活动主界面定位到战斗/爬塔入口")
        return False

    def find_and_click_map_battle(self, specific_rule=None, interval: float = 1.5) -> bool:
        """自适应寻找中转地图左侧区域的战斗关卡入口并点击。

        自适应策略：
        1. 若提供了专有规则（如 I_MAP_GOTO_BATTLE）且匹配成功，优先点击；
        2. 优先在左侧区域 (0, 100, 260, 400) 识别 '战斗' 或 '战'，动态居中点击该卡片；
        3. 否则自适应安全点击左侧第 1 个战斗关卡卡片中心 (120, 160)；
        4. 彻底消除对每期关卡名称（如『虚无精锐』）死图切图的依赖。
        """
        # 0. 中转地图卡片滑动与转场动效缓冲等待
        time.sleep(0.5)
        self.screenshot()

        target_rule = specific_rule or getattr(self, "I_MAP_GOTO_BATTLE", None)
        if target_rule and self.appear(target_rule):
            logger.info("在中转地图上检测到推荐关卡切图，执行点击")
            return bool(self.appear_then_click(target_rule, interval=interval))

        for rule in (
            getattr(self, "O_MAP_BATTLE_ENTRANCE", None),
            getattr(self, "O_MAP_BATTLE_ENTRANCE_CHAR", None),
        ):
            if rule and self.ocr_appear(rule):
                x, y = rule.coord()
                logger.info(f"在中转地图左侧卡片区域自适应定位到关卡入口 [{rule.keyword}] 于 ({x}, {y})，执行点击")
                return bool(self.ocr_appear_click(rule, interval=interval))

        # 通用关卡入口区域兜底点击（左侧第 1 个关卡卡片中心）
        logger.info("在中转地图上执行左侧推荐关卡自适应安全点击 (120, 160)")
        click_rule = RuleClick(
            roi_front=(35, 135, 170, 50),
            roi_back=(35, 135, 170, 50),
            name="generic_map_goto_battle",
        )
        return bool(self.click(click_rule, interval=interval))