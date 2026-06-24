from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Union

from tasks.GameUi.common import ActionLike, RecognizerLike, infer_category, infer_page_key_and_name
from tasks.GameUi.matcher import Matcher, ensure_matcher
from tasks.GameUi.registry import PageRegistry
from module.logger import logger


def _clamp_priority(value: int, page_key: str) -> int:
    priority = max(1, min(100, value))
    if priority != value:
        logger.warning(f"Page priority out of range: key={page_key}, value={value}, clamped={priority}")
    return priority


def sort_pages_by_priority(indexed_pages: Iterable[tuple[int, "Page"]]) -> list["Page"]:
    ordered_pages = sorted(indexed_pages, key=lambda item: (-item[1].priority, item[0]))
    return [page for _, page in ordered_pages]


@dataclass
class Transition:

    source: "Page"
    destination: "Page"
    action: ActionLike
    cost: float = 0.0
    key: str | None = None
    on_enter_success: list[ActionLike] = field(default_factory=list)
    on_enter_failure: list[ActionLike] = field(default_factory=list)
    on_leave_success: list[ActionLike] = field(default_factory=list)
    on_leave_failure: list[ActionLike] = field(default_factory=list)

    def __post_init__(self):
        if self.key is None:
            self.key = f"{self.source.key}->{self.destination.key}#{len(self.source.transitions)}"

    def hooks(self, stage: str) -> list[ActionLike]:
        return getattr(self, stage)


class Page:

    def __init__(
        self,
        recognizer: Union[Matcher, RecognizerLike, Iterable[RecognizerLike]],
        *,
        key: str | None = None,
        name: str | None = None,
        category: str | None = None,
        priority: int = 50,
        cost: float = 1.0,
        register: bool = True,
    ):
        inferred_key, inferred_name = infer_page_key_and_name()
        self.key = key or inferred_key
        self.name = name or inferred_name
        self.category = category or infer_category()
        self.priority = _clamp_priority(priority, self.key)
        self.cost = cost
        self.recognizer = ensure_matcher(recognizer)
        self.transitions: list[Transition] = []
        self.on_enter_success: list[ActionLike] = []
        self.on_enter_failure: list[ActionLike] = []
        self.on_leave_success: list[ActionLike] = []
        self.on_leave_failure: list[ActionLike] = []
        if register:
            PageRegistry.register(self)

    def __eq__(self, other):
        return isinstance(other, Page) and self.key == other.key

    def __hash__(self):
        return hash(self.key)

    def __str__(self):
        return self.name

    def connect(
        self,
        destination: "Page",
        action: ActionLike,
        *,
        cost: float = 0.0,
        key: str | None = None,
        on_enter_success: Iterable[ActionLike] = None,
        on_enter_failure: Iterable[ActionLike] = None,
        on_leave_success: Iterable[ActionLike] = None,
        on_leave_failure: Iterable[ActionLike] = None,
    ) -> Transition:
        transition = Transition(
            source=self,
            destination=destination,
            action=action,
            cost=cost,
            key=key,
            on_enter_success=list(on_enter_success or []),
            on_enter_failure=list(on_enter_failure or []),
            on_leave_success=list(on_leave_success or []),
            on_leave_failure=list(on_leave_failure or []),
        )
        if transition.key is not None:
            self.transitions = [item for item in self.transitions if item.key != transition.key]
        self.transitions.append(transition)
        return transition

    def remove_transition(self, *, destination: "Page | None" = None, key: str | None = None) -> None:
        remained = []
        for transition in self.transitions:
            if key is not None and transition.key == key:
                continue
            if destination is not None and transition.destination == destination:
                continue
            remained.append(transition)
        self.transitions = remained

    def clear_transitions(self) -> None:
        self.transitions = []

    def hooks(self, stage: str) -> list[ActionLike]:
        return getattr(self, stage)

    def add_hooks(self, stage: str, *actions: ActionLike):
        hooks = self.hooks(stage)
        hooks.extend(action for action in actions if action is not None)
        return self

    def add_enter_success_hooks(self, *actions: ActionLike):
        return self.add_hooks("on_enter_success", *actions)

    def add_enter_failure_hooks(self, *actions: ActionLike):
        return self.add_hooks("on_enter_failure", *actions)

    def add_leave_success_hooks(self, *actions: ActionLike):
        return self.add_hooks("on_leave_success", *actions)

    def add_leave_failure_hooks(self, *actions: ActionLike):
        return self.add_hooks("on_leave_failure", *actions)

    def clone(self) -> "Page":
        page = Page(
            self.recognizer,
            key=self.key,
            name=self.name,
            category=self.category,
            priority=self.priority,
            cost=self.cost,
            register=False,
        )
        page.on_enter_success = list(self.on_enter_success)
        page.on_enter_failure = list(self.on_enter_failure)
        page.on_leave_success = list(self.on_leave_success)
        page.on_leave_failure = list(self.on_leave_failure)
        return page