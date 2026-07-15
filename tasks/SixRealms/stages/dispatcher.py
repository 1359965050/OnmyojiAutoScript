# This Python file uses the following encoding: utf-8
"""
六道之门 Stage 调度器

按优先级依次询问每个 Stage 是否命中当前界面，命中的 Stage 执行一次动作。
Stage 顺序很重要：越具体/越关键的界面越靠前。
"""
from module.logger import logger
from tasks.SixRealms.stages.base_stage import Stage


class StageDispatcher:
    """管理所有 SixRealms Stage 并按优先级调度。"""

    def __init__(self, task, stages: list[Stage] = None):
        self.task = task
        self.stages = stages or []

    def register(self, stage: Stage):
        """注册一个 Stage，后注册的排在队尾（优先级更低）。"""
        self.stages.append(stage)

    def tick(self) -> bool:
        """
        主循环每 tick 调用一次。

        :return: True 表示有 Stage 命中并执行了动作；False 表示没有任何 Stage 命中
        """
        for stage in self.stages:
            if stage.recognize():
                logger.debug(f"[Dispatcher] Stage hit: {stage.__class__.__name__}")
                return stage.act()
        return False

    @staticmethod
    def is_task_finished(task) -> bool:
        """通用结束判断：回到探索页或庭院即认为任务结束。"""
        return (
            task.appear(task.I_CHECK_EXPLORATION) or
            task.appear(task.I_CHECK_MAIN) or
            task.appear(task.I_MAIN_GOTO_EXPLORATION)
        )
