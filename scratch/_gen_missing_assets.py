# -*- coding: utf-8 -*-
"""生成"待补切图清单"：找出所有被引用但缺失的切图，并补齐规则元数据。"""
import json
import pathlib
import re

ROOT = pathlib.Path(r'D:/daima/oas')
FILE_PAT = re.compile(r'^(\S+)\s*=\s*(Rule\w+)\((.*)file=["\'](\./[^"\']+)["\']')
ATTR_PAT = re.compile(r'^\s*([A-Z][A-Z0-9_]*)\s*=\s*(Rule\w+)\(')


def iter_assets():
    for py in list(ROOT.glob('tasks/**/assets.py')) + list(ROOT.glob('module/**/assets.py')):
        for line in py.read_text(encoding='utf-8', errors='replace').splitlines():
            m = ATTR_PAT.match(line)
            if not m:
                continue
            fm = re.search(r'file=["\'](\./[^"\']+)["\']', line)
            if not fm:
                continue
            yield py, m.group(1), m.group(2), fm.group(1)[2:]


def load_json_entries():
    """把所有资源 json 的 imageName -> 条目 建索引（含来源 json 路径）。"""
    idx = {}
    for js in ROOT.glob('tasks/**/*.json'):
        try:
            data = json.loads(js.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for it in data:
            if isinstance(it, dict) and it.get('imageName'):
                idx.setdefault(it['imageName'], []).append((js, it))
    return idx


json_idx = load_json_entries()
missing = []
for py, attr, kind, rel in iter_assets():
    if (ROOT / rel).exists():
        continue
    name = pathlib.Path(rel).name
    entries = json_idx.get(name, [])
    missing.append({
        'rel': rel,
        'attr': attr,
        'kind': kind,
        'assets': str(py.relative_to(ROOT)).replace('\\', '/'),
        'entries': entries,
    })

missing.sort(key=lambda x: x['rel'])

print(f'缺失切图总数: {len(missing)}\n')
for i, m in enumerate(missing, 1):
    print(f"### {i}. {m['rel']}")
    print(f"  规则: {m['attr']}  ({m['kind']})")
    print(f"  声明于: {m['assets']}")
    if m['entries']:
        for js, it in m['entries']:
            print(f"  JSON: {js.relative_to(ROOT)}")
            print(f"    itemName   : {it.get('itemName')}")
            print(f"    roiFront   : {it.get('roiFront')}")
            print(f"    roiBack    : {it.get('roiBack')}")
            print(f"    method     : {it.get('method')}")
            print(f"    threshold  : {it.get('threshold')}")
            print(f"    description: {it.get('description')}")
    else:
        print("  JSON: (未找到对应声明条目)")
    print()
