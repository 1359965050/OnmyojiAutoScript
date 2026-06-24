from module.logger import logger
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets as asa
from tasks.ActivityShikigami.base_act import BaseAct
import tasks.ActivityShikigami.page as pages
from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig


class NormalClimbAct(BaseAct):

    def before_run(self):
        super().before_run()
        pass