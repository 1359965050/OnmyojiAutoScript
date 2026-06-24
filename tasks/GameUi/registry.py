from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tasks.GameUi.page_definition import Page


class PageRegistry:

    _pages: dict[str, "Page"] = {}
    _loaded_modules: set[str] = set()
    _page_modules_loaded = False

    @classmethod
    def register(cls, page: "Page") -> "Page":
        cls._pages[page.key] = page
        return page

    @classmethod
    def get(cls, key: str) -> "Page | None":
        return cls._pages.get(key)

    @classmethod
    def all(cls, categories: set[str] = None) -> list["Page"]:
        pages = list(cls._pages.values())
        if not categories:
            return pages
        return [page for page in pages if page.category in categories]

    @classmethod
    def load_all_pages(cls) -> None:
        if cls._page_modules_loaded:
            return
        base_dir = Path(__file__).resolve().parent.parent
        for task_dir in base_dir.iterdir():
            if not task_dir.is_dir():
                continue
            for module_name in ("page"):
                module_file = task_dir / f"{module_name}.py"
                if not module_file.exists():
                    continue
                import_name = f"tasks.{task_dir.name}.{module_name}"
                if import_name in cls._loaded_modules:
                    continue
                importlib.import_module(import_name)
                cls._loaded_modules.add(import_name)
        cls._page_modules_loaded = True