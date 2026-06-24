from __future__ import annotations

from typing import Any, Callable, Union

from module.atom.click import RuleClick
from module.atom.gif import RuleGif
from module.atom.image import RuleImage
from module.atom.list import RuleList
from module.atom.ocr import RuleOcr

RecognizerLike = Union[RuleImage, RuleGif, RuleOcr, Callable[..., bool], None]
ActionLike = Union[RuleImage, RuleGif, RuleOcr, RuleList, RuleClick, Callable[..., Any], None]