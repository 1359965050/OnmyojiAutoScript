# -*- coding: utf-8 -*-
import sys
import io
import importlib
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def scan_all_python_files():
    root = PROJECT_ROOT / 'tasks'
    py_files = list(root.rglob('*.py'))
    failed = []
    
    for p in py_files:
        rel = p.relative_to(PROJECT_ROOT)
        mod_str = '.'.join(rel.with_suffix('').parts)
        try:
            importlib.import_module(mod_str)
        except Exception as e:
            failed.append((mod_str, str(e)))
            
    print(f"Scanned {len(py_files)} Python modules under tasks/")
    print(f"Failed imports: {len(failed)}")
    if failed:
        for mod, err in failed:
            print(f"  - {mod}: {err}")
    else:
        print("ALL Python modules under tasks/ imported successfully without any syntax or dependency errors!")

if __name__ == '__main__':
    scan_all_python_files()
