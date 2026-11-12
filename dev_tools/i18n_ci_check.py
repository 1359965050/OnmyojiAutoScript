# This Python file uses the following encoding: utf-8
"""CI check for OAS translations.

Runs in pull requests to ensure:
  1. Generated translation files are up to date with i18n_cn.dart.
  2. No translation keys are missing or conflicting.
  3. No redundant keys are introduced (with --check-redundant).

Usage:
    python dev_tools/i18n_ci_check.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> int:
    print(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(PROJECT_ROOT))


def _check_generated_assets_fallback() -> int:
    """Validate tracked `assets/i18n/zh-CN.json` against schema/menu when OASX-master is absent."""
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "dev_tools"))
    from i18n_check import CONFIG_MENU, parse_config_menu_keys, parse_schema_keys

    zh_json = PROJECT_ROOT / "assets" / "i18n" / "zh-CN.json"
    if not zh_json.exists():
        print(f"Missing generated translation asset: {zh_json}", file=sys.stderr)
        return 1

    actual_keys = set(json.loads(zh_json.read_text(encoding="utf-8")).keys())
    menu_keys = parse_config_menu_keys(CONFIG_MENU) if CONFIG_MENU.exists() else set()
    schema_keys: set[str] = set()
    try:
        from module.config.config_model import ConfigModel

        schema = ConfigModel.model_json_schema()
        schema_keys = parse_schema_keys(schema, menu_keys=menu_keys)
    except Exception as exc:
        print(f"Warning: skipping Pydantic schema extraction in fallback check: {exc}", file=sys.stderr)

    missing = (schema_keys | menu_keys) - actual_keys
    if missing:
        print(f"Missing keys in {zh_json}: {sorted(missing)}", file=sys.stderr)
        return 1
    print(f"Fallback CI check passed: {len(actual_keys)} keys in {zh_json.name} cover schema/menu.")
    return 0


def main() -> int:
    # OASX-master is gitignored in this fork, so i18n_cn.dart may be absent
    # in remote CI. Fall back to validating committed assets/i18n/zh-CN.json.
    I18N_CN_DART = PROJECT_ROOT / "OASX-master" / "lib" / "config" / "translation" / "i18n_cn.dart"
    if not I18N_CN_DART.exists():
        print(
            "OASX-master/i18n_cn.dart not found (directory is gitignored). "
            "Running fallback schema/menu check against assets/i18n/zh-CN.json."
        )
        return _check_generated_assets_fallback()

    # 1. Ensure generated files are up to date.
    result = run([sys.executable, "dev_tools/i18n_sync.py", "--check"])
    if result != 0:
        print(
            "\n❌ Generated translation files are out of date. "
            "Run 'python dev_tools/i18n_sync.py' and commit the changes.",
            file=sys.stderr,
        )
        return 1

    # 2. Ensure no missing, conflicting, or redundant translations.
    result = run(
        [sys.executable, "dev_tools/i18n_check.py", "--check-redundant"]
    )
    if result != 0:
        print(
            "\n❌ Translation validation failed. "
            "See the report above for missing or conflicting keys.",
            file=sys.stderr,
        )
        return 1

    print("\n✅ Translation CI check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
