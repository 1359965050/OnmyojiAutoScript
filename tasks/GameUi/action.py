from __future__ import annotations

from dataclasses import dataclass

from tasks.GameUi.matcher import Matcher, ensure_matcher
from tasks.GameUi.types import ActionLike, RecognizerLike


@dataclass(frozen=True)
class ActionSequence:

    actions: tuple[ActionLike, ...]
    success_index: int = 0


@dataclass(frozen=True)
class ConditionalAction:

    condition: Matcher
    action: ActionLike


def sequence(*actions: ActionLike, success_index: int = 0) -> ActionSequence:
    return ActionSequence(tuple(actions), success_index=success_index)


def conditional_action(condition: RecognizerLike | Matcher, action: ActionLike) -> ConditionalAction:
    matcher = ensure_matcher(condition)
    if matcher is None:
        raise ValueError("conditional_action requires a valid condition")
    return ConditionalAction(matcher, action)