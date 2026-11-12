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
    import_errors = []
    checked_modules = set()

    logger.info("Starting MRO (Method Resolution Order) check for all task files...")

    for root, dirs, files in os.walk(tasks_dir):
        if '__pycache__' in root:
            continue
        for file in sorted(files):
            if not file.endswith('.py'):
                continue
            rel_path = os.path.relpath(os.path.join(root, file), PROJECT_ROOT)
            if file == '__init__.py':
                mod_name = os.path.relpath(root, PROJECT_ROOT).replace(os.sep, '.').replace('/', '.')
            else:
                mod_name = rel_path.replace(os.sep, '.').replace('/', '.')[:-3]
            if mod_name in checked_modules:
                continue
            checked_modules.add(mod_name)
            try:
                importlib.import_module(mod_name)
            except TypeError as e:
                err_text = str(e)
                if 'MRO' in err_text or 'method resolution' in err_text.lower():
                    mro_errors.append((rel_path, err_text))
                else:
                    import_errors.append((rel_path, f"TypeError: {err_text}"))
            except Exception as e:
                import_errors.append((rel_path, f"{type(e).__name__}: {e}"))

    if mro_errors or import_errors:
        if mro_errors:
            logger.error(f"[FAIL] MRO Check failed! Found {len(mro_errors)} files with invalid inheritance order:")
            for path, err in mro_errors:
                logger.error(f"  - [{path}]: {err}")
            logger.error("Fix tip: Ensure derived components (e.g., GeneralBattle) are listed BEFORE base components (e.g., GameUi).")
        if import_errors:
            logger.error(f"[FAIL] Module import failed in {len(import_errors)} files during MRO check:")
            for path, err in import_errors:
                logger.error(f"  - [{path}]: {err}")
        sys.exit(1)
    else:
        logger.info(f"[PASS] MRO Check passed! Checked {len(checked_modules)} modules with zero MRO errors.")
        sys.exit(0)


if __name__ == '__main__':
    check_mro()
