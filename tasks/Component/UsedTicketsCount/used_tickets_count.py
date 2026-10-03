# This Python file uses the following encoding: utf-8
from __future__ import annotations

import re
import time
from typing import Optional

from module.atom.ocr import RuleOcr
from module.logger import logger
from tasks.base_task import BaseTask


class UsedTicketsCount(BaseTask):
    """已使用门票计数独立组件。

    职责：
    1. 精准记录并追踪【应用在本次任务运行中实际使用的门票/战斗次数】(app_used_count)。
       严格与游戏界面历史累计值解耦（例如游戏已用23次，手动打5次，应用打18次，此处计数严格为18）。
    2. 独立检测与解析游戏界面门票/体力余量（支持 DigitCounter 分数模式与 Digit 纯数字模式双模解析）。
    3. 提供限额校验与余票耗尽防误杀判定。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 本次应用运行中已使用的门票次数统计: {climb_type: count}
        self._app_used_count: dict[str, int] = {}
        # 上一次识别的游戏门票记录，用于防抖容错: {climb_type: count}
        self._pre_game_tickets_map: dict[str, int] = {}
        # 游戏界面最新识别出的剩余可用次数: {climb_type: remain}
        self._game_remain_map: dict[str, int] = {}
        # 游戏界面最新识别出的已使用/已挑战次数: {climb_type: cur}
        self._game_used_map: dict[str, int] = {}

    @property
    def app_used_count(self) -> dict[str, int]:
        """应用本次运行已使用的门票次数映射表。"""
        if not hasattr(self, '_app_used_count') or self._app_used_count is None:
            self._app_used_count = {}
        return self._app_used_count

    def get_app_used_count(self, climb_type: str) -> int:
        """获取指定爬塔类型在本次应用运行中已使用的门票次数。

        Args:
            climb_type: 爬塔类型 (如 'pass', 'ap', 'ap100', 'boss')

        Returns:
            int: 本次应用运行实际消耗的门票次数。
        """
        return self.app_used_count.get(climb_type, 0)

    def record_ticket_used(self, climb_type: str, count: int = 1, target_limit: int = 0) -> int:
        """记录应用成功消耗门票/完成战斗，将应用运行计数精准递增。

        Args:
            climb_type: 爬塔类型
            count: 本次消耗数量（默认 1）
            target_limit: 目标配置限额（仅用于格式化日志）

        Returns:
            int: 递增后的应用运行已使用门票总数。
        """
        current = self.get_app_used_count(climb_type) + count
        self.app_used_count[climb_type] = current
        limit_desc = f"{target_limit}" if target_limit > 0 else "无限制"
        logger.info(f"[{climb_type}] 应用运行已使用门票: {current} / 目标限额: {limit_desc}")
        return current

    def is_app_limit_reached(self, climb_type: str, target_limit: int) -> bool:
        """判断应用运行使用次数是否已达到用户配置的限额。

        Args:
            climb_type: 爬塔类型
            target_limit: 用户配置的限制次数（<= 0 表示不运行该类型）

        Returns:
            bool: True 表示已达到或超过限制，应停止该模式；False 表示尚未达到。
        """
        if target_limit <= 0:
            logger.info(f"[{climb_type}] 目标配置限额为 {target_limit}，视为达到上限或不执行")
            return True
        used = self.get_app_used_count(climb_type)
        if used >= target_limit:
            logger.info(f"[{climb_type}] 应用运行已使用门票达到配置上限: {used} >= {target_limit}")
            return True
        return False

    def reset_app_counter(self, climb_type: Optional[str] = None):
        """重置应用运行门票计数器。

        Args:
            climb_type: 若指定则只重置该类型，若为 None 则重置全部。
        """
        if climb_type is not None:
            self.app_used_count[climb_type] = 0
            if hasattr(self, '_pre_game_tickets_map') and climb_type in self._pre_game_tickets_map:
                self._pre_game_tickets_map[climb_type] = -1
            logger.info(f"[{climb_type}] 重置应用运行门票计数为 0")
        else:
            self._app_used_count = {}
            self._pre_game_tickets_map = {}
            logger.info("重置所有爬塔类型的应用运行门票计数为 0")

    @classmethod
    def parse_game_ticket_text(cls, raw_text: str) -> tuple[int, int, int]:
        """解析 OCR 提取的门票文本。

        支持两种形态：
        1. 分数形式 (DigitCounter): 如 '12/50', '0/300', '50/50'
           解析为 (已使用, 剩余, 上限)。
        2. 纯数字形式 (Digit): 如 '50', '0'
           解析为 (0, 剩余, 剩余)。

        Args:
            raw_text: 原始 OCR 字符串

        Returns:
            tuple[int, int, int]: (cur_used, remain, total)。若解析失败返回 (0, -1, 0)。
        """
        if not raw_text:
            return 0, -1, 0

        cleaned = str(raw_text).strip()
        # 兼容中文斜杠与其他标点
        cleaned = cleaned.replace('\\', '/').replace('／', '/')

        # 匹配分数型如 12/50
        match = re.search(r'(\d+)\s*/\s*(\d+)', cleaned)
        if match:
            part1 = int(match.group(1))
            part2 = int(match.group(2))
            # 在活动爬塔中，通常 part1 为已挑战次数，part2 为总上限
            cur_used = part1
            total = part2
            remain = max(0, total - cur_used)
            return cur_used, remain, total

        # 纯数字匹配
        digit_match = re.search(r'\d+', cleaned)
        if digit_match:
            num = int(digit_match.group())
            return 0, num, num

        return 0, -1, 0

    @classmethod
    def parse_top_bar_resources(cls, boxed_results: list) -> dict[str, int]:
        """解析顶栏通用 OCR 区域 (481, 6, 600, 55) 内的多资源信息。

        支持拓扑：
        1. 截图场景（多独立数字）：
           从左至右排序后：
           第 1 项数字 -> 常规活动门票 (pass)
           第 2 项数字 -> 特殊/首领门票 (boss / ap100 / five)
           包含 '万' 或第 3 项 -> 体力 (ap)
        2. 分数型单指标场景：
           '20/200' -> pass: 180, total: 200, cur_used: 20
        3. 单纯单数字场景：
           '50' -> pass: 50, total: 50, cur_used: 0

        Args:
            boxed_results: OCR 识别出的文本框列表（支持 BoxedResult 实例或含有 box/ocr_text 的对象/字典）

        Returns:
            dict[str, int]: 结构化各模式资源剩余可用数字，如 {'pass': 50, 'boss': 0, 'ap': 35000}
        """
        if not boxed_results:
            return {}

        # 提取 (x, text) 项并按 x 水平从左到右排序
        items = []
        for res in boxed_results:
            if hasattr(res, 'box') and hasattr(res, 'ocr_text'):
                x = float(res.box[0, 0])
                text = str(res.ocr_text).strip()
            elif isinstance(res, dict):
                x = float(res.get('x', 0))
                text = str(res.get('text', '')).strip()
            elif isinstance(res, (tuple, list)) and len(res) >= 2:
                x = float(res[0])
                text = str(res[1]).strip()
            else:
                continue
            if text:
                items.append((x, text))

        items.sort(key=lambda item: item[0])
        if not items:
            return {}

        resources: dict[str, int] = {}

        # 1. 优先检查是否存在分数型表示，如 20/200
        combined_text = "".join(t for _, t in items)
        for _, text in items:
            cur, remain, total = cls.parse_game_ticket_text(text)
            if '/' in text and total > 0:
                resources['pass'] = remain
                resources['total'] = total
                resources['cur_used'] = cur
                return resources

        fraction_match = re.search(r'(\d+)\s*/\s*(\d+)', combined_text)
        if fraction_match:
            part1 = int(fraction_match.group(1))
            part2 = int(fraction_match.group(2))
            resources['pass'] = max(0, part2 - part1)
            resources['total'] = part2
            resources['cur_used'] = part1
            return resources

        # 2. 多独立数字拓扑解析 (如截图中的 50 +, 0 +, 3.5万 +)
        numeric_tokens: list[tuple[float, int]] = []
        for x, text in items:
            clean_text = text.replace('+', '').replace('＋', '').replace('-', '').replace(',', '').strip()
            if not clean_text:
                continue

            # 处理体力 '万' 单位，如 3.5万
            if '万' in clean_text:
                val_str = clean_text.replace('万', '').strip()
                try:
                    ap_val = int(float(val_str) * 10000)
                    resources['ap'] = ap_val
                except ValueError:
                    pass
                continue

            # 纯整数匹配
            if clean_text.isdigit():
                numeric_tokens.append((x, int(clean_text)))

        if not numeric_tokens:
            return resources

        # 第 1 个数字：常规门票 (pass)
        resources['pass'] = numeric_tokens[0][1]

        # 第 2 个数字：五倍券/首领特殊挑战门票 (boss / ap100 / five)
        if len(numeric_tokens) > 1:
            second_val = numeric_tokens[1][1]
            resources['boss'] = second_val
            resources['ap100'] = second_val
            resources['five'] = second_val

        # 第 3 个数字（若未在前面解析出 '万' 体力）：体力 (ap)
        if len(numeric_tokens) > 2 and 'ap' not in resources:
            resources['ap'] = numeric_tokens[2][1]

        return resources

    def detect_generic_top_tickets(
        self,
        climb_type: str,
        ocr_rule: RuleOcr,
        image=None,
    ) -> tuple[int, int, int]:
        """使用顶栏广域规则自适应检测并提取指定爬塔模式的门票状态。

        Args:
            climb_type: 爬塔模式 ('pass', 'ap', 'boss', 'ap100' 等)
            ocr_rule: 顶栏 RuleOcr 规则 (如 O_GENERIC_TICKETS_BAR)
            image: 截图图像

        Returns:
            tuple[int, int, int]: (已用次数, 剩余可用, 上限)。若未识别出剩余返回 (0, -1, 0)。
        """
        if image is None:
            image = self.device.image

        try:
            boxed_results = ocr_rule.detect_and_ocr(image, logDisplay=True)
        except Exception as e:
            logger.debug(f"顶栏门票 OCR 识别异常: {e}")
            return 0, -1, 0

        resources = self.parse_top_bar_resources(boxed_results)
        if not resources:
            return 0, -1, 0

        remain = resources.get(climb_type, -1)
        total = resources.get('total', remain if remain >= 0 else 0)
        cur_used = resources.get('cur_used', 0)

        return cur_used, remain, total

    def detect_game_tickets(self, ocr_rule: RuleOcr, image=None) -> tuple[int, int, int]:
        """对游戏界面指定区域执行门票 OCR 识别与结构化提取。

        Args:
            ocr_rule: 对应的 RuleOcr 规则对象
            image: 目标图像，默认使用 self.device.image

        Returns:
            tuple[int, int, int]: (已用次数, 剩余可用, 总上限)。若未识别到剩余返回 -1。
        """
        if image is None:
            image = self.device.image

        try:
            # 优先使用 ocr_single 获取原始文字，绕过 ocr_digit 的纯数字断言
            raw_text = ocr_rule.ocr_single(image)
        except Exception as e:
            logger.debug(f"OCR [{ocr_rule.name}] failed: {e}")
            raw_text = ""

        return self.parse_game_ticket_text(raw_text)

    def check_game_tickets_available(self, climb_type: str, ocr_rule: Optional[RuleOcr] = None) -> bool:
        """检查游戏内是否仍有该类型的门票/体力可用。

        若未显式指定 ocr_rule，则自动回退使用顶栏通用自适应规则 O_GENERIC_TICKETS_BAR。

        Args:
            climb_type: 爬塔类型 ('pass', 'ap', 'boss', etc.)
            ocr_rule: 识别门票区域的 RuleOcr 规则（为 None 时采用通用顶栏规则）

        Returns:
            bool: True 表示游戏有票可以继续挑战，False 表示已耗尽无票。
        """
        target_rule = ocr_rule if ocr_rule is not None else getattr(self, 'O_GENERIC_TICKETS_BAR', None)
        if target_rule is None:
            # 均无规则时默认允许，由战斗点击或弹窗接管
            return True

        # 预留 0.5 秒缓冲等待，确保刚从战斗结算退回或进入界面时的淡入动效完全结束
        time.sleep(0.5)
        self.screenshot()
        if ocr_rule is not None:
            cur_used, remain, total = self.detect_game_tickets(ocr_rule, self.device.image)
        else:
            cur_used, remain, total = self.detect_generic_top_tickets(climb_type, target_rule, self.device.image)

        if not hasattr(self, '_game_used_map'):
            self._game_used_map = {}
        if not hasattr(self, '_game_remain_map'):
            self._game_remain_map = {}

        self._game_used_map[climb_type] = cur_used
        self._game_remain_map[climb_type] = remain

        logger.info(
            f"[{climb_type}] 游戏界面票况识别: 已使用={cur_used}, 剩余可用={remain}, 上限={total} | "
            f"应用本次已跑={self.get_app_used_count(climb_type)}"
        )

        # 初始化 pre_map
        if not hasattr(self, '_pre_game_tickets_map'):
            self._pre_game_tickets_map = {}
        pre_remain = self._pre_game_tickets_map.get(climb_type, -1)

        # 明确识别为 0（且不是完全未识别 -1），说明游戏内门票/体力已耗尽
        if remain == 0:
            logger.warning(f"[{climb_type}] 顶栏识别门票剩余为 0，判定门票耗尽")
            return False

        # 如果未识别出有效数字 (-1)
        if remain == -1:
            logger.debug(f"[{climb_type}] 未识别到门票文本，采用历史余量或容错放行")
            if pre_remain == 0:
                logger.warning(f"[{climb_type}] 历史门票记录已为 0，判定无票")
                return False
            return True

        # 上一次识别的票数量和这一次差值大于 1 时，允许容错（防单次识别闪烁抖动）
        if pre_remain != -1 and (pre_remain - remain > 1):
            logger.debug(f"[{climb_type}] 门票识别单次跳变较大 (上次: {pre_remain}, 本次: {remain})，执行差值容错放行")
            self._pre_game_tickets_map[climb_type] = max(0, pre_remain - 1)
            return True

        self._pre_game_tickets_map[climb_type] = remain
        return remain > 0
