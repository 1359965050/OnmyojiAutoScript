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


def collect_missing_keys(schema_path: Path | None = None) -> Tuple[Set[str], Dict[str, str], Set[str], Dict[str, str]]:
    """Return (missing_keys, titles, all_constants, i18n_content_constants)."""
    constants = parse_i18n_content_constants(I18N_CONTENT_DART)
    merged, _entries, _warnings = parse_i18n_cn(I18N_CN_DART, constants)
    actual_keys: Set[str] = set(merged.keys())

    menu_keys = parse_config_menu_keys(CONFIG_MENU) if CONFIG_MENU.exists() else set()

    schema: dict = {}
    if schema_path and schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    else:
        from module.config.config_model import ConfigModel
        schema = ConfigModel.model_json_schema()

    schema_keys = parse_schema_keys(schema, menu_keys=menu_keys)
    constant_keys: Set[str] = set(constants.values())
    expected_keys = schema_keys | menu_keys | constant_keys
    missing = expected_keys - actual_keys

    titles = collect_schema_titles(schema, menu_keys)
    return missing, titles, constant_keys, constants


def _format_entry_lines(missing: Set[str], titles: Dict[str, str], constants: Dict[str, str]) -> List[str]:
    entries: List[str] = []
    const_by_val = {const_value: name for name, const_value in constants.items()}
    for key in sorted(missing):
        value = str(titles.get(key, key))
        if "\n" in value:
            safe_val = value.replace("'''", r"\'\'\'")
            val_literal = f"'''{safe_val}'''"
        else:
            safe_val = value.replace("\\", "\\\\").replace("'", "\\'")
            val_literal = f"'{safe_val}'"
        const_name = const_by_val.get(key)
        key_literal = f"I18n.{const_name}" if const_name else f"'{key}'"
        entries.append(f"  {key_literal}: {val_literal},")
    return entries


def build_fallbacks_map(missing: Set[str], titles: Dict[str, str], constants: Dict[str, str]) -> List[str]:
    """Return the Dart lines for a new _cn_schema_fallbacks map."""
    return [
        "\nfinal Map<String, String> _cn_schema_fallbacks = {",
        *_format_entry_lines(missing, titles, constants),
        "};",
    ]


def merge_fallbacks_into_dart(
    text: str, missing: Set[str], titles: Dict[str, str], constants: Dict[str, str]
) -> str:
    """Insert missing keys into existing `_cn_schema_fallbacks` map if present, avoiding duplicate declarations."""
    entry_lines = _format_entry_lines(missing, titles, constants)
    pattern = re.compile(
        r"(final Map<String, String> _cn_schema_fallbacks = \{)(.*?)(\n\};)",
        re.DOTALL,
    )
    match = pattern.search(text)
    if match:
        existing_body = match.group(2).rstrip()
        if existing_body and not existing_body.endswith(","):
            existing_body += ","
        merged_body = existing_body + "\n" + "\n".join(entry_lines)
        return text[: match.start(2)] + merged_body + text[match.start(3) :]

    cleaned = text.rstrip() + "\n"
    return cleaned + "\n".join(build_fallbacks_map(missing, titles, constants)) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill missing schema/menu translation keys into i18n_cn.dart."
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=None,
        help="Optional path to Pydantic JSON schema (default: generate in memory from ConfigModel).",
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

    missing, titles, _constant_keys, constants = collect_missing_keys(schema_path=args.schema)

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

    text = I18N_CN_DART.read_text(encoding="utf-8")
    updated = merge_fallbacks_into_dart(text, missing, titles, constants)
    I18N_CN_DART.write_text(updated, encoding="utf-8")

    print(f"Added {len(missing)} missing keys to {I18N_CN_DART}")
    print("Run `python dev_tools/i18n_sync.py` to regenerate JSON/XML artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
