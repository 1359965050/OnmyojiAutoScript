# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from typing import Any, Dict

from pydantic import Field, ValidationError, field_validator, model_serializer, model_validator

from module.logger import logger
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase
from tasks.Component.config_scheduler import Scheduler


class DefaultStrategy(ConfigBase):
    # 1 是高于阈值选这个阵容，2 是低于这个阈值选这个阵容
    md_preset_group_team_default_1: str = Field(default='1,1', description='md_preset_group_team_default_1_help')
    md_preset_group_team_default_2: str = Field(default='1,1', description='md_preset_group_team_default_2_help')


class Strategy(ConfigBase):
    # 匹配的式神中文名字
    md_match_names: str = Field(default='御撰津')
    # 选哪一个预设组（高血量 / 低血量）
    md_preset_group_team_1: str = Field(default='1,1')
    md_preset_group_team_2: str = Field(default='1,1')

    def is_valid(self) -> bool:
        return bool(self.md_match_names)

    @classmethod
    def parse_names(cls, names: str) -> list[str]:
        names = names.replace('，', ',').replace(' ', '')
        return [n for n in names.split(',') if n]

    @classmethod
    def parse_group_team(cls, team: str) -> list[int]:
        team = team.replace('，', ',').replace(' ', '')
        team = ''.join(c for c in team if c.isdigit() or c == ',')
        try:
            result = [int(i) for i in team.split(',') if i != '']
            if len(result) != 2:
                raise ValueError('group team length is not 2')
            if result[0] < 1 or result[0] > 7:
                raise ValueError('group is not valid (1-7)')
            if result[1] < 1 or result[1] > 5:
                raise ValueError('team is not valid (1-5)')
            return result
        except Exception as e:
            logger.error(f'group team string: {team}')
            logger.error(f'parse_team error: {e}')
            raise

    @classmethod
    def parse_all(cls, data: list['Strategy'] | None) -> dict[str, list[int]]:
        result: dict[str, list[int]] = {}
        if not data:
            return result
        for item in data:
            value = (
                item.parse_group_team(item.md_preset_group_team_1)
                + item.parse_group_team(item.md_preset_group_team_2)
            )
            for name in cls.parse_names(item.md_match_names):
                result.setdefault(name, value)
        return result


class MetaDemonConfig(ConfigBase):
    meta_crafting_card: bool = Field(default=True, description='craft_essence_help')
    auto_tea: bool = Field(default=False, description='auto_tea_help')
    auto_shared_boss: bool = Field(default=True, description='auto_shared_boss_help')
    md_fatigue_summon_first: bool = Field(default=True, description='md_fatigue_summon_first_help')
    md_strategy_count: int = Field(default=0, ge=0, description='md_strategy_count_help')
    md_use_strategy: bool = Field(default=False, description='md_use_strategy_help')

    @field_validator('auto_tea', mode='after')
    @classmethod
    def to_false(cls, v):
        return False

    @field_validator('md_strategy_count', mode='after')
    @classmethod
    def validator_strategy_count(cls, v):
        return max(0, int(v))


class MetaDemon(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    meta_demon_config: MetaDemonConfig = Field(default_factory=MetaDemonConfig)
    md_default_strategy: DefaultStrategy = Field(default_factory=DefaultStrategy)
    md_strategies: list[Strategy] = Field(default_factory=list)

    @model_validator(mode='before')
    @classmethod
    def validator_all(cls, v: Any) -> Any:
        if not isinstance(v, dict):
            return v
        v = dict(v)
        cfg = v.get('meta_demon_config')
        if isinstance(cfg, dict):
            strategy_count = max(0, int(cfg.get('md_strategy_count', 0)))
        elif isinstance(cfg, MetaDemonConfig):
            strategy_count = max(0, int(cfg.md_strategy_count))
        else:
            strategy_count = 0

        list_name = 'md_strategies'
        raw_list = v.get(list_name)
        current_list: list[Strategy] = []
        if isinstance(raw_list, list):
            for elem in raw_list:
                if isinstance(elem, Strategy):
                    current_list.append(elem)
                elif isinstance(elem, dict):
                    try:
                        item = Strategy(**elem)
                        if item.is_valid():
                            current_list.append(item)
                    except (ValidationError, TypeError):
                        pass

        remove_keys = []
        for key, value in v.items():
            if key == list_name or list_name not in key:
                continue
            if isinstance(value, dict):
                try:
                    item = Strategy(**value)
                    if item.is_valid():
                        current_list.append(item)
                    remove_keys.append(key)
                except (ValidationError, TypeError):
                    pass
        for key in remove_keys:
            del v[key]

        if len(current_list) < strategy_count:
            current_list.extend(Strategy() for _ in range(strategy_count - len(current_list)))
        elif len(current_list) > strategy_count:
            current_list = current_list[:strategy_count]
        v[list_name] = current_list
        return v

    @model_serializer()
    def serializer_model(self) -> Dict[str, Any]:
        properties = self.__dict__
        data: Dict[str, Any] = {}

        def v_dump(val):
            try:
                return val.model_dump()
            except AttributeError as e:
                logger.error(e)
                return val

        for key, val in properties.items():
            if isinstance(val, list):
                for index, item in enumerate(val):
                    data[f'{key}_{index + 1}'] = v_dump(item)
            else:
                data[key] = v_dump(val)
        return data
