# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum

from pydantic import BaseModel, Field

from tasks.GlobalGame.config_emergency import Emergency
from tasks.Component.Costume.config import CostumeConfig


class BattleTaskOverEnum(str, Enum):
    FINISH = 'finish'
    EXIT = 'exit'


class BattleTakeover(BaseModel):
    battle_timeout: int = Field(default=420, description='battle_timeout_global_help', ge=1)
    on_takeover: BattleTaskOverEnum = Field(default=BattleTaskOverEnum.FINISH, description='on_takeover_help')


class GlobalGame(BaseModel):
    emergency: Emergency = Field(default_factory=Emergency)
    costume_config: CostumeConfig = Field(default_factory=CostumeConfig)
    battle: BattleTakeover = Field(default_factory=BattleTakeover)
