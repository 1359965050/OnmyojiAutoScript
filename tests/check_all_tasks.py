# -*- coding: utf-8 -*-
import sys
import os
import io
import importlib
import traceback
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np

# 避免 Windows 编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from module.config.config import Config
from module.device.device import Device
from tasks.base_task import BaseTask


def check_assets_exist(task_dir: Path):
    """检查任务目录下的 assets.py 中引用的图片路径是否存在"""
    assets_file = task_dir / "assets.py"
    if not assets_file.exists():
        return []
    
    missing = []
    try:
        mod_name = f"tasks.{task_dir.name}.assets"
        mod = importlib.import_module(mod_name)
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if hasattr(obj, "file") and getattr(obj, "file", None):
                file_path = getattr(obj, "file")
                if isinstance(file_path, str):
                    p = PROJECT_ROOT / file_path.lstrip("./\\")
                    if not p.exists():
                        missing.append((attr_name, file_path))
    except Exception as e:
        missing.append(("MODULE_ERROR", str(e)))
    return missing


def test_all_tasks():
    tasks_dir = PROJECT_ROOT / "tasks"
    task_subdirs = [d for d in tasks_dir.iterdir() if d.is_dir() and not d.name.startswith("__")]
    
    print(f"Checking {len(task_subdirs)} potential task folders in tasks/\n")
    
    config = Config("template")
    
    # 构造 mock device
    mock_device = MagicMock(spec=Device)
    # 提供一个空的 1280x720 图像用于 mock 截图
    dummy_img = np.zeros((720, 1280, 3), dtype=np.uint8)
    mock_device.image = dummy_img
    mock_device.screenshot.return_value = dummy_img
    mock_device.click.return_value = True
    mock_device.swipe.return_value = True
    
    results = {
        "passed": [],
        "failed_import": [],
        "failed_init": [],
        "missing_script_task": [],
        "missing_assets": {},
        "mro_errors": []
    }
    
    for task_dir in sorted(task_subdirs):
        task_name = task_dir.name
        script_file = task_dir / "script_task.py"
        
        # 1. 检查 assets 资源是否存在
        missing_assets = check_assets_exist(task_dir)
        if missing_assets:
            results["missing_assets"][task_name] = missing_assets
        
        if not script_file.exists():
            results["missing_script_task"].append(task_name)
            continue
            
        module_path = f"tasks.{task_name}.script_task"
        try:
            mod = importlib.import_module(module_path)
        except Exception as e:
            err_msg = traceback.format_exc()
            print(f"[FAIL IMPORT] {task_name}: {e}")
            results["failed_import"].append((task_name, err_msg))
            continue
            
        script_task_cls = getattr(mod, "ScriptTask", None)
        if script_task_cls is None:
            print(f"[NO ScriptTask] {task_name}")
            results["missing_script_task"].append(task_name)
            continue
            
        # 2. 验证 MRO
        try:
            mro = script_task_cls.mro()
        except TypeError as e:
            print(f"[MRO ERROR] {task_name}: {e}")
            results["mro_errors"].append((task_name, str(e)))
            continue
            
        # 3. 实例化测试
        try:
            instance = script_task_cls(config=config, device=mock_device)
            results["passed"].append(task_name)
            print(f"[PASS] {task_name} (Class: {script_task_cls.__name__})")
        except Exception as e:
            err_msg = traceback.format_exc()
            print(f"[FAIL INIT] {task_name}: {e}")
            results["failed_init"].append((task_name, err_msg))

    print("\n" + "="*60)
    print("TASK CHECK SUMMARY")
    print("="*60)
    print(f"Passed Tasks ({len(results['passed'])}):")
    for t in results["passed"]:
        print(f"  + {t}")
        
    if results["mro_errors"]:
        print(f"\nMRO Errors ({len(results['mro_errors'])}):")
        for t, err in results["mro_errors"]:
            print(f"  x {t}: {err}")
            
    if results["failed_import"]:
        print(f"\nFailed Import ({len(results['failed_import'])}):")
        for t, err in results["failed_import"]:
            print(f"  x {t}:\n{err}")
            
    if results["failed_init"]:
        print(f"\nFailed Init ({len(results['failed_init'])}):")
        for t, err in results["failed_init"]:
            print(f"  x {t}:\n{err}")
            
    if results["missing_assets"]:
        print(f"\nMissing Asset Images ({len(results['missing_assets'])} tasks affected):")
        for t, items in results["missing_assets"].items():
            print(f"  ! {t}:")
            for attr, path in items:
                print(f"      - {attr}: {path}")
                
    if results["missing_script_task"]:
        print(f"\nSubdirectories without ScriptTask (Components/Modules) ({len(results['missing_script_task'])}):")
        print(f"  {', '.join(results['missing_script_task'])}")
        
    print("="*60)
    
    total_issues = len(results["mro_errors"]) + len(results["failed_import"]) + len(results["failed_init"]) + len(results["missing_assets"])
    if total_issues == 0:
        print("\nALL TASKS ARE HEALTHY AND CAN START PROPERLY!")
    else:
        print(f"\nFOUND {total_issues} ISSUES TO INVESTIGATE.")

if __name__ == "__main__":
    test_all_tasks()
