from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Callable

from module.atom.click import RuleClick
from module.atom.gif import RuleGif
from module.atom.image import RuleImage
from module.atom.list import RuleList
from module.atom.ocr import RuleOcr
from tasks.GameUi.matcher import Matcher
from tasks.GameUi.types import ActionLike, RecognizerLike


def invoke_task_callable(target: Callable[..., Any], task) -> Any:
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return target(task)
    if len(signature.parameters) == 0:
        return target()
    return target(task)


def infer_category() -> str:
    frame = inspect.currentframe()
    if frame is None:
        return "global"
    caller_frame = frame.f_back
    if caller_frame is None:
        return "global"
    module = inspect.getmodule(caller_frame)
    if module is None:
        return "global"
    module_path = Path(module.__file__).resolve()
    tasks_dir = module_path.parent.parent
    if tasks_dir.name != "tasks":
        return "global"
    category_dir = module_path.parent
    if category_dir == tasks_dir:
        return "global"
    return category_dir.name


def infer_page_key_and_name() -> tuple[str, str]:
    frame = inspect.currentframe()
    if frame is None:
        return ("unknown", "unknown")
    caller_frame = frame.f_back
    if caller_frame is None:
        return ("unknown", "unknown")
    code = caller_frame.f_code
    filename = code.co_filename
    line_number = caller_frame.f_lineno
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if 0 <= line_number - 1 < len(lines):
                line = lines[line_number - 1].strip()
                if "=" in line:
                    name = line.split("=")[0].strip()
                    return (name, name)
    except (IOError, IndexError):
        pass
    return ("unknown", "unknown")


def infer_tasks_category_from_parts(module_parts: list[str], tasks_index: int, component_use_child: bool = False) -> str:
    if tasks_index < 0 or tasks_index >= len(module_parts):
        return "global"
    if tasks_index + 1 >= len(module_parts):
        return "global"
    category = module_parts[tasks_index + 1]
    if category == "Component" and component_use_child and tasks_index + 2 < len(module_parts):
        return module_parts[tasks_index + 2]
    return category


def infer_tasks_category_from_path(class_file: Path, component_use_child: bool = False) -> str:
    parts = class_file.parts
    try:
        tasks_index = list(parts).index("tasks")
    except ValueError:
        return "global"
    if tasks_index < 0 or tasks_index >= len(parts):
        return "global"
    if tasks_index + 1 >= len(parts):
        return "global"
    category = parts[tasks_index + 1]
    if category == "Component" and component_use_child and tasks_index + 2 < len(parts):
        return parts[tasks_index + 2]
    return category