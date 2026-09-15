# This Python file uses the following encoding: utf-8
"""活动爬塔通用组件异常定义模块。"""


class LimitTimeOut(Exception):
    """任务运行时间超时异常。"""
    pass


class LimitCountOut(Exception):
    """单模式运行次数/门票达到限制异常。"""
    pass


class TicketsNotEnough(Exception):
    """游戏内门票/体力不足异常。"""
    pass
