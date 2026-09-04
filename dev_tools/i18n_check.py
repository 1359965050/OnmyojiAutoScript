# This Python file uses the following encoding: utf-8
"""Validate OAS translations against the actual config schema and menu.

Usage:
    python dev_tools/i18n_check.py
    python dev_tools/i18n_check.py --schema schema_debug.json
    python dev_tools/i18n_check.py --check-redundant
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Ensure sibling dev_tools modules are importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from i18n_models import parse_i18n_cn, parse_i18n_content_constants


PROJECT_ROOT = Path(__file__).resolve().parent.parent

I18N_CN_DART = (
    PROJECT_ROOT / "OASX-master" / "lib" / "config" / "translation" / "i18n_cn.dart"
)
I18N_CONTENT_DART = (
    PROJECT_ROOT / "OASX-master" / "lib" / "config" / "translation" / "i18n_content.dart"
)
SCHEMA_DEFAULT = PROJECT_ROOT / "schema_debug.json"
CONFIG_MENU = PROJECT_ROOT / "module" / "config" / "config_menu.py"


def _looks_like_translation_key(value: str) -> bool:
    """Return True if a schema string is likely a translation key.

    Hard-coded Chinese labels or long sentences are displayed as-is and do not
    need an entry in i18n_cn.dart. English identifiers, enum values and help
    keys (e.g. "limit_count", "limit_count_help", "ADB") do.
    """
    if not value:
        return False
    value = value.strip()
    if not value:
        return False
    # Skip strings that contain CJK characters: they are already Chinese text.
    if any(unicodedata.category(ch).startswith("Lo") and "CJK" in unicodedata.name(ch, "") for ch in value):
        return False
    # Skip long sentences / paragraphs that are clearly help text.
    if len(value) > 60:
        return False
    return True


def _normalize_key(value: str) -> str:
    """Normalize a key for case-insensitive comparison.

    'Soul Zones', 'soul_zones' and 'soulzones' should be treated as the same
    conceptual key.
    """
    return re.sub(r"[^a-z0-9]", "", value.lower())


def parse_schema_keys(schema: dict, menu_keys: Set[str] | None = None) -> Set[str]:
    """Collect translation keys that appear in a Pydantic JSON schema.

    Keys include:
      - object titles (task / group names) when they look like keys
      - property titles (field labels) when they look like keys
      - property descriptions (help text keys)
      - enum values
      - property names themselves, when they are used as translation keys

    Task-level property names (e.g. "orochi") are skipped when they match a
    menu key, because the actual translation key is the menu name ("Orochi").
    """
    keys: Set[str] = set()
    menu_keys = menu_keys or set()
    normalized_menu_keys = {_normalize_key(k) for k in menu_keys}

    def add(value: str | None) -> None:
        if not value:
            return
        value = value.strip()
        if not _looks_like_translation_key(value):
            return
        # Android package names are identifiers, not translation keys.
        if "." in value and value.startswith("com."):
            return
        keys.add(value)

    def is_task_name(prop_name: str) -> bool:
        return _normalize_key(prop_name) in normalized_menu_keys

    def walk(node: dict) -> None:
        if not isinstance(node, dict):
            return

        # Titles in this project are either hard-coded Chinese labels or
        # auto-generated from field/class names (e.g. "Limit Count"). They are
        # not used as translation keys, so we skip them.

        # Description is either a help-text key or literal help text.
        if "description" in node and isinstance(node["description"], str):
            add(node["description"])

        # Enum values are often shown in dropdowns and translated via .tr.
        if "enum" in node and isinstance(node["enum"], list):
            for item in node["enum"]:
                if isinstance(item, str):
                    add(item)

        # Property names themselves are frequently used as translation keys
        # (e.g. "limit_count", "enable"). Task names are covered by menu keys.
        if "properties" in node and isinstance(node["properties"], dict):
            for prop_name, sub in node["properties"].items():
                if not is_task_name(prop_name):
                    add(prop_name)
                walk(sub)

        # Recurse into nested structures.
        for sub in node.get("$defs", {}).values():
            walk(sub)
        if "items" in node and isinstance(node["items"], dict):
            walk(node["items"])
        if "allOf" in node and isinstance(node["allOf"], list):
            for sub in node["allOf"]:
                walk(sub)

    walk(schema)
    return keys


def parse_config_menu_keys(file_path: Path) -> Set[str]:
    """Extract menu names and task names from ConfigMenu.

    The menu structure uses English identifiers like 'Orochi' and 'Soul Zones'.
    These identifiers are used as translation keys in i18n_cn.dart.
    """
    keys: Set[str] = set()
    text = file_path.read_text(encoding="utf-8")

    # Match lines like: self.menu["Soul Zones"] = ['Orochi', 'Sougenbi', ...]
    for line in text.splitlines():
        match = re.search(r'self\.menu\[["\']([^"\']+)["\']\]\s*=\s*(.+)', line)
        if not match:
            continue
        menu_name = match.group(1)
        keys.add(menu_name)
        rest = match.group(2)
        for task in re.findall(r'[\"\']([^"\']+)[\"\']', rest):
            keys.add(task)

    return keys


def parse_i18n_content_keys(file_path: Path) -> Set[str]:
    """Return all constant *values* defined in i18n_content.dart."""
    constants = parse_i18n_content_constants(file_path)
    return set(constants.values())


def classify_missing(
    missing: Set[str],
    schema_keys: Set[str],
    menu_keys: Set[str],
    constant_keys: Set[str],
) -> Dict[str, List[str]]:
    """Group missing keys by their source for easier fixing."""
    result: Dict[str, List[str]] = {
        "schema": [],
        "menu": [],
        "constants": [],
        "other": [],
    }

    for key in sorted(missing):
        if key in schema_keys:
            result["schema"].append(key)
        elif key in menu_keys:
            result["menu"].append(key)
        elif key in constant_keys:
            result["constants"].append(key)
        else:
            result["other"].append(key)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate OAS Chinese translations against schema and menus."
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=SCHEMA_DEFAULT,
        help="Path to Pydantic JSON schema (default: schema_debug.json).",
    )
    parser.add_argument(
        "--check-redundant",
        action="store_true",
        help="Also report keys present in i18n_cn.dart but unused in schema/menu.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output report as JSON instead of human-readable text.",
    )
    args = parser.parse_args()

    if not I18N_CN_DART.exists():
        print(f"Source file not found: {I18N_CN_DART}", file=sys.stderr)
        return 1

    # Load actual translation keys from the single source of truth.
    constants = parse_i18n_content_constants(I18N_CONTENT_DART)
    merged, entries, warnings = parse_i18n_cn(I18N_CN_DART, constants)
    actual_keys: Set[str] = set(merged.keys())

    # Load expected keys from schema, menu and constants.
    menu_keys = parse_config_menu_keys(CONFIG_MENU) if CONFIG_MENU.exists() else set()

    schema: dict = {}
    schema_keys: Set[str] = set()
    if args.schema.exists():
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        schema_keys = parse_schema_keys(schema, menu_keys=menu_keys)
    else:
        print(f"Schema file not found: {args.schema}", file=sys.stderr)

    constant_keys = parse_i18n_content_keys(I18N_CONTENT_DART)

    expected_keys = schema_keys | menu_keys | constant_keys

    # Build reports.
    collisions = [w for w in warnings if w.startswith("Collision:")]
    duplicates = [w for w in warnings if w.startswith("Duplicate:")]
    missing = expected_keys - actual_keys
    redundant = actual_keys - expected_keys if args.check_redundant else set()

    has_error = bool(missing or collisions)

    report = {
        "summary": {
            "total_actual_keys": len(actual_keys),
            "total_expected_keys": len(expected_keys),
            "missing_count": len(missing),
            "redundant_count": len(redundant),
            "collision_count": len(collisions),
            "duplicate_count": len(duplicates),
        },
        "missing": classify_missing(missing, schema_keys, menu_keys, constant_keys),
        "redundant": sorted(redundant),
        "collisions": collisions,
        "duplicates": duplicates,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if has_error else 0

    # Human-readable output.
    s = report["summary"]
    print("=" * 60)
    print("OAS Translation Check Report")
    print("=" * 60)
    print(f"Actual keys in i18n_cn.dart : {s['total_actual_keys']}")
    print(f"Expected keys from schema/menu: {s['total_expected_keys']}")
    print(f"Missing keys                : {s['missing_count']}")
    print(f"Redundant keys              : {s['redundant_count']}")
    print(f"Collisions (same key, diff value): {s['collision_count']}")
    print(f"Duplicates (same key, same value): {s['duplicate_count']}")
    print("=" * 60)

    if missing:
        print("\n[Missing translations]")
        for category, items in report["missing"].items():
            if not items:
                continue
            print(f"\n  {category}:")
            for item in items:
                print(f"    - {item}")

    if args.check_redundant and redundant:
        print("\n[Redundant translations (present in i18n_cn.dart but unused)]")
        for item in redundant:
            print(f"    - {item}")

    if collisions:
        print("\n[Collisions in i18n_cn.dart]")
        for item in collisions:
            print(f"    - {item}")

    if duplicates:
        print("\n[Duplicates in i18n_cn.dart]")
        for item in duplicates:
            print(f"    - {item}")

    if not has_error:
        print("\n[OK] No missing translations or collisions.")

    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
