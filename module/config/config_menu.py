# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import json

from cached_property import cached_property
from pydantic import BaseModel, ValidationError, validator, Field

from module.config.utils import *


class ConfigMenu:
    # 手动的代码配置菜单
    def __init__(self) -> None:
        self.menu = {}
        # 总览
        self.menu["Overview"] = []
        self.menu['TaskList'] = []
        # 全局设置
        self.menu['GlobalSettings'] = ['EmulatorSettings', 'Restart', 'GameSettings']
        # 刷御魂
        self.menu["Soul Zones"] = ['Orochi', 'Sougenbi', 'FallenSun', 'EternitySea']
        # 日常的任务
        self.menu["Daily Task"] = ['AreaBoss', 'DemonEncounter', 'BondlingFairyland', 'EvoZone',
                                   'Exploration', 'GoryouRealm', 'Hyakkiyakou']
        # 阴阳寮
        self.menu["Guild"] = ['KekkaiUtilize', 'KekkaiActivation', 'RealmRaid', 'RyouToppa', 'Dokan',
                              'Hunt' , 'AbyssShadows', 'GuildBanquet', 'DemonRetreat', 'GuildActivityMonitor']
        # 每周任务
        self.menu["Weekly Task"] = ['RichMan', 'Secret', 'WeeklyTrifles', 'SixRealms', 'HeroTest']
        # 活动的任务
        self.menu["Activity Task"] = ['ActivityShikigami', 'MetaDemon', 'DyeTrials']

    @cached_property
    def gui_menu(self) -> str:
        """
        生成的是json字符串
        :return:
        """
        return json.dumps(self.menu, ensure_ascii=False, sort_keys=False, default=str)

    @cached_property
    def gui_menu_list(self) -> dict:
        del self.menu['TaskList']
        self.menu.pop('Tools', None)
        return self.menu


if __name__ == "__main__":
    try:
        m = ConfigMenu()
        print(m.gui_menu)
    except:
        print('weih')