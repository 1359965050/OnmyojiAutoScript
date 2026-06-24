from __future__ import annotations

import time
from collections import deque
from pathlib import Path

from module.atom.click import RuleClick
from module.atom.gif import RuleGif
from module.atom.image import RuleImage
from module.atom.list import RuleList
from module.atom.ocr import RuleOcr
from module.base.decorator import run_once
from module.base.timer import Timer
from module.exception import GameNotRunningError, GamePageUnknownError
from module.logger import logger
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.navigator import GameUi as NewGameUi
from tasks.GameUi.page import Page, PageRegistry, page_main, random_click
from tasks.Restart.assets import RestartAssets
from tasks.SixRealms.assets import SixRealmsAssets
from tasks.base_task import BaseTask


class GameUi(NewGameUi):

    ui_current: Page = None

    def __init__(self, config, device):
        super().__init__(config, device)

    @property
    def ui_pages(self) -> list[Page]:
        return self.navigator.all_pages()

    def ui_page_appear(self, page: Page, skip_first_screenshot: bool = True, interval: float = None):
        self.maybe_screenshot(skip_first_screenshot)
        if isinstance(page.check_button, list):
            for button in page.check_button:
                if self.appear(button, interval):
                    return True
            return False
        return self.appear(page.check_button, interval)

    def ui_wait_until_appear(self, page: Page, timeout: float = 5, interval: float = 0.5,
                             skip_first_screenshot: bool = True) -> bool:
        logger.info(f'Waiting for {page}')
        timeout_timer = Timer(timeout).start()
        while not timeout_timer.reached():
            if self.ui_page_appear(page, skip_first_screenshot, interval=interval):
                return True
            skip_first_screenshot = False
        return False

    def ui_get_current_page(self, skip_first_screenshot=True) -> Page:
        logger.info("UI get current page")

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

        timeout = Timer(10, count=20).start()
        while 1:
            self.maybe_screenshot(skip_first_screenshot)
            skip_first_screenshot = False
            if timeout.reached():
                break
            for page in self.ui_pages:
                if not page.check_button:
                    continue
                if self.ui_page_appear(page=page, interval=None):
                    logger.attr("UI", page.name)
                    self.ui_current = page
                    return page
            if self.try_close_unknown_page():
                timeout = Timer(10, count=20).start()
            else:
                self.click(random_click(), interval=4)
            time.sleep(0.3)
            app_check()
            minicap_check()
            rotation_check()
        logger.warning("Unknown ui page")
        logger.attr("EMULATOR__SCREENSHOT_METHOD", self.config.script.device.screenshot_method)
        logger.attr("EMULATOR__CONTROL_METHOD", self.config.script.device.control_method)
        logger.warning("Starting from current page is not supported")
        logger.warning(f"Supported page: {[str(page) for page in self.ui_pages]}")
        logger.warning('Supported page: Any page with a "HOME" button on the upper-right')
        logger.critical("Please switch to a supported page before starting oas")
        raise GamePageUnknownError

    def build_reverse_path_dict(self, destination: Page) -> dict[Page, list[Page]]:
        paths = {destination: [destination]}
        queue = deque([destination])
        while queue:
            cur = queue.popleft()
            for page in self.ui_pages:
                if page not in paths and cur in page.links:
                    paths[page] = [page] + paths[cur]
                    queue.append(page)
        return paths

    def build_reverse_paths(self, destination: Page) -> list[tuple[Page, list[Page]]]:
        paths = self.build_reverse_path_dict(destination)
        sorted_paths = sorted(paths.items(), key=lambda kv: len(kv[1]))
        return sorted_paths

    def ui_goto_page(self, dest_page: Page, confirm_wait=0, skip_first_screenshot=True, timeout: int = 60) -> bool:
        self.ui_get_current_page()
        return self.ui_goto(dest_page, confirm_wait, skip_first_screenshot, timeout)

    def ui_goto(self, destination: Page, confirm_wait=0, skip_first_screenshot=True, timeout: int = 60) -> bool:
        logger.hr(f"UI goto {destination}")
        timeout_timer = Timer(timeout).start()
        confirm_timer = Timer(confirm_wait, count=int(confirm_wait // 0.5)).start()
        close_unknown_timer = Timer(3).start()
        path_dict = self.build_reverse_path_dict(destination)

        found = False
        while not timeout_timer.reached():
            if found:
                confirm_timer.wait()
                return True
            confirm_timer.reset()
            path = path_dict.get(self.ui_current, None)
            if not path:
                self.ui_get_current_page(skip_first_screenshot)
                continue
            skip_first_screenshot = False
            logger.info(f"Current page: {self.ui_current}. Following shortest path:")
            show_paths: str = ' -> '.join([p.name for p in path])
            logger.info(f"{show_paths}")
            found = self._execute_path(path, timeout_timer)
            if not found:
                if close_unknown_timer.reached_and_reset():
                    self.try_close_unknown_page(skip_screenshot=False)
                    self.ui_current = None
        else:
            logger.error(f'Cannot goto page[{destination}], timeout[{timeout}s] reached')
        return False

    def try_close_unknown_page(self, skip_screenshot: bool = True):
        self.maybe_screenshot(skip_screenshot)
        timer = Timer(None).start()
        for close in self.ui_close:
            if self.appear_then_click(close, interval=1.5):
                logger.warning('Trying to switch to supported page')
                logger.info(f'[{timer.current():.1f}s]Click {close} on {self.ui_current} success')
                return True
        return False

    def _execute_path(self, path: list, timeout_timer):
        for i, current_page in enumerate(path):
            if timeout_timer.reached():
                return False
            if self.ui_current != current_page:
                continue
            self.run_additional(current_page, interval=0.6, skip_first_screenshot=False)
            if i == len(path) - 1:
                if len(path) == 1:
                    logger.info(f'Page arrived {current_page}')
                break
            next_page = path[i + 1]
            logger.info(f'Page switch: {current_page} -> {next_page}')
            button = current_page.links.get(next_page)
            if not button:
                logger.warning(f"No link from {current_page} to {next_page}")
                continue
            max_wait_timer = Timer(6).start()
            logger.info(f'Wait appear and operate {button} on {current_page}')
            while not max_wait_timer.reached():
                if timeout_timer.reached():
                    return False
                if isinstance(button, list):
                    exec_operates = [self.appear_then_operate(btn, interval=0.8, skip_first_screenshot=False)
                                     for btn in button]
                    if exec_operates[0]:
                        break
                if self.appear_then_operate(button, interval=0.8, skip_first_screenshot=False):
                    break
            else:
                logger.warning(f'Failed recognize {button} on {current_page}')
                self.ui_get_current_page(skip_first_screenshot=False)
                if self.ui_current != current_page:
                    continue
            max_wait_timer.reset()
            while not max_wait_timer.reached():
                if timeout_timer.reached():
                    return False
                if self.ui_wait_until_appear(next_page, timeout=2.5, skip_first_screenshot=False):
                    logger.info(f'[{max_wait_timer.current():.1f}s]Page arrived {next_page}')
                    self.ui_current = next_page
                    break
            else:
                self.ui_get_current_page(skip_first_screenshot=False)
        return self.ui_current == path[-1]

    def run_additional(self, page: Page, interval: float = None, skip_first_screenshot: bool = True):
        if not page.additional:
            return
        for btn in page.additional:
            if isinstance(btn, list) and len(btn) == 2:
                condition, action = btn
                self.maybe_screenshot(skip_first_screenshot)
                if self.appear(condition):
                    if self.appear_then_operate(action, interval=interval, skip_first_screenshot=False):
                        logger.info(f'Page {page} additional conditional {condition} -> {action} executed')
                        skip_first_screenshot = False
            elif self.appear_then_operate(btn, interval=interval, skip_first_screenshot=skip_first_screenshot):
                logger.info(f'Page {page} additional {btn} clicked')
                skip_first_screenshot = False

    def appear_then_operate(self, target: RuleList | RuleImage | RuleGif | RuleOcr | RuleClick,
                            interval: float = None, skip_first_screenshot: bool = True):
        self.maybe_screenshot(skip_first_screenshot)
        operated = False
        if isinstance(target, RuleList):
            operated = self.list_appear_click(target, interval=interval)
        elif isinstance(target, (RuleImage, RuleGif)):
            operated = self.appear_then_click(target, interval=interval)
        elif isinstance(target, RuleOcr):
            operated = self.ocr_appear_click(target, interval=interval)
        elif isinstance(target, RuleClick):
            operated = self.click(target, interval=interval)
        return operated