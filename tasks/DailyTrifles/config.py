# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, dynamic_hide, DateTime
from enum import Enum


class SummonType(str, Enum):
    default = '普通召唤'
    recall = '今忆召唤'


class PetsConfig(ConfigBase):
    # 快速喂养
    pets_feast: bool = Field(default=True)
    enable_orochi_ten_once: bool = Field(default=False)
    # 御魂切换配置（平铺，避免嵌套子模型导致前端 schema 解析问题）
    switch_soul_enable: bool = Field(default=False)
    switch_group_team: str = Field(default='-1,-1', description='switch_group_team_help')
    enable_switch_by_name: bool = Field(default=False, description='enable_switch_by_name_help')
    group_name: str = Field(default='')
    team_name: str = Field(default='')


class SimpleTidy(BaseModel):
    # 简易整理：贪吃鬼和奉纳
    enable_greed: bool = Field(default=True, description="是否启用贪吃鬼")
    enable_maneki: bool = Field(default=True, description="是否启用奉纳")


class DoneRecord(ConfigBase):
    courtyard_affairs_dt: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"))
    pickup_email_dt: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"))
    summon_dt: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"))
    luck_msg_dt: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"))
    store_sign_dt: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"))


class DailyTriflesConfig(BaseModel):
    # 庭院事务
    courtyard_affairs: bool = Field(default=True)
    # 收取邮件
    pickup_email: bool = Field(default=True)
    one_summon: bool = Field(title='One Summon', default=False)
    # 召唤类型
    summon_type: SummonType = Field(default=SummonType.default, description='召唤类型')
    # 是否绘制神秘图案
    draw_mystery_pattern: bool = Field(title='Draw Mystery Pattern', default=False, description='是否绘制神秘图案')
    luck_msg: bool = Field(title='Luck Msg', default=False)
    store_sign: bool = Field(title='Store Sign', default=False, description='store_sign_help')

    hide_fields = dynamic_hide('draw_mystery_pattern')


class DailyTrifles(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    trifles_config: DailyTriflesConfig = Field(default_factory=DailyTriflesConfig)
    pets_config: PetsConfig = Field(default_factory=PetsConfig)
    simple_tidy: SimpleTidy = Field(default_factory=SimpleTidy)
    done_record: DoneRecord = Field(default_factory=DoneRecord)

    hide_fields = dynamic_hide('done_record')

    def today_is_done(self, mode: str) -> bool:
        """对应mode今天是否已经完成"""
        done_dt = getattr(self.done_record, f'{mode}_dt', None)
        if done_dt is None:
            return False
        return done_dt.date() == datetime.today().date()
