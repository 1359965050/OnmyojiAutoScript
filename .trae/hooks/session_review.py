"""Stop hook: review changes before ending the assistant turn."""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


SENSITIVE_PATTERNS = (
    ".env",
    "password",
    "secret",
    "api_key",
    "apikey",
    "token",
)


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


def contains_sensitive(path: str) -> bool:
    lower = path.lower()
    return any(pattern.lower() in lower for pattern in SENSITIVE_PATTERNS)


def main():
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        data = {}

    loop_count = data.get("loop_count", 0)
    last_message = data.get("last_assistant_message", "")

    diff_stat = run_cmd(["git", "diff", "--stat"])
    changed_files = run_cmd(["git", "diff", "--name-only"]).splitlines()
    sensitive_files = [f for f in changed_files if contains_sensitive(f)]

    report_lines = [
        f"## {datetime.now().isoformat(timespec='minutes')}",
        f"loop_count: {loop_count}",
        "",
        "### git diff --stat",
        diff_stat or "无未提交改动",
        "",
    ]

    if sensitive_files:
        report_lines.append("### 敏感文件改动")
        report_lines.extend(f"- {f}" for f in sensitive_files)
        report_lines.append("")

    report_text = "\n".join(report_lines)

    reviews_dir = Path(".trae/reviews")
    reviews_dir.mkdir(parents=True, exist_ok=True)
    review_file = reviews_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    with review_file.open("a", encoding="utf-8") as f:
        f.write(report_text + "\n")

    decision = ""
    reason = ""
    if sensitive_files:
        decision = "block"
        reason = f"检测到敏感文件改动: {', '.join(sensitive_files)}，请确认是否为预期行为并继续检查。"
    elif "TODO" in last_message or "FIXME" in last_message:
        decision = "block"
        reason = "助手输出中包含 TODO/FIXME，建议先完成或明确遗留事项。"

    output = {
        "decision": decision,
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": report_text,
        },
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
