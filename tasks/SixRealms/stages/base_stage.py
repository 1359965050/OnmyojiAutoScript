# This Python file uses the following encoding: utf-8
"""
六道之门 Stage 基类

每个 Stage 对应游戏中的一个独立界面，职责单一：
- recognize(): 判断当前是否处于该界面
- act(): 执行该界面下需要的操作
"""
from abc import ABC, abstractmethod


class Stage(ABC):
    """六道之门单一界面模块的抽象基类。"""

    def __init__(self, task):
        self.task = task

    @abstractmethod
    def recognize(self) -> bool:
        """
        根据当前 screenshot 判断是否为该 Stage 负责的界面。
        :return: True 表示命中，False 表示不命中
        """
        raise NotImplementedError

    @abstractmethod
    def act(self) -> bool:
        """
        执行该界面下的操作。
        :return: True 表示执行了动作（通常需要 continue 主循环），False 表示未执行
        """
        raise NotImplementedError

    def run(self) -> bool:
        """命中则执行，简化 dispatcher 调用。"""
        if self.recognize():
            return self.act()
        return False
