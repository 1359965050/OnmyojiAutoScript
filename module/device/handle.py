# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re

from module.base.dpi import enable_dpi_awareness
enable_dpi_awareness()

from enum import Enum
from cached_property import cached_property
from anytree import NodeMixin, RenderTree, PreOrderIter
from win32api import GetSystemMetrics, SendMessage, MAKELONG, PostMessage
from win32print import GetDeviceCaps
from win32process import GetWindowThreadProcessId
from win32gui import (GetWindowText, EnumWindows, FindWindow, FindWindowEx,
                      IsWindow, GetWindowRect, GetClientRect, SetWindowPos,
                      GetWindowDC, DeleteObject,
                      SetForegroundWindow, IsWindowVisible, GetDC, GetParent,
                      EnumChildWindows, IsIconic)
from win32con import (SRCCOPY, DESKTOPHORZRES, DESKTOPVERTRES, WM_LBUTTONUP,
                      WM_LBUTTONDOWN, WM_ACTIVATE, WA_ACTIVE, MK_LBUTTON,
                      WM_NCHITTEST, WM_SETCURSOR, HTCLIENT, WM_MOUSEMOVE,
                      SWP_NOMOVE, SWP_NOZORDER)
from module.config.config import Config
from module.logger import logger


def handle_title2num(title: str) -> int:
    """
    从标题到句柄号
    :param title:
    :return:  如果没有找到就是返回零
    """
    return FindWindow(None, title)


def handle_num2title(num: int) -> str:
    """
    通过句柄号返回窗口的标题，如果传入句柄号不合法则返回None
    :param num:
    :return:
    """
    return None if num is None or num == 0 or num == '' else GetWindowText(num)


def is_handle_valid(num: int) -> bool:
    """
    输入一个句柄号，如果还在返回True
    :param num:
    :return:
    """
    return IsWindow(num)


def is_handle_healthy(num: int) -> bool:
    """
    检查窗口句柄是否健康可用（句柄有效、窗口可见且非最小化状态）
    :param num: 窗口句柄号
    :return: bool
    """
    if not num or not isinstance(num, int):
        return False
    try:
        if not IsWindow(num) or not IsWindowVisible(num):
            return False
        rect = GetWindowRect(num)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        return w > 0 and h > 0
    except Exception:
        return False


def handle_num2pid(num: int) -> int:
    """
    通过句柄号获取句柄进程id，如果句柄号非法则返回0
    :param num:
    :return:
    """
    return 0 if num is None or num == 0 or num == '' else GetWindowThreadProcessId(num)[1]


def window_scale_rate() -> float:
    """
    获取window的系统缩放 一遍是1
    :return:
    """
    hDC = GetDC(0)
    # 物理上（真实的）的 横纵向分辨率
    wReal = GetDeviceCaps(hDC, DESKTOPHORZRES)
    hReal = GetDeviceCaps(hDC, DESKTOPVERTRES)
    # 缩放后的 分辨率
    wAfter = GetSystemMetrics(0)
    hAfter = GetSystemMetrics(1)
    # print(wReal, wAfter)
    return round(wReal / wAfter, 2)


class WindowNode(NodeMixin):
    def __init__(self, name, num, parent=None):
        super().__init__()
        self.name = name
        self.num = num
        self.parent = parent

    @classmethod
    def get_tree_depth(cls, root_node: 'WindowNode'):
        if not root_node.children:
            return 1 if root_node else 0
        return max(node.depth for node in root_node.descendants) + 1


class EmulatorFamily(Enum):
    FAMILY_MUMU = 10  # mumu模拟器
    FAMILY_OTHER = 60  # 其他模拟器 待定
    FAMILY_WINDOWS_CLIENT = 70  # 阴阳师桌面版


# 各个模拟器的句柄树*******************************************************************************************************
""""
<MuMu>系列
模拟器的窗口名字
----MuMuPlayer      (!如果是mumu12是MuMuPlayer, 否则是NemuPlayer)
--------nemudisplay
"""""
# **********************************************************************************************************************

class Handle:
    emulator_list = ['MuMu12',
                     'MuMu',
                     '阴阳师',
                     'Onmyoji',
                     '模拟器']
    emulator_handle = {
        # mumu
        'mumu_player': ['root_handle_title', 'NemuPlayer'],
        'mumu_player_12': ['root_handle_title', 'MuMuPlayer'],
        'mumu_player_family': ['root_handle_title', 'MuMuPlayer'],
    }
    config: Config = None

    def __init__(self, config) -> None:
        """

        :param config:
        """
        logger.hr('Handle')
        if self.config is None:
            if isinstance(config, str):
                self.config = Config(config, task=None)
            else:
                self.config = config

        self.init_handle()

    def init_handle(self) -> None:
        """
        探测并初始化窗口句柄树及相关属性。支持重试刷新。
        """
        if getattr(self, 'is_windows_client', False):
            h_str = str(self.config.script.device.handle or '').lower()
            if not h_str or any(emu in h_str for emu in ['mumu', 'nox', '雷电', '逍遥', '蓝叠']):
                self.config.script.device.handle = 'auto'

        if not self.config.script.device.handle:
            logger.info('Handle is empty. oas not use handle')
            return
        if self.config.script.device.handle == '':
            logger.info('Handle is empty. oas not use handle')
            return

        # 清除可能缓存的旧属性
        for prop in ('emulator_family', 'screenshot_handle_num', 'screenshot_size'):
            if prop in self.__dict__:
                del self.__dict__[prop]

        # 获取根的句柄
        self.root_handle_title = ''
        self.root_handle_num = 0
        self.root_handle = self.config.script.device.handle
        is_win_client = getattr(self, 'is_windows_client', False)
        if self.root_handle == "auto":
            logger.info('Handle is auto. oas will find window emulator')
            window_list = Handle.all_windows()
            serial = getattr(self, 'serial', None)
            if not serial and hasattr(self, 'config') and hasattr(self.config, 'script'):
                serial = getattr(self.config.script.device, 'serial', None)
            self.root_handle_title = self.auto_handle_title(window_list, is_windows_client=is_win_client, serial=serial)
            if self.root_handle_title:
                self.root_handle_num = handle_title2num(self.root_handle_title)
            else:
                self.root_handle_num = 0
        elif isinstance(self.root_handle, str):
            try:
                self.root_handle_num = int(self.root_handle)
                logger.info('Handle is handle num. oas use it as root handle num')
                if is_handle_valid(self.root_handle_num):
                    logger.info(f'Handle number {self.root_handle_num} is valid')
                    self.root_handle_title = handle_num2title(self.root_handle_num)
            except ValueError:
                logger.info('Handle is handle string. oas use it as root handle title')
                if handle_title2num(self.root_handle) != 0:
                    self.root_handle_num = handle_title2num(self.root_handle)
                    self.root_handle_title = self.root_handle
        logger.info(f'The root handle title is {self.root_handle_title} and num is {self.root_handle_num}')

        if not self.root_handle_num or not is_handle_valid(self.root_handle_num):
            if is_win_client:
                logger.info('No valid Onmyoji game window handle found yet.')
            else:
                logger.warning('No valid emulator or game window handle found.')
            self.root_node = WindowNode(name=self.root_handle_title or 'Unknown', num=0)
            return

        # 获取句柄树
        self.root_node = WindowNode(name=self.root_handle_title, num=self.root_handle_num)
        Handle.handle_tree(self.root_handle_num, self.root_node)
        logger.info('Emulator handle structure:')
        for pre, fill, node in RenderTree(self.root_node):
            logger.info("%s%s" % (pre, node.name))
        for pre, fill, node in RenderTree(self.root_node):
            logger.info("%s%s" % (pre, node.num))

        # 判断是哪一个模拟器 通过句柄树结构
        logger.info(f'Emulator family: {self.emulator_family}')

        # window系统的缩放
        logger.info(f'Your window screen scale rate: {window_scale_rate()}')
        _ = self.screenshot_handle_num
        logger.info(f'Screenshot handle num: {self.screenshot_handle_num}')
        logger.info(f'Emulator screenshot size: {self.screenshot_size}')

    @staticmethod
    def all_windows() -> list:
        """
        获取桌面上的所有窗体

        :return:  类似这样['MuMu模拟器']
        """

        def enum_windows_callback(hwnd, windows):
            if IsWindowVisible(hwnd):
                window_text = GetWindowText(hwnd)
                if window_text:
                    windows.append(window_text)

        windows = []
        try:
            EnumWindows(enum_windows_callback, windows)
        except Exception:
            pass
        return windows

    @classmethod
    def auto_handle_title(cls, windows: list, is_windows_client: bool = False, serial: str = None) -> str:
        """
        返回第一个找到的有模拟器的标题
        :param windows:
        :param is_windows_client: 是否为 Windows 桌面版渠道
        :param serial: 设备串口号或连接地址（如 127.0.0.1:16448）
        :return:
        """
        if windows is None:
            logger.error("handle_auto not get all wnidow")
            return None

        # 优先检测阴阳师桌面版窗口（忽略 IDE 或编辑器窗口）
        for window_title in windows:
            if '阴阳师' in window_title or 'Onmyoji' in window_title:
                if any(ide in window_title.lower() for ide in ['ide', 'antigravity', 'visual studio', 'code', 'pycharm', 'cursor']):
                    continue
                logger.info(f'Found Onmyoji Windows client title: {window_title}')
                return window_title

        if is_windows_client:
            logger.info('Onmyoji PC client window is not present yet.')
            return None

        # 排除内部子窗口、渲染表面，避免被误选为根窗口
        exclude_internal = {'MuMuNxDevice', 'nemudisplay', 'TheRender', 'sub', 'toolbar_nox', 'HD-Player'}

        # 尝试根据 serial 推导多开实例索引
        target_index = None
        if serial:
            s = str(serial).strip().lower()
            s = s.replace('：', ':')
            if s.isdigit():
                s = f'127.0.0.1:{s}'
            elif s.startswith(':') and s[1:].isdigit():
                s = f'127.0.0.1{s}'
            m_port = re.search(r':(\d+)$', s)
            if m_port:
                port = int(m_port.group(1))
                # MuMu 12 / 5.0 端口规律: 基础 16384，步长 32 (16384->0, 16416->1, 16448->2)
                if 16384 <= port <= 20000 and (port - 16384) % 32 == 0:
                    target_index = (port - 16384) // 32

        # 若已知目标实例索引，优先精准匹配对应实例窗口
        if target_index is not None:
            if target_index == 0:
                target_candidates = [
                    'MuMu安卓设备', 'MuMu安卓设备-0', 'MuMu安卓设备-1',
                    'MuMu模拟器12', 'MuMu模拟器12-0', 'MuMu模拟器12-1',
                    'MuMuPlayer', 'MuMuPlayer-0',
                ]
            else:
                target_candidates = [
                    f'MuMu安卓设备-{target_index}',
                    f'MuMu模拟器12-{target_index}',
                    f'MuMuPlayer-{target_index}',
                ]
            for cand in target_candidates:
                if cand in windows:
                    logger.info(f'Found matched emulator window for instance {target_index}: {cand}')
                    return cand

        emu_list = []
        for window_title in windows:
            if window_title in exclude_internal or window_title.startswith('MuMuNxDevice'):
                continue
            for item in Handle.emulator_list:
                if window_title.find(item) != -1:
                    if window_title not in emu_list:
                        emu_list.append(window_title)

        if not len(emu_list):
            logger.error('Can not find emulator handle, please check your emulator is running')
            return None

        # 优先匹配具体模拟器主运行实例正则（支持多开后缀 -1, -2 等）
        instance_patterns = [
            r'^MuMu安卓设备(-\d+)?$',
            r'^MuMu模拟器12(-\d+)?$',
            r'^MuMuPlayer(-\d+)?$',
        ]
        for pattern in instance_patterns:
            for title in emu_list:
                if re.match(pattern, title):
                    logger.info(f'Handle auto select to find {title} by pattern and use it as root_title')
                    return title

        emulator_title = ''
        # 测试mumu12的时候发现 获取的全部的窗体标题有这样的: 'MuMuPlayer', 'MuMuPlayer', 'MuMuPlayer', 'MuMu模拟器12'
        # 事实上 我们只需要最后一个 'MuMu模拟器12'，其他的不重要
        if 'MuMu模拟器12' in emu_list and 'MuMuPlayer' in emu_list:
            emulator_title = 'MuMu模拟器12'

        # 过滤掉多开管理器/外层主控窗口（如 雷电多开器、夜神多开器、逍遥多开器）
        if emulator_title == '':
            clean_list = [w for w in emu_list if '多开' not in w]
            if clean_list:
                emulator_title = clean_list[0]
            else:
                emulator_title = emu_list[0]

        if len(emu_list) > 1:
            logger.warning(f'Find more than one emulator handle, oas will use {emulator_title}')

        logger.info(f'Handle auto seclect to find {emulator_title} and use it as root_title')
        return emulator_title

    @staticmethod
    def handle_tree(hwnd, node: WindowNode, level: int = 0) -> None:
        """
        生成一个窗口的句柄树
        :param hwnd:
        :param node:
        :param level:
        :return:
        """
        child_windows = []
        EnumChildWindows(hwnd, lambda hwnd, param: param.append(hwnd), child_windows)

        if not child_windows:
            return
        for child_hwnd in child_windows:
            if GetParent(child_hwnd) == hwnd:
                child_text = GetWindowText(child_hwnd)
                child_node = WindowNode(name=child_text, num=child_hwnd, parent=node)

                # 递归遍历子窗体的子窗体
                Handle.handle_tree(child_hwnd, child_node, level + 1)

    @cached_property
    def emulator_family(self) -> EmulatorFamily:
        """
        通过句柄树来判断这个是那个模拟器大类
        :return:
        """
        if getattr(self, 'is_windows_client', False):
            return EmulatorFamily.FAMILY_WINDOWS_CLIENT
        if '阴阳师' in self.root_handle_title or 'Onmyoji' in self.root_handle_title:
            return EmulatorFamily.FAMILY_WINDOWS_CLIENT

        children_num = len(self.root_node.children)
        if children_num == 1:
            name = self.root_node.children[0].name
            if name in ('MuMuPlayer', 'MuMuNxDevice', 'NemuPlayer'):
                return EmulatorFamily.FAMILY_MUMU

        # 基于句柄标题的判定
        for emu in Handle.emulator_list:
            if self.root_handle_title.find(emu) != -1:
                if emu in ('阴阳师', 'Onmyoji'):
                    return EmulatorFamily.FAMILY_WINDOWS_CLIENT
                elif emu == 'MuMu':
                    return EmulatorFamily.FAMILY_MUMU
        return EmulatorFamily.FAMILY_OTHER

    @cached_property
    def screenshot_handle_num(self) -> int:
        """
        截屏的句柄其实并不是根句柄
        :return:  出错返回0
        """
        if not getattr(self, 'root_node', None) or not getattr(self.root_node, 'num', 0):
            return 0

        if self.emulator_family == EmulatorFamily.FAMILY_WINDOWS_CLIENT:
            return self.root_node.num

        if self.emulator_family == EmulatorFamily.FAMILY_MUMU:
            # 遍历句柄树，匹配 MuMu 相关内部渲染窗口或子窗口
            for node in PreOrderIter(self.root_node):
                if node.num == self.root_node.num:
                    continue
                if node.name == 'MuMuPlayer':
                    logger.info('The emulator is MuMu模拟器12')
                    return node.num
                elif node.name == 'MuMuNxDevice':
                    logger.info('The emulator is MuMu模拟器5.0')
                    return node.num
                elif node.name == 'NemuPlayer':
                    logger.info('The emulator is MuMu模拟器')
                    return node.num
                elif node.name == 'nemudisplay':
                    logger.info('The emulator display handle found: nemudisplay')
                    return node.num

            if getattr(self.root_node, 'children', None):
                return self.root_node.children[0].num
            return self.root_node.num

        return self.root_node.num

    @cached_property
    def screenshot_size(self) -> tuple or None:
        """
        第一个是width 第二个是heigth
        2023.7.1 在高缩放的设备上应该输出1280X720
        :return:
        """
        hwnd = getattr(self, 'screenshot_handle_num', 0)
        if not hwnd or not is_handle_valid(hwnd):
            return None

        if self.emulator_family == EmulatorFamily.FAMILY_WINDOWS_CLIENT:
            if IsIconic(hwnd):
                if hasattr(self, 'ensure_window_restored'):
                    self.ensure_window_restored(hwnd)
            crect = GetClientRect(hwnd)
            scale_rate = window_scale_rate()
            width_raw = crect[2] - crect[0]
            height_raw = crect[3] - crect[1]
            if width_raw <= 0 or height_raw <= 0:
                width = 1280
                height = 720
            else:
                width = int(round(width_raw * scale_rate))
                height = int(round(height_raw * scale_rate))
                if abs(width - 1280) < 15:
                    width = 1280
                if abs(height - 720) < 15:
                    height = 720
            logger.info(f'Windows client screenshot size: raw=({width_raw}, {height_raw}), scale={scale_rate}, final=({width}, {height})')
            return width, height

        winRect = GetWindowRect(self.screenshot_handle_num)
        scale_rate = window_scale_rate()
        width_before: int = winRect[2] - winRect[0]  # 右x-左x
        height_before: int = winRect[3] - winRect[1]  # 下y - 上y 计算高度
        width, height = width_before, height_before
        if abs((width_before * scale_rate) - 1280) < 5:
            width = 1280
        if abs((height_before * scale_rate) - 720) < 5:
            height = 720
        if width is None or height is None:
            logger.error(f'Get screenshot size error, width={width}, height={height}')
            return None
        return width, height

    @cached_property
    def window_scale_rate(self) -> float:
        """
        获取window的系统缩放 一般是1
        :return:
        """
        hDC = GetDC(0)
        # 物理上（真实的）的 横纵向分辨率
        wReal = GetDeviceCaps(hDC, DESKTOPHORZRES)
        hReal = GetDeviceCaps(hDC, DESKTOPVERTRES)
        # 缩放后的 分辨率
        wAfter = GetSystemMetrics(0)
        hAfter = GetSystemMetrics(1)
        # print(wReal, wAfter)
        return round(wReal / wAfter, 2)


    @classmethod
    def handle_has_children(cls, hwnd: int, name: str = 'MuMuPlayer12') -> bool:
        root_node = WindowNode(name=name, num=hwnd)
        Handle.handle_tree(hwnd=hwnd, node=root_node)
        handle_depth = WindowNode.get_tree_depth(root_node)
        if handle_depth > 1:
            logger.info(f'Window handle [{hwnd}] depth: {handle_depth}')
            return True
        return False


if __name__ == '__main__':
    h = Handle(config='oas1')
    # logger.info(h.auto_handle_title(h.all_windows()))
    # logger.info(h.root_handle_num)
    # logger.info(h.emulator_family)
