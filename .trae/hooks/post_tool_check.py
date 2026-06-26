"""PostToolUse hook: validate results after file edits."""
import json
import os
import subprocess
import sys
from pathlib import Path


def py_compile_file(file_path: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["python", "-m", "py_compile", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            cwd=os.environ.get("TRAE_PROJECT_DIR", "."),
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip()
    except Exception as exc:
        return False, str(exc)


def main():
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        data = {}

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    messages = []
    if file_path.endswith(".py") and Path(file_path).exists():
        ok, err = py_compile_file(file_path)
        if ok:
            messages.append(f"{file_path}: py_compile 通过")
        else:
            messages.append(f"{file_path}: py_compile 失败 - {err}")

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(messages) if messages else "",
        }
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
