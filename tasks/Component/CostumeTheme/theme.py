# This Python file uses the following encoding: utf-8
"""庭院菜单主题。原地更新共享规则，保持导航图持有的对象引用有效。"""
from copy import deepcopy

from tasks.Component.Costume.config import ThemeType
from tasks.Component.CostumeTheme.assets import CostumeThemeAssets
from tasks.GameUi.assets import GameUiAssets


_THEME_NAMES = (
    'I_MAIN_SCROLL_CLOSE',
    'I_MAIN_GOTO_COLLECTION', 'I_MAIN_GOTO_TRAVEL',
    'I_MAIN_GOTO_TEAM', 'I_MAIN_GOTO_GUILD', 'I_MAIN_GOTO_MALL',
    'I_MAIN_GOTO_DAILY', 'I_MAIN_GOTO_FRIENDS', 'I_MAIN_GOTO_ONMYODO',
    'I_MAIN_GOTO_SHIKIGAMI_RECORDS',
)
# 在任何任务切换主题前捕获原始默认规则快照
_DEFAULT_RULES = {name: deepcopy(getattr(GameUiAssets, name)) for name in _THEME_NAMES}
_THEME_RULES = {
    ThemeType.COSTUME_THEME_DEFAULT: _DEFAULT_RULES,
    ThemeType.COSTUME_THEME_XINYU_MINGXIAO: {
        # 入口图标复用共享 GameUi 默认规则（含 I_MAIN_GOTO_GUILD 掩码匹配）
        **_DEFAULT_RULES,
        'I_MAIN_SCROLL_CLOSE': CostumeThemeAssets.I_MAIN_SCROLL_CLOSE_2,
    },
}


def apply_theme(theme_type: ThemeType) -> None:
    rules = _THEME_RULES[theme_type]
    for name, source in rules.items():
        target = getattr(GameUiAssets, name)
        # 原地更新状态并清理缓存，不可替换对象本身（页面跳转边持有该引用）
        target.__dict__.clear()
        target.__dict__.update(deepcopy(source.__dict__))
