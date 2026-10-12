# -*- coding: utf-8 -*-
"""扫描 docs/ 及项目内 md 文档，提取引用的文件/目录路径并校验是否存在。"""
import re
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(r"D:/daima/oas")
EXCLUDE_PARTS = {".workbuddy-ai", "toolkit", "node_modules", ".dart_tool", "build",
                 "site-packages", ".git", "dist", "windows", "linux", "macos", "web", "android", "ios"}

EXTS = {"py", "dart", "json", "md", "yaml", "yml", "bat", "exe", "png", "jpg", "jpeg",
        "pt", "onnx", "txt", "xml", "csv", "qml", "cpp", "h", "ps1", "sh", "toml",
        "cfg", "ini", "cache", "apk", "jar", "zip", "cn", "pyi", "pyd"}

# markdown 链接目标
RE_LINK = re.compile(r"\]\(\s*file:///([^)\s]+)\s*\)")
# 行内代码
RE_CODE = re.compile(r"`([^`\n]+)`")

def looks_like_path(s: str) -> bool:
    s = s.strip()
    if not s or " " in s or "\n" in s:
        return False
    if "/" not in s and "\\" not in s:
        return False
    if s.startswith(("http://", "https://", "file://")):
        return False
    s2 = s.rstrip("/")
    if "/" not in s2:
        return False
    ext = s2.rsplit(".", 1)[-1].lower() if "." in s2.rsplit("/", 1)[-1] else ""
    if s.endswith("/") and s.count("/") >= 1:
        return True
    return ext in EXTS

def clean(p: str) -> str:
    p = p.split("#", 1)[0]
    p = p.replace("\\", "/").strip().strip('"').strip("'")
    p = re.sub(r"^[a-zA-Z]:/", "", p)
    return p

def norm_top(p: str) -> str:
    # 仅剥离单个前导 "./"（保留 .github 等点开头目录）与 daima/oas/ 前缀
    p = re.sub(r"^\./+", "", p)
    p = re.sub(r"^daima/oas/", "", p, flags=re.I)
    return p

md_files = []
for p in ROOT.rglob("*.md"):
    if any(part in EXCLUDE_PARTS for part in p.parts):
        continue
    md_files.append(p)

missing = defaultdict(list)   # path -> [md refs]
ok = defaultdict(int)
total_refs = 0

for md in md_files:
    try:
        text = md.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = md.read_text(encoding="utf-8", errors="surrogateescape")
    rel_md = str(md.relative_to(ROOT)).replace("\\", "/")
    cands = set()
    for m in RE_LINK.finditer(text):
        cands.add(clean(m.group(1)))
    for m in RE_CODE.finditer(text):
        c = m.group(1).strip()
        if looks_like_path(c):
            cands.add(clean(c))
    for c in cands:
        c = norm_top(c)
        if not c:
            continue
        if "*" in c or "<" in c:   # 通配符 / 占位符，跳过
            continue
        total_refs += 1
        # 多基准尝试：仓库根 / docs 目录 / 当前 md 所在目录 / 其上一级
        tries = [ROOT / c, ROOT / "docs" / c, md.parent / c, md.parent.parent / c]
        if any(t.exists() for t in tries):
            ok[c] += 1
        else:
            missing[c].append(rel_md)

print(f"扫描 md 文件: {len(md_files)}")
print(f"路径引用总数: {total_refs}")
print(f"存在: {len(ok)}  缺失: {len(missing)}")
print("=" * 70)
print("【缺失清单】")
for path in sorted(missing):
    refs = sorted(set(missing[path]))
    print(f"  ✗ {path}")
    print(f"      引用自: {', '.join(refs)}")
