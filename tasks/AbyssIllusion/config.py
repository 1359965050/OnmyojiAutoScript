# This Python file uses the following encoding: utf-8
# @author runhey
from pydantic import Field

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase
from tasks.Component.config_scheduler import Scheduler


class AbyssIllusionConfig(ConfigBase):
    limit_count: int = Field(default=0, title='挑战次数上限',
                             description='0 表示不限制，按门票/挑战券数量判断；大于 0 时达到该次数也会停止')


class AbyssIllusion(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler, title='任务调度')
    abyss_illusion_config: AbyssIllusionConfig = Field(default_factory=AbyssIllusionConfig, title='狭间幻境设置')
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig, title='执行任务前切换御魂')
    general_battle_config: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig, title='战斗配置')
