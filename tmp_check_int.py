import json
with open('module/config/i18n/zh-CN.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
for k in ['layer', 'layer_help', 'number_attack', 'number_attack_help', 'preset_group', 'preset_group_help']:
    print(f'{k}: {data.get(k, "MISSING")!r}')
