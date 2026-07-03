# This Python file uses the following encoding: utf-8
# @author AzurTian
from pydantic import Field

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase
from tasks.Component.config_scheduler import Scheduler


class GuaGuaArtRoomConfig(ConfigBase):
    limit_count: int = Field(default=0, title='挑战次数上限',
                             description='0 表示不限制，按「今日可得」判断；大于 0 时达到该次数也会停止')


class GuaGuaArtRoom(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler, title='任务调度')
    gua_gua_art_room_config: GuaGuaArtRoomConfig = Field(default_factory=GuaGuaArtRoomConfig, title='呱呱画室设置')
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig, title='执行任务前切换御魂')
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig, title='战斗配置')
