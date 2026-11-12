# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import argparse
from pathlib import Path
import subprocess
import sys

from module.logger import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def generate(input_file: str = "requirements-in.txt", output_file: str = "requirements.txt"):
    in_path = PROJECT_ROOT / input_file
    out_path = PROJECT_ROOT / output_file
    if not in_path.exists():
        raise FileNotFoundError(f"Input requirements file not found: {in_path}")

    # 执行命令 pip-compile --annotation-style=line --output-file=requirements.txt requirements-in.txt
    subprocess.run(
        [
            sys.executable,
            "-m",
            "piptools",
            "compile",
            "--annotation-style=line",
            "--output-file",
            str(out_path),
            str(in_path),
        ],
        cwd=str(PROJECT_ROOT),
        check=True,
    )

    if out_path.exists():
        content = out_path.read_text(encoding="utf-8")
        cleaned = content.replace(
            "--index-url https://pypi.tuna.tsinghua.edu.cn/simple\n"
            "--trusted-host pypi.tuna.tsinghua.edu.cn\n",
            "",
        ).replace(
            "--index-url https://pypi.tuna.tsinghua.edu.cn/simple\n"
            "--trusted-host pypi.tuna.tsinghua.edu.cn",
            "",
        )
        if cleaned != content:
            out_path.write_text(cleaned, encoding="utf-8")
    logger.info(f"{output_file} generated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate requirements.txt from requirements-in.txt")
    parser.add_argument("--input", default="requirements-in.txt", help="Input .in requirements file")
    parser.add_argument("--output", default="requirements.txt", help="Output locked requirements file")
    args, _ = parser.parse_known_args()
    generate(input_file=args.input, output_file=args.output)


