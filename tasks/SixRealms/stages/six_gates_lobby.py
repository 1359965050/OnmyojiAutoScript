# This Python file uses the following encoding: utf-8
"""
六道之门总页 / 孔雀国进入流程 Stage

职责：
- 识别当前处于六道之门总页或孔雀国大厅/初始技能选择界面
- 处理 60 体力弹窗、开启挑战、继续、进入、最终 BOSS 挑战、初始技能选择等
- 成功进入副本（出现备战/继续/退出弹窗/式神确认/3卡技能选择）后不再命中
"""
from time import sleep

from module.logger import logger
from tasks.GameUi.assets import GameUiAssets as G
from tasks.SixRealms.stages.base_stage import Stage


class SixGatesLobbyStage(Stage):
    """六道之门入口大厅及孔雀国进入流程。"""

    def recognize(self) -> bool:
        task = self.task
        island_name = task.O_ISLAND_NAME.ocr(task.device.image)
        # 孔雀国大厅必须优先被本 Stage 处理，不能被 already_in_run 排除
        if island_name == "孔雀国" or task.appear(task.I_MSTART):
            return True
        # 命中大厅或初始技能选择，但排除已经进入副本的情况
        in_lobby = (
            task.appear(G.I_CHECK_SIX_GATES) or
            task.ocr_appear(G.O_CHECK_SIX_GATES_TITLE) or
            task.is_peacock_lobby()
        )
        already_in_run = task.appear(task.I_PREPARE_BATTLE) or task.appear(task.I_M_STORE)
        return in_lobby and not already_in_run

    def act(self) -> bool:
        task = self.task
        logger.info("[SixGatesLobby] Processing lobby entry flow")

        if task.appear_then_click(task.I_MSTART_CONFIRM, interval=2):
            return True
        if task.appear_then_click(task.I_MSTART_CONFIRM2, interval=2):
            return True

        if task.appear_then_click(task.I_MSTART, interval=2):
            sleep(2.0)
            return True

        if task.appear_then_click(task.I_BOSS_FIRE, interval=2):
            logger.info("[SixGatesLobby] Clicked boss challenge button")
            sleep(2.0)
            return True

        if task.appear_then_click(task.I_MCONINUE, interval=2):
            sleep(2.0)
            return True

        # 孔雀国大厅点击开启挑战
        island_name = task.O_ISLAND_NAME.ocr(task.device.image)
        if island_name == "孔雀国" or task.is_peacock_lobby():
            logger.info("[SixGatesLobby] Inside Peacock Kingdom lobby, clicking start challenge")
            if task.appear_then_click(task.I_MSTART, interval=2):
                sleep(2.0)
                return True
            task.device.click(x=1160, y=630, control_name="Peacock_Lobby_Challenge")
            sleep(2.0)
            return True

        if task.appear_then_click(task.I_MSKIP, interval=2):
            return True
        if task.appear_then_click(task.I_MSTART_UNCHECK, interval=2):
            return True

        if task.appear_then_click(task.I_MENTER, interval=2):
            sleep(2.0)
            return True

        return False
