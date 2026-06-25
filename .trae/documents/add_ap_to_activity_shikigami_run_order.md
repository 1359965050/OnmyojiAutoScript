# 当期爬塔添加体力（AP）模式到运行顺序

## 上下文

`ActivityShikigami` 模块的通用爬塔配置里，`run_sequence` 默认仅 `pass,boss`，帮助文案也只列出 `pass(门票)` 和 `boss(boss战)`。虽然代码中已存在 `ap_limit`、`page_act_ap`、`O_REMAIN_AP`、`I_TO_BATTLE_AP` 等体力模式基础设施，但 `run_sequence` 的 UI 描述未暴露 `ap` 选项，用户无法直观选择体力模式。用户要求把体力模式加入运行顺序选项，并补齐相关逻辑。

用户明确：AP 模式的**战斗配置**和**御魂切换配置**与门票模式（pass）共用一套，仅进入战斗的消耗凭证不同（门票 vs 体力）。因此不需要新增 `ap_battle_conf` 或 AP 专用御魂切换字段。

## 目标

1. 让 `ap` 成为 `run_sequence` 的合法选项，并将默认值改为 `pass,ap,boss`。
2. 在 `base_act.py` 中让 `ap` 模式复用 `pass` 的战斗配置和御魂切换配置。
3. 同步更新三处翻译源中的 `run_sequence_help` 文案。
4. 保持与现有 `pass`/`boss` 模式一致的代码风格，不引入额外配置字段。

## 实施方案

### 1. `tasks/ActivityShikigami/config.py`

- `GeneralClimb.run_sequence`
  - 默认值改为 `'pass,ap,boss'`。
  - `description` 改为：
    ```text
    可选：pass(门票), ap(体力), boss(boss战)
    英文逗号分隔，从左到右依次运行
    例：pass,ap,boss = 先门票 -> 再体力 -> 再boss战
    ```
  - `valid_run_sequence` 通过扫描 `_limit` 后缀字段自动识别 `ap`（`ap_limit` 已存在），无需额外修改校验逻辑。

- **不新增字段**：`ap_battle_conf`、AP 御魂切换字段均不需要，AP 与 pass 共用现有配置。

### 2. `tasks/ActivityShikigami/base_act.py`

新增一个配置标签映射，使 `ap` 复用 `pass` 的配置：

```python
@property
def config_label(self) -> str:
    """返回用于获取战斗配置和御魂切换配置的 label，ap 与 pass 共用一套配置"""
    return 'pass' if self.climb_type == 'ap' else self.climb_type
```

修改以下位置，将原本的 `self.climb_type` 替换为 `self.config_label`：

- `run()` 中获取战斗配置：
  ```python
  config_label = 'pass' if climb_type == 'ap' else climb_type
  cur_battle_conf = getattr(self.conf, f'{config_label}_battle_conf')
  ```

- `switch_soul()` 中获取御魂切换配置：
  - `enable_switch = getattr(conf, f"enable_switch_{self.config_label}", False)`
  - `enable_by_name = getattr(conf, f"enable_switch_{self.config_label}_by_name", False)`
  - `group_team = getattr(conf, f"{self.config_label}_group_team", None)`
  - `group_team_name = getattr(conf, f"{self.config_label}_group_team_name", None)`

以下逻辑保持基于 `self.climb_type` 不变：

- `lock_team()`：AP/Boss 使用 AP 专用锁图标，`pass` 使用通用锁图标。
- `check_tickets_enough()`：AP 读取 `O_REMAIN_AP`，pass 读取 `O_REMAIN_PASS`，boss 读取 `O_REMAIN_BOSS`。
- `count_map` 与 `pre_tickets_map`：按 `climb_type` 统计，AP 与 pass 独立计数。

### 3. 翻译源同步（仅修改 `run_sequence_help`）

#### `OASX-master/lib/config/translation/i18n_cn.dart`

在 `_cn_general_climb_config` 中修改：

```dart
'run_sequence_help':
    '可选：pass(门票), ap(体力), boss(boss战)\n英文逗号分隔,从左到右依次运行\n例：pass,ap,boss = 先门票 -> 再体力 -> 再boss战',
```

#### `assets/i18n/zh-CN.json`

与 i18n_cn.dart 保持文案一致，仅修改 `run_sequence_help`：

```json
"run_sequence_help": "可选：pass(门票), ap(体力), boss(boss战)\n英文逗号分隔，从左到右依次运行\n例：pass,ap,boss = 先门票 -> 再体力 -> 再boss战"
```

#### `module/config/i18n/zh_CN.xml`

该文件中没有 `run_sequence_help` 对应的条目（只有 `run_sequence`），因此只需确认无需新增即可。如需保持和前端一致，可在合适位置追加 `<source>run_sequence_help</source>` 条目。

### 4. 无需改动但需验证的文件

- `tasks/ActivityShikigami/page.py`：`page_act_ap`、`I_TO_BATTLE_AP`、`I_CLIMB_MODE_AP` 已存在。
- `tasks/ActivityShikigami/assets.py`：AP 相关资源已存在。
- `tasks/ActivityShikigami/activities/normal.py`：AP 页面连接已存在。

## 验收标准

1. 配置模型验证：
   ```bash
   python -c "from tasks.ActivityShikigami.config import ActivityShikigami; c=ActivityShikigami(); print(c.general_climb.run_sequence_v)"
   ```
   预期输出包含 `['pass', 'ap', 'boss']`。

2. 配置标签映射验证：
   ```bash
   python -c "
   from tasks.ActivityShikigami.base_act import BaseAct
   from tasks.ActivityShikigami.config import ActivityShikigami
   from unittest.mock import MagicMock
   b = BaseAct.__new__(BaseAct)
   b.config = MagicMock()
   b.config.model.activity_shikigami = ActivityShikigami()
   b.run_idx = 1
   print(b.config_label)
   "
   当 `run_idx=1` 且默认顺序为 `pass,ap,boss` 时，`config_label` 应为 `'pass'`（因为 `climb_type='ap'`）。

3. 模块导入验证：
   ```bash
   python -c "from tasks.ActivityShikigami.base_act import BaseAct; from tasks.ActivityShikigami.script_task import ScriptTask; print('ok')"
   ```

4. 翻译文件校验：
   - `assets/i18n/zh-CN.json` JSON 语法无误。
   - `module/config/i18n/zh_CN.xml` XML 标签闭合无误。
   - `OASX-master/.../i18n_cn.dart` map 语法无误。

5. 前端验证（OASX 重启/重新编译后）：
   - `运行爬塔顺序` 默认值显示 `pass,ap,boss`。
   - 帮助文案显示 `可选：pass(门票), ap(体力), boss(boss战)`。
   - 配置页不会出现新的“体力爬塔战斗配置”或“体力爬塔御魂切换”面板，AP 模式复用现有的“战斗配置”和“切换御魂”设置。

## 关键修改文件

- `f:\daima\OAS\tasks\ActivityShikigami\config.py`
- `f:\daima\OAS\tasks\ActivityShikigami\base_act.py`
- `f:\daima\OAS\OASX-master\lib\config\translation\i18n_cn.dart`
- `f:\daima\OAS\assets\i18n\zh-CN.json`
- `f:\daima\OAS\module\config\i18n\zh_CN.xml`（仅按需追加 help 条目）
