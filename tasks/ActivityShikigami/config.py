# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta, time
from module.logger import logger

from pydantic import BaseModel, ConfigDict, Field, model_validator, validator

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time, dynamic_hide
from typing import Optional


class GeneralClimb(ConfigBase):
    limit_time: Time = Field(default=Time(hour=1, minute=30), title='限制运行时间', description='总限制时间')
    pass_limit: int = Field(default=50, title='门票爬塔最大次数', description='')
    ap_limit: int = Field(default=300, title='体力爬塔最大次数', description='')
    boss_limit: int = Field(default=20, title='Boss战最大次数', description='')
    run_sequence: str = Field(default='pass,ap,boss',
                              title='运行爬塔顺序',
                              description='可选：pass(门票), ap(体力), boss(boss战)\n'
                                          '英文逗号分隔，从左到右依次运行\n'
                                          '例：pass,ap,boss = 先门票 -> 再体力 -> 再boss战')

    @property
    def limit_time_v(self) -> timedelta:
        if isinstance(self.limit_time, time):
            return timedelta(hours=self.limit_time.hour, minutes=self.limit_time.minute,
                             seconds=self.limit_time.second)
        return self.limit_time

    @property
    def run_sequence_v(self) -> list[str]:
        """得到limit>0且配置好的运行顺序序列"""
        self.valid_run_sequence()
        str_list = [climb_type.strip() for climb_type in self.run_sequence.split(',')]
        return [climb_type for climb_type in str_list if getattr(self, f'{climb_type}_limit', 0) > 0]

    # @model_validator(mode='after')
    def valid_run_sequence(self):
        if not self.run_sequence or not self.run_sequence.strip():
            raise ValueError('run sequence cannot be empty')
        sequence_list = [climb_type.strip() for climb_type in self.run_sequence.split(',')]
        if not sequence_list or len(sequence_list) < 1:
            raise ValueError('run sequence cannot be empty')
        label_set = {field.replace('_limit', '') for field in self.model_fields if field.endswith('_limit')}
        for climb_type in sequence_list:
            if climb_type not in label_set:
                raise ValueError(f'run sequence can only be one of {", ".join(label_set)}, now is {climb_type}')
        return self

    @validator('limit_time', pre=True, always=True)
    def parse_limit_time(cls, value):
        if isinstance(value, str):
            if value.isdigit():
                try:
                    value = int(value)
                except ValueError:
                    logger.warning('Invalid limit_time value. Expected format: seconds')
                    return time(hour=0, minute=30, second=0)
                delta = timedelta(seconds=value)
                return time(hour=delta.seconds // 3600, minute=delta.seconds // 60 % 60, second=delta.seconds % 60)
            else:
                try:
                    return time.fromisoformat(value)
                except ValueError:
                    logger.warning('Invalid limit_time value. Expected format: HH:MM:SS')
                    return time(hour=0, minute=30, second=0)
        return value


def check_soul_by_number(enable_switch: bool, group_team: str, label: str):
    if not enable_switch:
        return
    if not group_team or group_team == "-1,-1":
        raise ValueError(f"[{label}]Switch Soul configuration is enabled, but there is no setting")
    if ',' not in group_team:
        raise ValueError(f"[{label}]The switch soul configuration must be in English ','")
    parts = group_team.split(',')
    if len(parts) != 2:
        raise ValueError(f"[{label}]The length of the switch soul configuration must be equal to 2")
    if not all(p.strip().isdigit() for p in parts):
        raise ValueError(f"[{label}]Switching soul configurations must be numeric")


def check_soul_by_ocr(enable_switch: bool, group_team: str, label: str):
    if not enable_switch:
        return
    if not group_team:
        raise ValueError(f"[{label}]Switch Soul configuration is enabled, but there is no setting")
    if ',' not in group_team:
        raise ValueError(f"[{label}]The switch soul configuration must be in English ','")
    parts = group_team.split(',')
    if len(parts) != 2:
        raise ValueError(f"[{label}]The length of the switch soul configuration must be equal to 2")


class SwitchSoulConfig(BaseModel):
    enable_switch_pass: bool = Field(default=False, title='切换御魂', description='爬塔战斗前是否切换到下方指定御魂分组')
    pass_group_team: str = Field(default='-1,-1', title='御魂分组', description='格式：预设组,队伍。例如"1,2"表示第一预设组第二个队伍，使用英文逗号')
    enable_switch_pass_by_name: bool = Field(default=False, title='按名称切换', description='是否通过OCR识别御魂分组名称来切换')
    pass_group_team_name: str = Field(default='', title='分组名称', description='OCR方式使用的目标分组名称，留空则不切换')

    enable_switch_boss: bool = Field(default=False, title='Boss战切换御魂', description='Boss战战斗前是否切换到下方指定御魂分组')
    boss_group_team: str = Field(default='-1,-1', title='Boss战御魂分组', description='格式：预设组,队伍。例如"1,2"表示第一预设组第二个队伍，使用英文逗号')
    enable_switch_boss_by_name: bool = Field(default=False, title='Boss战按名称切换', description='是否通过OCR识别御魂分组名称来切换')
    boss_group_team_name: str = Field(default='', title='Boss战分组名称', description='OCR方式使用的目标分组名称，留空则不切换')

    # @model_validator(mode='after')
    def validate_switch_soul(self):
        label_set = self.get_label_set()
        for label in label_set:
            enable_num = getattr(self, f"enable_switch_{label}", False)
            team = getattr(self, f"{label}_group_team", None)
            check_soul_by_number(enable_num, team, label=label.upper())

            enable_ocr = getattr(self, f"enable_switch_{label}_by_name", False)
            team_name = getattr(self, f"{label}_group_team_name", None)
            check_soul_by_ocr(enable_ocr, team_name, label=label.upper())
        return self

    def get_label_set(self):
        return {field.replace("enable_switch_", "") for field in self.model_fields if
                field.startswith("enable_switch_") and not field.endswith("by_name")}


class ActivityShikigami(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler, title='任务调度')
    general_climb: GeneralClimb = Field(default_factory=GeneralClimb, title='通用爬塔')
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig, title='执行任务前切换御魂')

    pass_battle_conf: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig, title='战斗配置')
    boss_battle_conf: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig, title='Boss战战斗配置')
