"""PreToolUse hook: intercept dangerous file writes and commands."""
import json
import re
import sys


SENSITIVE_FILES = (
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
)

DANGEROUS_COMMANDS = (
    "rm -rf",
    "git push --force",
    "git push -f",
    "git reset --hard",
    "git checkout .",
    "git clean -f",
)

UPSTREAM_PATTERNS = (
    "runhey/OnmyojiAutoScript",
)


def is_sensitive_file(path: str) -> bool:
    lower = path.lower()
    return any(lower.endswith(name.lower()) for name in SENSITIVE_FILES) or "/.env" in lower


def is_dangerous_command(command: str) -> tuple[bool, str]:
    cmd_lower = command.lower()
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous.lower() in cmd_lower:
            return True, f"检测到高危命令: {dangerous}"
    return False, ""


def is_upstream_operation(command: str) -> tuple[bool, str]:
    cmd_lower = command.lower()
    if "git" in cmd_lower and ("fetch" in cmd_lower or "pull" in cmd_lower or "merge" in cmd_lower):
        for pattern in UPSTREAM_PATTERNS:
            if pattern.lower() in cmd_lower:
                return True, f"禁止从 upstream {pattern} 拉取或合并"
    return False, ""


def main():
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        data = {}

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    decision = "allow"
    reason = ""

    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if is_sensitive_file(file_path):
            decision = "deny"
            reason = f"禁止直接写入敏感文件: {file_path}"

    elif tool_name in ("RunCommand", "Shell", "Bash", "PowerShell"):
        command = tool_input.get("command", "")
        if command:
            dangerous, dangerous_reason = is_dangerous_command(command)
            if dangerous:
                decision = "deny"
                reason = dangerous_reason
            else:
                upstream, upstream_reason = is_upstream_operation(command)
                if upstream:
                    decision = "deny"
                    reason = upstream_reason

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason if reason else "通过安全校验",
        }
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
