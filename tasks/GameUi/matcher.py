from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Union

from module.atom.gif import RuleGif
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr
from tasks.GameUi.types import RecognizerLike


def invoke_task_callable(target: Callable[..., Any], task) -> Any:
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return target(task)
    if len(signature.parameters) == 0:
        return target()
    return target(task)


class Matcher:

    def evaluate(self, task) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class AtomMatcher(Matcher):

    target: RecognizerLike

    def evaluate(self, task) -> bool:
        target = self.target
        if callable(target) and not isinstance(target, (RuleImage, RuleGif, RuleOcr)):
            return bool(invoke_task_callable(target, task))
        if isinstance(target, RuleOcr):
            return bool(task.ocr_appear(target))
        if isinstance(target, (RuleImage, RuleGif)):
            return bool(task.appear(target))
        return False


@dataclass(frozen=True)
class AnyMatcher(Matcher):

    children: tuple[Matcher, ...]

    def evaluate(self, task) -> bool:
        return any(child.evaluate(task) for child in self.children)


@dataclass(frozen=True)
class AllMatcher(Matcher):

    children: tuple[Matcher, ...]

    def evaluate(self, task) -> bool:
        return all(child.evaluate(task) for child in self.children)


@dataclass(frozen=True)
class NotMatcher(Matcher):

    child: Matcher

    def evaluate(self, task) -> bool:
        return not self.child.evaluate(task)


def ensure_matcher(target: Union[Matcher | RecognizerLike | Iterable[RecognizerLike] | None]) -> Matcher | None:
    if target is None:
        return None
    if isinstance(target, Matcher):
        return target
    if isinstance(target, (list, tuple, set)):
        return AnyMatcher(tuple(ensure_matcher(item) for item in target if item is not None))
    return AtomMatcher(target)


def any_of(*targets: RecognizerLike | Matcher) -> Matcher:
    return AnyMatcher(tuple(ensure_matcher(target) for target in targets if target is not None))


def all_of(*targets: RecognizerLike | Matcher) -> Matcher:
    return AllMatcher(tuple(ensure_matcher(target) for target in targets if target is not None))


def not_(target: RecognizerLike | Matcher) -> Matcher:
    return NotMatcher(ensure_matcher(target))


def collect_rule_images(target: Union[Matcher | RecognizerLike | Iterable[RecognizerLike] | None]) -> tuple[RuleImage, ...]:
    images: list[RuleImage] = []
    seen = set()

    def visit(node):
        if node is None:
            return
        if isinstance(node, RuleImage):
            cache_key = id(node)
            if cache_key in seen:
                return
            seen.add(cache_key)
            images.append(node)
            return
        if isinstance(node, AtomMatcher):
            visit(node.target)
            return
        if isinstance(node, (AnyMatcher, AllMatcher)):
            for child in node.children:
                visit(child)
            return
        if isinstance(node, NotMatcher):
            visit(node.child)
            return
        if isinstance(node, Matcher):
            return
        if isinstance(node, (list, tuple, set)):
            for item in node:
                visit(item)

    visit(target)
    return tuple(images)