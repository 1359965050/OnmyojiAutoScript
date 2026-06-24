from __future__ import annotations

from dataclasses import dataclass, field

from tasks.GameUi.page_definition import Page, Transition
from tasks.GameUi.registry import PageRegistry


@dataclass
class NavigatorSession:

    task_category: str
    current_page: Page | None = None
    edge_penalties: dict[str, float] = field(default_factory=dict)
    local_unknown_closers: list = field(default_factory=list)
    pages: dict[str, Page] = field(default_factory=dict)
    unknown_close_history: list[str] = field(default_factory=list)
    last_enter_success_page_key: str | None = None

    def bootstrap(self, pages: list[Page]) -> None:
        self.pages = self._snapshot_pages(pages)

    def _snapshot_pages(self, source_pages: list[Page]) -> dict[str, Page]:
        cloned_pages = {page.key: page.clone() for page in source_pages}
        for page in source_pages:
            cloned_page = cloned_pages[page.key]
            for transition in page.transitions:
                destination = cloned_pages.get(transition.destination.key)
                if destination is None:
                    continue
                cloned_page.connect(
                    destination,
                    transition.action,
                    cost=transition.cost,
                    key=transition.key,
                    on_enter_success=transition.on_enter_success,
                    on_enter_failure=transition.on_enter_failure,
                    on_leave_success=transition.on_leave_success,
                    on_leave_failure=transition.on_leave_failure,
                )
        return cloned_pages

    def all_pages(self, categories: set[str] = None) -> list[Page]:
        pages = list(self.pages.values())
        if not categories:
            return pages
        return [page for page in pages if page.category in categories]

    def add_page(self, page: Page) -> Page:
        current = self.pages.get(page.key)
        if current is not None:
            return current

        cloned_page = page.clone()
        self.pages[cloned_page.key] = cloned_page
        for transition in page.transitions:
            destination = self.resolve_page(transition.destination)
            if destination is None:
                destination = self.add_page(transition.destination)
            cloned_page.connect(
                destination,
                transition.action,
                cost=transition.cost,
                key=transition.key,
                on_enter_success=transition.on_enter_success,
                on_enter_failure=transition.on_enter_failure,
                on_leave_success=transition.on_leave_success,
                on_leave_failure=transition.on_leave_failure,
            )
        return cloned_page

    def resolve_page(self, page: Page | None) -> Page | None:
        if page is None:
            return None

        current = self.pages.get(page.key)
        if current is not None:
            return current

        registry_page = PageRegistry.get(page.key)
        if registry_page is not None:
            return self.add_page(registry_page)
        return None

    def add_unknown_closer(self, *actions) -> None:
        self.local_unknown_closers.extend(action for action in actions if action is not None)

    def add_penalty(self, transition: Transition, value: float = 1.0) -> float:
        self.edge_penalties[transition.key] = self.edge_penalties.get(transition.key, 0.0) + value
        return self.edge_penalties[transition.key]

    def penalty_of(self, transition: Transition) -> float:
        return self.edge_penalties.get(transition.key, 0.0)