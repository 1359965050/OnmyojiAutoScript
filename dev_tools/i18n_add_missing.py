# This Python file uses the following encoding: utf-8
"""Add missing schema/menu translation keys to i18n_cn.dart.

This is a one-off helper to backfill keys that the validation tool reports as
missing. It tries to reuse the Chinese title from the Pydantic schema; if no
title is available it falls back to the key itself.

Safety features:
  * By default the script lists the missing keys and asks for confirmation
    before modifying i18n_cn.dart.
  * Use --dry-run to preview the changes without writing anything.
  * Use --yes to skip the confirmation prompt (useful in CI/automation).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from i18n_check import (
    CONFIG_MENU,
    I18N_CN_DART,
    I18N_CONTENT_DART,
    SCHEMA_DEFAULT,
    parse_config_menu_keys,
    parse_i18n_content_constants,
    parse_schema_keys,
)
from i18n_models import parse_i18n_cn


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def collect_schema_titles(schema: dict, menu_keys: Set[str]) -> Dict[str, str]:
    """Build a map of property/enum key -> Chinese title (or fallback)."""
    suggestions: Dict[str, str] = {}
    normalized_menu = {_normalize(k) for k in menu_keys}

    def is_task_name(name: str) -> bool:
        return _normalize(name) in normalized_menu

    def walk(node: dict) -> None:
        if not isinstance(node, dict):
            return

        title = node.get("title")
        description = node.get("description")

        if "properties" in node and isinstance(node["properties"], dict):
            for prop_name, sub in node["properties"].items():
                if is_task_name(prop_name):
                    walk(sub)
                    continue
                if prop_name not in suggestions:
                    sub_title = sub.get("title") if isinstance(sub, dict) else None
                    # Prefer the property's own title; fall back to parent's.
                    suggestions[prop_name] = sub_title or title or prop_name
                walk(sub)

        if "enum" in node and isinstance(node["enum"], list):
            for item in node["enum"]:
                if isinstance(item, str) and item not in suggestions:
                    if "." in item and item.startswith("com."):
                        continue
                    suggestions[item] = item

        for sub in node.get("$defs", {}).values():
            walk(sub)
        if "items" in node and isinstance(node["items"], dict):
            walk(node["items"])
        if "allOf" in node and isinstance(node["allOf"], list):
            for sub in node["allOf"]:
                walk(sub)

    walk(schema)
    return suggestions


def collect_missing_keys() -> Tuple[Set[str], Dict[str, str], Set[str], Dict[str, str]]:
    """Return (missing_keys, titles, all_constants, i18n_content_constants)."""
    constants = parse_i18n_content_constants(I18N_CONTENT_DART)
    merged, _entries, _warnings = parse_i18n_cn(I18N_CN_DART, constants)
    actual_keys: Set[str] = set(merged.keys())

    menu_keys = parse_config_menu_keys(CONFIG_MENU) if CONFIG_MENU.exists() else set()

    schema: dict = {}
    if SCHEMA_DEFAULT.exists():
        schema = json.loads(SCHEMA_DEFAULT.read_text(encoding="utf-8"))

    schema_keys = parse_schema_keys(schema, menu_keys=menu_keys)
    constant_keys: Set[str] = set(constants.values())
    expected_keys = schema_keys | menu_keys | constant_keys
    missing = expected_keys - actual_keys

    titles = collect_schema_titles(schema, menu_keys)
    return missing, titles, constant_keys, constants


def build_fallbacks_map(missing: Set[str], titles: Dict[str, str], constants: Dict[str, str]) -> List[str]:
    """Return the Dart lines for a new _cn_schema_fallbacks map."""
    lines = ["\nfinal Map<String, String> _cn_schema_fallbacks = {"]
    for key in sorted(missing):
        value = titles.get(key, key)
        # Escape single quotes for Dart.
        value = value.replace("'", "\\'")
        # Use I18n constant if one exists for this key, otherwise string literal.
        const_name = None
        for name, const_value in constants.items():
            if const_value == key:
                const_name = name
                break
        key_literal = f"I18n.{const_name}" if const_name else f"'{key}'"
        lines.append(f"  {key_literal}: '{value}',")
    lines.append("};")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill missing schema/menu translation keys into i18n_cn.dart."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the missing keys and the generated map without modifying i18n_cn.dart.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt and write changes directly.",
    )
    args = parser.parse_args(argv)

    missing, titles, _constant_keys, constants = collect_missing_keys()

    if not missing:
        print("No missing keys.")
        return 0

    lines = build_fallbacks_map(missing, titles, constants)

    print(f"Found {len(missing)} missing keys:")
    for key in sorted(missing):
        value = titles.get(key, key)
        print(f"  - {key}: {value!r}")
    print()

    if args.dry_run:
        print("Generated fallback map (dry run, no file modified):")
        print("\n".join(lines))
        return 0

    if not args.yes:
        answer = input(f"Add {len(missing)} missing keys to {I18N_CN_DART}? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Aborted.")
            return 1

    # Append the new map before the final blank line / end of file.
    text = I18N_CN_DART.read_text(encoding="utf-8")
    # Remove trailing whitespace and ensure one trailing newline.
    text = text.rstrip() + "\n"
    text += "\n".join(lines) + "\n"
    I18N_CN_DART.write_text(text, encoding="utf-8")

    print(f"Added {len(missing)} missing keys to {I18N_CN_DART}")
    print("Run `python dev_tools/i18n_sync.py` to regenerate JSON/XML artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
