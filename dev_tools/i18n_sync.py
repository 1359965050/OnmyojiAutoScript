# This Python file uses the following encoding: utf-8
"""Generate runtime translation files from the single source of truth.

Source of truth:
    OASX-master/lib/config/translation/i18n_cn.dart
    OASX-master/lib/config/translation/i18n_us.dart

Generated files:
    module/config/i18n/zh-CN.json
    assets/i18n/zh-CN.json
    module/config/i18n/en-US.json
    assets/i18n/en-US.json
    module/config/i18n/zh_CN.xml

After editing i18n_cn.dart or i18n_us.dart, run:

    python dev_tools/i18n_sync.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

# Ensure sibling dev_tools modules are importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from i18n_models import (
    parse_i18n_cn,
    parse_i18n_content_constants,
    parse_i18n_us,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

I18N_CN_DART = PROJECT_ROOT / "OASX-master" / "lib" / "config" / "translation" / "i18n_cn.dart"
I18N_US_DART = PROJECT_ROOT / "OASX-master" / "lib" / "config" / "translation" / "i18n_us.dart"
I18N_CONTENT_DART = (
    PROJECT_ROOT / "OASX-master" / "lib" / "config" / "translation" / "i18n_content.dart"
)

OUTPUT_JSON_BACKEND = PROJECT_ROOT / "module" / "config" / "i18n" / "zh-CN.json"
OUTPUT_JSON_ASSETS = PROJECT_ROOT / "assets" / "i18n" / "zh-CN.json"
OUTPUT_US_JSON_BACKEND = PROJECT_ROOT / "module" / "config" / "i18n" / "en-US.json"
OUTPUT_US_JSON_ASSETS = PROJECT_ROOT / "assets" / "i18n" / "en-US.json"
OUTPUT_XML = PROJECT_ROOT / "module" / "config" / "i18n" / "zh_CN.xml"


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)
    path.write_text(text + "\n", encoding="utf-8")


def build_xml(merged: dict, entries: list) -> str:
    """Build a Qt TS file grouped by origin map name.

    The XML is kept as a generated legacy artifact; it is no longer edited
    by hand. Each `_cn_*` Dart map becomes a `<context>`.
    """
    ts = ET.Element("TS", version="2.1", language="zh_CN")

    # Preserve first-appearance order of contexts.
    contexts: dict[str, list[tuple[str, str]]] = {}
    for entry in entries:
        contexts.setdefault(entry.map_name, []).append((entry.key, entry.value))

    for context_name, messages in contexts.items():
        context = ET.SubElement(ts, "context")
        name_el = ET.SubElement(context, "name")
        name_el.text = context_name
        seen: set[str] = set()
        for key, value in messages:
            # Within a context, keep only the first occurrence of a key.
            if key in seen:
                continue
            seen.add(key)
            message = ET.SubElement(context, "message")
            source = ET.SubElement(message, "source")
            source.text = key
            translation = ET.SubElement(message, "translation")
            translation.text = value

    # Pretty-print with the declaration used by the original file.
    rough = ET.tostring(ts, encoding="unicode")
    pretty = minidom.parseString(rough).toprettyxml(indent="    ", encoding="utf-8")
    # toprettyxml returns bytes when encoding is given.
    return pretty.decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync translation runtime files from i18n_cn.dart"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with non-zero status if generated files would change.",
    )
    args = parser.parse_args()

    if not I18N_CN_DART.exists():
        print(f"Source file not found: {I18N_CN_DART}", file=sys.stderr)
        return 1

    constants = parse_i18n_content_constants(I18N_CONTENT_DART)
    merged, entries, warnings = parse_i18n_cn(I18N_CN_DART, constants)

    if warnings:
        print("Warnings from i18n_cn.dart:", file=sys.stderr)
        for warning in warnings:
            print(f"  {warning}", file=sys.stderr)

    us_merged, us_entries, us_warnings = parse_i18n_us(I18N_US_DART, constants)
    if us_warnings:
        print("Warnings from i18n_us.dart:", file=sys.stderr)
        for warning in us_warnings:
            print(f"  {warning}", file=sys.stderr)

    if args.check:
        changed = False
        for path, content in (
            (OUTPUT_JSON_BACKEND, json.dumps(merged, ensure_ascii=False, indent=2)),
            (OUTPUT_JSON_ASSETS, json.dumps(merged, ensure_ascii=False, indent=2)),
            (OUTPUT_US_JSON_BACKEND, json.dumps(us_merged, ensure_ascii=False, indent=2)),
            (OUTPUT_US_JSON_ASSETS, json.dumps(us_merged, ensure_ascii=False, indent=2)),
            (OUTPUT_XML, build_xml(merged, entries)),
        ):
            if not path.exists() or path.read_text(encoding="utf-8").strip() != content.strip():
                changed = True
                print(f"Would change: {path}", file=sys.stderr)
        return 1 if changed else 0

    write_json(OUTPUT_JSON_BACKEND, merged)
    write_json(OUTPUT_JSON_ASSETS, merged)
    write_json(OUTPUT_US_JSON_BACKEND, us_merged)
    write_json(OUTPUT_US_JSON_ASSETS, us_merged)

    OUTPUT_XML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_XML.write_text(build_xml(merged, entries), encoding="utf-8")

    print(f"Generated {OUTPUT_JSON_BACKEND}")
    print(f"Generated {OUTPUT_JSON_ASSETS}")
    print(f"Generated {OUTPUT_US_JSON_BACKEND}")
    print(f"Generated {OUTPUT_US_JSON_ASSETS}")
    print(f"Generated {OUTPUT_XML}")
    print(f"Total zh-CN keys: {len(merged)}")
    print(f"Total en-US keys: {len(us_merged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
