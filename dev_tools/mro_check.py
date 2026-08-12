# This Python file uses the following encoding: utf-8
import os
import sys
import importlib

# Add project root path to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from module.logger import logger


def check_mro():
    tasks_dir = os.path.join(PROJECT_ROOT, 'tasks')
    mro_errors = []
    checked_count = 0

    logger.info("Starting MRO (Method Resolution Order) check for all task files...")

    for root, dirs, files in os.walk(tasks_dir):
        if '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                rel_path = os.path.relpath(os.path.join(root, file), PROJECT_ROOT)
                mod_name = rel_path.replace(os.sep, '.').replace('/', '.')[:-3]
                try:
                    importlib.import_module(mod_name)
                    checked_count += 1
                except TypeError as e:
                    if 'MRO' in str(e) or 'method resolution' in str(e).lower():
                        mro_errors.append((rel_path, str(e)))
                except Exception:
                    # Ignore unrelated import errors during pure MRO check
                    pass

    if mro_errors:
        logger.error(f"❌ MRO Check failed! Found {len(mro_errors)} files with invalid inheritance order:")
        for path, err in mro_errors:
            logger.error(f"  - [{path}]: {err}")
        logger.error("Fix tip: Ensure derived components (e.g., GeneralBattle) are listed BEFORE base components (e.g., GameUi).")
        sys.exit(1)
    else:
        logger.info(f"✅ MRO Check passed! Checked {checked_count} modules with zero MRO errors.")
        sys.exit(0)


if __name__ == '__main__':
    check_mro()
