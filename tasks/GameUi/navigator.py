from __future__ import annotations

import random
import time
import heapq
import inspect
from pathlib import Path
from time import sleep

from module.atom.click import RuleClick
from module.atom.gif import RuleGif
from module.atom.image import RuleImage
from module.atom.list import RuleList
from module.atom.ocr import RuleOcr
from module.base.decorator import run_once
from module.base.timer import Timer
from module.exception import GamePageUnknownError, GameNotRunningError
from module.logger import logger
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.GameUi.action import ActionSequence, ConditionalAction
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.common import infer_tasks_category_from_parts, infer_tasks_category_from_path
from tasks.GameUi.matcher import collect_rule_images
from tasks.GameUi.page_definition import Page, Transition, sort_pages_by_priority
from tasks.GameUi.registry import PageRegistry
from tasks.GameUi.session import NavigatorSession
from tasks.SixRealms.assets import SixRealmsAssets
from tasks.base_task import BaseTask


class GameUi(BaseTask, GameUiAssets):

    REPEATED_TRANSITION_FAILURE_THRESHOLD = 3

    DEFAULT_UNKNOWN_CLOSERS = [
        BaseTask.I_UI_BACK_RED,
        GameUiAssets.I_CLOSE_CHAT_WINDOW,
        ActivityShikigamiAssets.I_SKIP_BUTTON,
        BaseTask.I_UI_CONFIRM,
        SixRealmsAssets.I_EXIT_SIXREALMS,
        BaseTask.I_UI_BACK_BLUE,
        BaseTask.I_UI_BACK_YELLOW,
    ]

    def __init__(self, config, device):
        super().__init__(config, device)
        PageRegistry.load_all_pages()
        self.navigator = NavigatorSession(task_category=self._infer_task_category())
        self.navigator.bootstrap(PageRegistry.all())

    def _infer_task_category(self) -> str:
        module_parts = self.__class__.__module__.split(".")
        if "tasks" in module_parts:
            return infer_tasks_category_from_parts(
                module_parts,
                module_parts.index("tasks"),
                component_use_child=True,
            )
        try:
            class_file = Path(inspect.getfile(self.__class__)).resolve()
        except (TypeError, OSError):
            return "global"
        return infer_tasks_category_from_path(class_file, component_use_child=True)

    def _default_detect_categories(self) -> set[str]:
        return {"global", self.navigator.task_category}

    def _navigation_detect_categories(self, destination: Page) -> set[str]:
        return {"global", self.navigator.task_category, destination.category}

    def _navigation_graph_categories(self, destination: Page, current: Page | None) -> set[str]:
        categories = {"global", destination.category}
        if current is not None:
            categories.add(current.category)
        return categories

    def _invoke_callable(self, target):
        try:
            signature = inspect.signature(target)
        except (TypeError, ValueError):
            return target(self)
        if len(signature.parameters) == 0:
            return target()
        return target(self)

    def match_page_once(self, page: Page) -> bool:
        if page.recognizer is None:
            return False
        return bool(page.recognizer.evaluate(self))

    def confirm_page(self, page: Page, skip_first_screenshot: bool = True) -> bool:
        self.maybe_screenshot(skip_first_screenshot)
        if not self.match_page_once(page):
            return False
        self.screenshot()
        return self.match_page_once(page)

    def _detect_current_page(
        self,
        *,
        skip_first_screenshot: bool = True,
        categories: set[str] = None,
    ) -> Page | None:
        pages = self.navigator.all_pages(categories)
        return GameUi._detect_pages(self, pages, skip_first_screenshot=skip_first_screenshot)

    def _detect_current_page_with_fallback(
        self,
        *,
        skip_first_screenshot: bool = True,
        categories: set[str] = None,
        context: str = "current_page",
    ) -> Page | None:
        page = self._detect_current_page(
            skip_first_screenshot=skip_first_screenshot,
            categories=categories,
        )
        if page is not None or not categories:
            return page

        sorted_categories = sorted(categories)
        page = GameUi._detect_pages(
            self,
            self.navigator.all_pages(),
            skip_first_screenshot=True,
        )
        if page is not None:
            logger.attr("UI", page.name)
            return page

        logger.warning(f"Page detect miss[{context}]: scoped={sorted_categories}")
        return None

    def _detect_pages(
        self,
        pages: list[Page],
        *,
        skip_first_screenshot: bool = True,
    ) -> Page | None:
        if not pages:
            return None

        self.maybe_screenshot(skip_first_screenshot)
        GameUi._prepare_page_rule_image_cache(self, pages)
        indexed_candidates = [(index, page) for index, page in enumerate(pages) if self.match_page_once(page)]
        if not indexed_candidates:
            return None

        self.screenshot()
        GameUi._prepare_page_rule_image_cache(self, [page for _, page in indexed_candidates])
        for page in sort_pages_by_priority(indexed_candidates):
            if self.match_page_once(page):
                self.navigator.current_page = page
                logger.attr("UI", page.name)
                return page
        return None

    def _prepare_page_rule_image_cache(self, pages: list[Page]) -> None:
        targets = []
        seen = set()
        for page in pages:
            if page.recognizer is None:
                continue
            for target in collect_rule_images(page.recognizer):
                cache_key = id(target)
                if cache_key in seen:
                    continue
                seen.add(cache_key)
                targets.append(target)
        if targets:
            self._prepare_appear_cache(targets)

    @staticmethod
    def _prepare_appear_cache(targets: list) -> None:
        """
        Pre-load image resources for the given targets to warm up the cache.
        This avoids loading latency on the first match call.
        """
        for target in targets:
            if hasattr(target, 'load_image'):
                try:
                    target.load_image()
                except Exception:
                    pass

    @staticmethod
    def _action_name(action) -> str:
        if isinstance(action, (RuleImage, RuleGif, RuleOcr, RuleList, RuleClick)):
            return action.name
        if isinstance(action, ConditionalAction):
            return f"ConditionalAction({GameUi._action_name(action.action)})"
        if isinstance(action, ActionSequence):
            return f"ActionSequence[{len(action.actions)}]"
        if callable(action):
            return str(getattr(action, "__name__", action.__class__.__name__))
        return repr(action)

    def _execute_action(self, action, *, interval: float | None = None, skip_first_screenshot: bool = True) -> bool:
        self.maybe_screenshot(skip_first_screenshot)

        if isinstance(action, ConditionalAction):
            if not action.condition.evaluate(self):
                return False
            return self._execute_action(action.action, interval=interval, skip_first_screenshot=False)

        if isinstance(action, ActionSequence):
            if not action.actions:
                return False
            results = [
                self._execute_action(item, interval=interval, skip_first_screenshot=(index == 0 and skip_first_screenshot))
                for index, item in enumerate(action.actions)
            ]
            if action.success_index < len(results):
                return results[action.success_index]
            return any(results)

        if isinstance(action, (list, tuple)):
            return self._execute_action(
                ActionSequence(tuple(action)),
                interval=interval,
                skip_first_screenshot=skip_first_screenshot,
            )

        if callable(action) and not isinstance(action, (RuleImage, RuleGif, RuleOcr, RuleList, RuleClick)):
            result = self._invoke_callable(action)
            if isinstance(result, bool):
                return result
            if result is None:
                return False
            return self._execute_action(result, interval=interval, skip_first_screenshot=False)

        if isinstance(action, RuleList):
            return self.list_appear_click(action, interval=interval or 0.8)
        if isinstance(action, (RuleImage, RuleGif)):
            return self.appear_then_click(action, interval=interval)
        if isinstance(action, RuleOcr):
            return self.ocr_appear_click(action, interval=interval)
        if isinstance(action, RuleClick):
            if interval is not None:
                return self.click(action, interval=interval)
            x, y = action.coord()
            self.device.click(x=x, y=y, control_name=action.name)
            return True
        return False

    def _run_hooks(self, hooks: list, *, interval: float = 0.6) -> None:
        for index, hook in enumerate(hooks):
            self._execute_action(hook, interval=interval, skip_first_screenshot=(index == 0))

    def _mark_page_entered(self, page: Page) -> None:
        self.navigator.last_enter_success_page_key = page.key

    def _run_enter_success_hooks_if_needed(self, page: Page) -> None:
        if self.navigator.last_enter_success_page_key == page.key:
            return
        self._run_hooks(page.on_enter_success)
        self._mark_page_entered(page)

    def _allowed_pages_for_navigation(self, destination: Page, current: Page | None) -> dict[str, Page]:
        categories = self._navigation_graph_categories(destination, current)
        categories.add(self.navigator.task_category)
        pages = {page.key: page for page in self.navigator.all_pages(categories)}
        if current is not None:
            pages[current.key] = current
        pages[destination.key] = destination
        return pages

    def _build_path(self, current: Page, destination: Page) -> list[Transition]:
        if current == destination:
            return []

        allowed_pages = self._allowed_pages_for_navigation(destination, current)
        if destination.key not in allowed_pages:
            return None

        queue: list[tuple[float, int, str]] = [(0.0, 0, current.key)]
        best_cost: dict[str, float] = {current.key: 0.0}
        previous: dict[str, tuple[str, Transition]] = {}
        sequence = 0

        while queue:
            cost, _, page_key = heapq.heappop(queue)
            if cost > best_cost.get(page_key, float("inf")):
                continue
            if page_key == destination.key:
                break

            page = allowed_pages[page_key]
            for transition in page.transitions:
                next_page = transition.destination
                if next_page.key not in allowed_pages:
                    continue
                next_cost = cost + next_page.cost + transition.cost + self.navigator.penalty_of(transition)
                if next_cost >= best_cost.get(next_page.key, float("inf")):
                    continue
                best_cost[next_page.key] = next_cost
                previous[next_page.key] = (page_key, transition)
                sequence += 1
                heapq.heappush(queue, (next_cost, sequence, next_page.key))

        if destination.key not in previous:
            return None

        path: list[Transition] = []
        node_key = destination.key
        while node_key != current.key:
            prev_key, transition = previous[node_key]
            path.append(transition)
            node_key = prev_key
        path.reverse()
        return path

    def _refresh_current_page(self, destination: Page, skip_first_screenshot: bool) -> Page | None:
        current = self.navigator.current_page
        if current is not None and self.confirm_page(current, skip_first_screenshot=skip_first_screenshot):
            return current
        return self._detect_current_page_with_fallback(
            skip_first_screenshot=skip_first_screenshot,
            categories=self._navigation_detect_categories(destination),
            context="goto_page",
        )

    def _wait_for_destination(self, destination: Page, timeout: float = 4.0) -> bool:
        timer = Timer(timeout).start()
        while not timer.reached():
            if self.confirm_page(destination, skip_first_screenshot=False):
                self.navigator.current_page = destination
                return True
        return False

    def _execute_transition(self, transition: Transition) -> bool:
        source = transition.source
        destination = transition.destination

        logger.info(f"Page switch: {source} -> {destination}")

        action_timer = Timer(6.0).start()
        action_done = False
        while not action_timer.reached():
            if self._execute_action(transition.action, interval=0.8, skip_first_screenshot=False):
                action_done = True
                break

        if not action_done:
            self._run_hooks(source.on_leave_failure)
            self._run_hooks(transition.on_leave_failure)
            self._run_hooks(destination.on_enter_failure)
            self._run_hooks(transition.on_enter_failure)
            penalty = self.navigator.add_penalty(transition)
            logger.warning(f"Transition failed before leaving {source}: {transition.key}, penalty={penalty:.1f}")
            self.navigator.current_page = self._detect_current_page_with_fallback(
                skip_first_screenshot=False,
                categories=self._navigation_detect_categories(destination),
            )
            return False

        if self._wait_for_destination(destination):
            self._run_hooks(source.on_leave_success)
            self._run_hooks(transition.on_leave_success)
            self._run_hooks(destination.on_enter_success)
            self._run_hooks(transition.on_enter_success)
            self._mark_page_entered(destination)
            logger.info(f"Page arrived {destination}")
            return True

        self._run_hooks(source.on_leave_failure)
        self._run_hooks(transition.on_leave_failure)
        self._run_hooks(destination.on_enter_failure)
        self._run_hooks(transition.on_enter_failure)
        penalty = self.navigator.add_penalty(transition)
        logger.warning(f"Transition cannot reach {destination}: {transition.key}, penalty={penalty:.1f}")
        self.navigator.current_page = self._detect_current_page_with_fallback(
            skip_first_screenshot=False,
            categories=self._navigation_detect_categories(destination),
        )
        return False

    def _collect_page_check_results(self, destination: Page) -> list[str]:
        pages = self.navigator.all_pages(self._navigation_detect_categories(destination))
        self.screenshot()
        return [page.name for page in pages if self.match_page_once(page)]

    def _record_unknown_close_event(self, message: str) -> None:
        self.navigator.unknown_close_history.append(message)
        self.navigator.unknown_close_history = self.navigator.unknown_close_history[-10:]

    def _log_navigation_timeout(
        self,
        destination: Page,
        last_path_signature: tuple[str, str] | None = None,
        repeated_failure_transition_key: str | None = None,
        repeated_failure_count: int = 0,
        last_repeated_failure_close_result: str | None = None,
    ) -> None:
        current = self.navigator.current_page.name if self.navigator.current_page else "None"
        allowed_categories = sorted(self._navigation_graph_categories(destination, self.navigator.current_page))
        penalties = {
            key: value
            for key, value in sorted(self.navigator.edge_penalties.items(), key=lambda item: item[0])
            if value > 0
        }
        check_results = self._collect_page_check_results(destination)
        logger.warning("Unknown ui page or navigation stalled")
        logger.warning(f"Current page: {current}")
        logger.warning(f"Target page: {destination.name}")
        logger.warning(f"Allowed categories: {allowed_categories}")
        logger.warning(f"Current task category: {self.navigator.task_category}")
        logger.warning(f"Current page checks: {check_results}")
        logger.warning(f"Last path signature: {last_path_signature}")
        logger.warning(
            "Repeated transition failure: "
            f"key={repeated_failure_transition_key}, count={repeated_failure_count}"
        )
        logger.warning(f"Last repeated-failure close result: {last_repeated_failure_close_result}")
        logger.warning(f"Edge penalties: {penalties}")
        logger.warning(f"Unknown close history: {self.navigator.unknown_close_history}")
        raise GamePageUnknownError(f"Cannot goto page[{destination}]")

    def get_current_page(self, skip_first_screenshot: bool = True, fallback: bool = False) -> Page | None:
        if not fallback:
            return self._detect_current_page(
                skip_first_screenshot=skip_first_screenshot,
                categories=self._default_detect_categories()
            )
        return self._detect_current_page_with_fallback(
            skip_first_screenshot=skip_first_screenshot,
            categories=self._default_detect_categories(),
            context="get_current_page",
        )

    def pages_in_category(self, category: str) -> list[Page]:
        return self.navigator.all_pages({category})

    def detect_page_in(self, *targets: str | Page, include_global: bool = True) -> Page | None:
        category_set = {target for target in targets if isinstance(target, str)}
        explicit_pages: list[Page] = []
        for target in targets:
            if not isinstance(target, Page):
                continue
            page = self.navigator.resolve_page(target)
            if page is None:
                continue
            explicit_pages.append(page)

        pages: list[Page] = []
        if category_set:
            if include_global:
                category_set.add("global")
            pages.extend(self.navigator.all_pages(category_set))
        elif not explicit_pages and include_global:
            pages.extend(self.navigator.all_pages({"global"}))

        if explicit_pages:
            existed = {page.key for page in pages}
            for page in explicit_pages:
                if page.key in existed:
                    continue
                pages.append(page)
                existed.add(page.key)

        return GameUi._detect_pages(self, pages, skip_first_screenshot=True)

    def close_unknown_pages(self, skip_first_screenshot: bool = True) -> bool:
        self.maybe_screenshot(skip_first_screenshot)
        logger.warning("Try switch to a supported page")
        for action in [*self.navigator.local_unknown_closers, *self.DEFAULT_UNKNOWN_CLOSERS]:
            action_name = self._action_name(action)
            if len(self.navigator.unknown_close_history) >= 3 and \
                    self.navigator.unknown_close_history[-3:] == [action_name] * 3:
                continue
            if self._execute_action(action, interval=1.5, skip_first_screenshot=False):
                self._record_unknown_close_event(f"{action_name}")
                time.sleep(random.randrange(8, 16, 1) / 10)
                return True
        self._record_unknown_close_event(f"None")

        @run_once
        def app_check():
            if not self.device.app_is_running():
                raise GameNotRunningError("Game not running")

        @run_once
        def minicap_check():
            if self.config.script.device.control_method == "uiautomator2":
                self.device.uninstall_minicap()

        @run_once
        def rotation_check():
            self.device.get_orientation()

        app_check()
        minicap_check()
        rotation_check()
        return False

    def _finalize_arrival(self, destination: Page, confirm_wait: float, start_time: float) -> bool:
        self.navigator.current_page = destination
        self._run_enter_success_hooks_if_needed(destination)
        if confirm_wait > 0:
            Timer(confirm_wait, count=int(confirm_wait // 0.5)).start().wait()
        logger.attr(f'{time.time() - start_time:.1f}s', f"Page arrived {destination}")
        return True

    def goto_page(self, destination: Page, confirm_wait: float = 0, skip_first_screenshot: bool = True,
                  timeout: int = 30) -> bool | None:
        destination = self.navigator.resolve_page(destination) or self.navigator.add_page(destination)
        logger.hr(f"UI goto {destination}")
        start_time = time.time()
        progress_timer = Timer(timeout).start()
        last_progress_signature: tuple[str, str] | None = None
        last_detected_page_key: str | None = None
        repeated_failure_transition_key: str | None = None
        repeated_failure_count = 0
        last_repeated_failure_close_result: str | None = None

        def reset_repeated_transition_failures() -> None:
            nonlocal repeated_failure_transition_key, repeated_failure_count
            repeated_failure_transition_key = None
            repeated_failure_count = 0

        while True:
            current = self._refresh_current_page(destination, skip_first_screenshot)
            skip_first_screenshot = False

            if current is None:
                if self.close_unknown_pages(skip_first_screenshot=False):
                    progress_timer.reset()
                    last_progress_signature = ("close_unknown", destination.key)
                    last_detected_page_key = None
                    reset_repeated_transition_failures()
                elif progress_timer.reached():
                    self._log_navigation_timeout(
                        destination,
                        last_path_signature=last_progress_signature,
                        repeated_failure_transition_key=repeated_failure_transition_key,
                        repeated_failure_count=repeated_failure_count,
                        last_repeated_failure_close_result=last_repeated_failure_close_result,
                    )
                    raise GamePageUnknownError(f"Cannot goto page[{destination}]")
                continue

            if current.key != last_detected_page_key:
                self._run_enter_success_hooks_if_needed(current)
                progress_timer.reset()
                last_detected_page_key = current.key
                reset_repeated_transition_failures()

            if current == destination:
                return self._finalize_arrival(destination, confirm_wait, start_time)

            path = self._build_path(current, destination)
            if not path:
                if self.close_unknown_pages(skip_first_screenshot=False):
                    progress_timer.reset()
                    last_progress_signature = ("close_unknown", current.key)
                    reset_repeated_transition_failures()
                    continue
                if progress_timer.reached():
                    self._log_navigation_timeout(
                        destination,
                        last_path_signature=last_progress_signature,
                        repeated_failure_transition_key=repeated_failure_transition_key,
                        repeated_failure_count=repeated_failure_count,
                        last_repeated_failure_close_result=last_repeated_failure_close_result,
                    )
                continue

            path_signature = (current.key, " -> ".join(transition.key for transition in path))
            if path_signature != last_progress_signature:
                progress_timer.reset()
                last_progress_signature = path_signature
            logger.info(f"Current page: {current}. Following path:")
            logger.info(" -> ".join([current.name, *[transition.destination.name for transition in path]]))

            advanced = True
            for transition in path:
                if not self._execute_transition(transition):
                    advanced = False
                    if repeated_failure_transition_key == transition.key:
                        repeated_failure_count += 1
                    else:
                        repeated_failure_transition_key = transition.key
                        repeated_failure_count = 1
                    if repeated_failure_count % self.REPEATED_TRANSITION_FAILURE_THRESHOLD == 0:
                        close_success = self.close_unknown_pages(skip_first_screenshot=False)
                        logger.warning(f"Transition {transition.key} repeated failure close result: {close_success}")
                        if close_success:
                            progress_timer.reset()
                            last_progress_signature = ("close_unknown_after_repeated_failure", transition.key)
                            reset_repeated_transition_failures()
                    break
                progress_timer.reset()
                last_detected_page_key = transition.destination.key
                last_repeated_failure_close_result = None
                reset_repeated_transition_failures()

            if advanced and self.navigator.current_page == destination:
                return self._finalize_arrival(destination, confirm_wait, start_time)
            if progress_timer.reached():
                self._log_navigation_timeout(
                    destination,
                    last_path_signature=last_progress_signature,
                    repeated_failure_transition_key=repeated_failure_transition_key,
                    repeated_failure_count=repeated_failure_count,
                    last_repeated_failure_close_result=last_repeated_failure_close_result,
                )