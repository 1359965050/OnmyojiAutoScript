"""SessionStart hook: inject project context at the beginning of each session."""
import json
import os
import socket
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str]) -> str:
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
            cwd=os.environ.get("TRAE_PROJECT_DIR", "."),
        )
        return result.stdout.strip()
    except Exception:
        return ""


def is_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except Exception:
        return False


def read_harness_state() -> dict:
    state_path = Path(".trae/.harness-state")
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def main():
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        data = {}

    cwd = data.get("cwd", os.environ.get("TRAE_PROJECT_DIR", "."))

    branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    status = run_cmd(["git", "status", "--short"])
    changed_files = len([line for line in status.splitlines() if line.strip()])
    origin_url = run_cmd(["git", "remote", "get-url", "origin"]) or "unknown"
    backend_running = is_port_open(7788)
    state = read_harness_state()
    mode = state.get("mode", "full")
    phase = state.get("phase", "build")

    context_lines = [
        f"当前分支: {branch}",
        f"改动文件数: {changed_files}",
        f"origin: {origin_url}",
        f"后端 7788 端口: {'运行中' if backend_running else '未启动'}",
        f"Harness mode: {mode}, phase: {phase}",
        "",
        "项目约束速查：",
        "- 禁止从 runhey/OnmyojiAutoScript upstream 拉取或覆盖本地。",
        "- 禁止自动 git commit / git push，提交前需用户确认。",
        "- 禁止恢复已删除模块（御魂整理、悬赏、年兽、真蛇等）。",
        "- 新增配置字段需同步三处翻译源。",
        "- 敏感信息必须放 .env，不得写入源码。",
    ]

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(context_lines),
        }
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
