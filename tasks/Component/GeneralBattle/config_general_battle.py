# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field

class GreenMarkType(str, Enum):
    GREEN_LEFT1 = 'green_left1'
    GREEN_LEFT2 = 'green_left2'
    GREEN_LEFT3 = 'green_left3'
    GREEN_LEFT4 = 'green_left4'
    GREEN_LEFT5 = 'green_left5'
    GREEN_MAIN = 'green_main'

class GeneralBattleConfig(BaseModel):

    # 是否锁定阵容, 有些的战斗是外边的锁定阵容甚至有些的战斗没有锁定阵容的
    lock_team_enable: bool = Field(default=False, description='lock_team_enable_help')

    # 是否启动 预设队伍
    preset_enable: bool = Field(default=False, description='preset_enable_help')
    # 选哪一个预设组
    preset_group: int = Field(default=1, description='preset_group_help', ge=1, le=7)
    # 选哪一个队伍
    preset_team: int = Field(default=1, description='preset_team_help', ge=1, le=5)
    # 是否启动开启buff
    # buff_enable: bool = Field(default=False, description='buff_enable_help')
    # 是否点击觉醒Buff
    # buff_awake_click: bool = Field(default=False, description='')
    # 是否点击御魂buff
    # buff_soul_click: bool = Field(default=False, description='')
    # 是否点击金币50buff
    # buff_gold_50_click: bool = Field(default=False, description='')
    # 是否点击金币100buff
    # buff_gold_100_click: bool = Field(default=False, description='')
    # 是否点击经验50buff
    # buff_exp_50_click: bool = Field(default=False, description='')
    # 是否点击经验100buff
    # buff_exp_100_click: bool = Field(default=False, description='')

    # 是否开启绿标
    green_enable: bool = Field(default=False, description='green_enable_help')
    # 选哪一个绿标
    green_mark: GreenMarkType = Field(default=GreenMarkType.GREEN_LEFT1, description='green_mark_help')

    # 是否启动战斗时随机点击或者随机滑动
    random_click_swipt_enable: bool = Field(default=False, description='random_click_swipt_enable_help')

    # 以下字段为 mine 分支兼容字段，用于 ActivityShikigami
    continuous_battle: bool = Field(default=False, description='continuous_battle_help')
    max_continuous: int = Field(default=0, description='max_continuous_help', ge=0)
    quick_exit: bool = Field(default=False, description='quick_exit_help')
    battle_timeout: float = Field(default=120.0, description='battle_timeout_help', ge=10.0)


