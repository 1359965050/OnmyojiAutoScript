import typing as t

from module.device.platform2.handlers.base import EmulatorHandler
from module.device.platform2.handlers.mumu12 import MuMu12Handler
from module.device.platform2.handlers.mumu import MuMuHandler

_ALL_HANDLERS: list[EmulatorHandler] = [
    MuMu12Handler(),
    MuMuHandler(),
]

_HANDLER_MAP: dict[str, EmulatorHandler] = {}
for _h in _ALL_HANDLERS:
    for _name in _h.type_names():
        _HANDLER_MAP[_name] = _h


def get_handler(emulator_type: str) -> t.Optional[EmulatorHandler]:
    """根据模拟器类型名获取对应的 Handler 实例。"""
    return _HANDLER_MAP.get(emulator_type)


def all_handlers() -> list[EmulatorHandler]:
    """返回所有已注册的 Handler 列表。"""
    return list(_ALL_HANDLERS)
