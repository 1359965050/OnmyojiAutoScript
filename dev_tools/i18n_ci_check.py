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


def main() -> int:
    # OASX-master is gitignored in this fork, so i18n_cn.dart is not available
    # in CI. Skip translation checks when the source file is missing.
    I18N_CN_DART = PROJECT_ROOT / "OASX-master" / "lib" / "config" / "translation" / "i18n_cn.dart"
    if not I18N_CN_DART.exists():
        print(
            "OASX-master/i18n_cn.dart not found (directory is gitignored). "
            "Skipping translation CI check."
        )
        return 0

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
