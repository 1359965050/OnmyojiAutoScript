import numpy as np
from enum import Enum

from module.logger import logger
from module.exception import *
from module.atom.image import RuleImage

from tasks.GlobalGame.assets import GlobalGameAssets


class AnalyzeType(str, Enum):
    NONE = "none"
    SoulOverflow = "soul_overflow"


class PostDiagnotor(GlobalGameAssets):
    def handle(self, e: Exception, command: str, image: np.ndarray) -> AnalyzeType:
        # SoulsTidy 模块已物理移除，御魂溢出检测功能暂时禁用
        return AnalyzeType.NONE
