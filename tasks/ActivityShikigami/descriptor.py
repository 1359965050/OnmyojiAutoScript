from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from tasks.ActivityShikigami.base_act import BaseAct
    from module.atom.image import RuleImage


@dataclass
class EventDescriptor:
    """爬塔活动描述器 - 声明活动特有数据的接口

    每个活动定义一个 EventDescriptor，BaseAct 据此创建页面和导航。
    """
    # === 活动身份 ===
    event_id: str = ""                     # 唯一标识，如 "normal"
    name: str = "未命名活动"               # 日志/显示名称

    # === 入口与主页面 ===
    entry_button: 'RuleImage' = None                  # 庭院→活动入口按钮模板图
    main_page_check: 'RuleImage' = None               # 活动主界面检测图
    main_page_enter_failure_hooks: list = field(default_factory=list)

    # === 可选的页面注册钩子 ===
    on_setup_pages: Optional[Callable[['BaseAct'], None]] = None

    def setup_pages(self, act: 'BaseAct') -> None:
        """调用 on_setup_pages 钩子（如果有）"""
        if self.on_setup_pages:
            self.on_setup_pages(act)
