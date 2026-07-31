# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field

class AreaBossFloor(str, Enum):
    DEFAULT = '不更改'
    ONE = '一星'
    TEN = '十星'
    NORMAL_LV1 = '普通-1级'
    NORMAL_LV60 = '普通-60级'

class Boss(BaseModel):
    # 是否查找当日悬赏鬼王
    boss_reward: bool = Field(default=False, description='boss_reward_help')
    # 悬赏默认打较简单的一星鬼王，若想要更高悬赏奖励可自行更改为十星或不更改（保留已勾选DEBUFF）
    reward_floor: AreaBossFloor = Field(default=AreaBossFloor.DEFAULT, description='reward_floor_help')
    # 是否使用收藏的
    use_collect: bool = Field(default=False, description='use_collect_help')
