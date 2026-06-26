"""Harness health check for OAS Python backend in Trae IDE."""
from __future__ import annotations

import importlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class CheckResult:
    def __init__(self) -> None:
        self.checks: list[dict] = []
        self.ok_count = 0
        self.critical_fails = 0

    def add(self, name: str, ok: bool, hint: str = "", optional: bool = False) -> None:
        self.checks.append({"name": name, "ok": ok, "hint": hint, "optional": optional})
        if ok:
            self.ok_count += 1
        elif not optional:
            self.critical_fails += 1


def package_installed(name: str) -> bool:
    try:
        importlib.metadata.version(name)
        return True
    except importlib.metadata.PackageNotFoundError:
        return False


def run_cmd(cmd: list[str], timeout: int = 5) -> str:
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            cwd=PROJECT_ROOT,
        )
        return result.stdout.strip()
    except Exception as exc:
        return str(exc)


def check_files(result: CheckResult) -> None:
    rules_dir = PROJECT_ROOT / ".trae" / "rules"
    required_rules = [
        "project_overview.md",
        "coding_standards.md",
        "security_guardrails.md",
        "review_checklist.md",
        "git_commit_message.md",
    ]
    for rule in required_rules:
        path = rules_dir / rule
        ok = path.exists()
        result.add(f"rule: {rule}", ok, hint="" if ok else f"{path} 缺失")

    hooks_json = PROJECT_ROOT / ".trae" / "hooks.json"
    if hooks_json.exists():
        try:
            with hooks_json.open("r", encoding="utf-8") as f:
                data = json.load(f)
            required_events = {"SessionStart", "PreToolUse", "PostToolUse", "Stop"}
            registered = set(data.get("hooks", {}).keys())
            missing = required_events - registered
            result.add(
                "hooks.json 事件注册",
                not missing,
                hint="" if not missing else f"缺少事件: {', '.join(missing)}",
            )
        except json.JSONDecodeError as exc:
            result.add("hooks.json 解析", False, hint=f"JSON 解析失败: {exc}")
    else:
        result.add("hooks.json", False, hint=".trae/hooks.json 缺失")

    hooks_dir = PROJECT_ROOT / ".trae" / "hooks"
    required_hooks = [
        "session_start.py",
        "pre_tool_check.py",
        "post_tool_check.py",
        "session_review.py",
    ]
    for hook in required_hooks:
        path = hooks_dir / hook
        ok = path.exists()
        result.add(f"hook: {hook}", ok, hint="" if ok else f"{path} 缺失")

    skills_dir = PROJECT_ROOT / ".trae" / "skills"
    required_skills = [
        "harness-init/SKILL.md",
        "harness-mode/SKILL.md",
        "oas-backend/SKILL.md",
    ]
    for skill in required_skills:
        path = skills_dir / skill
        ok = path.exists()
        result.add(f"skill: {skill}", ok, hint="" if ok else f"{path} 缺失")


def check_lsp(result: CheckResult) -> None:
    lsp_json = PROJECT_ROOT / ".lsp.json"
    ok = lsp_json.exists()
    result.add(".lsp.json", ok, hint="" if ok else "缺失")

    pyright_config = PROJECT_ROOT / "pyrightconfig.json"
    ok = pyright_config.exists()
    result.add("pyrightconfig.json", ok, hint="" if ok else "缺失")

    pyright = shutil.which("pyright-langserver") or shutil.which("basedpyright-langserver")
    result.add(
        "Python LSP (pyright)",
        bool(pyright),
        hint="" if pyright else "未安装，执行 pip install pyright 或安装 BasedPyright 插件",
    )


def check_python_environment(result: CheckResult) -> None:
    version_info = sys.version_info
    version_ok = version_info.major == 3 and version_info.minor == 10
    result.add(
        "Python 版本 3.10.x",
        version_ok,
        hint=f"当前 {version_info.major}.{version_info.minor}.{version_info.micro}",
    )

    required_packages = [
        "fastapi",
        "pydantic",
        "uiautomator2",
        "ppocr-onnx",
        "uvicorn",
    ]
    for package in required_packages:
        if package_installed(package):
            result.add(f"依赖: {package}", True)
        else:
            result.add(f"依赖: {package}", False, hint="未安装")

    critical_imports = [
        "module.logger",
        "module.config.config_model",
    ]
    for module_name in critical_imports:
        try:
            importlib.import_module(module_name)
            result.add(f"导入: {module_name}", True)
        except ImportError as exc:
            result.add(f"导入: {module_name}", False, hint=str(exc))


def check_git_remote(result: CheckResult) -> None:
    origin = run_cmd(["git", "remote", "get-url", "origin"])
    if not origin:
        result.add("git origin", False, hint="未配置 origin")
        return

    forbidden = "runhey/OnmyojiAutoScript"
    if forbidden in origin:
        result.add(
            "git origin 指向",
            False,
            hint=f"origin 指向 upstream {origin}，禁止从此源拉取",
        )
    else:
        result.add("git origin 指向", True, hint=origin)


def main() -> int:
    result = CheckResult()
    check_files(result)
    check_lsp(result)
    check_python_environment(result)
    check_git_remote(result)

    total = len(result.checks)
    print(f"\nHarness 健康检查: {result.ok_count}/{total} 通过\n")
    for check in result.checks:
        icon = "✅" if check["ok"] else "⚠️" if check["optional"] else "❌"
        line = f"  {icon} {check['name']}"
        if check["hint"]:
            line += f" — {check['hint']}"
        print(line)
    print("")

    if result.critical_fails > 0:
        print(f"关键失败项: {result.critical_fails}")
        return 1
    print("所有关键检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
