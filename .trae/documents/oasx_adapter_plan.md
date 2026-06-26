# OASX 前端适配当前后端实施计划

## 1. 目标摘要
将 `f:\daima\oas\OASX-master` 这份较早的 OASX 前端源码，调整为能够连接当前后端（`127.0.0.1:7788`）并正确渲染菜单、任务配置界面的可运行前端。本次只改动前端代码，不修改后端任务、接口与翻译文件。

## 2. 当前状态分析

### 2.1 已完成（来自前文）
- `lib/api/api_client.dart`：默认地址已改为 `127.0.0.1:7788`，与当前后端端口一致。
- `lib/config/translation/i18n_content.dart`：已新增 `dokan`、`global_settings`、`emulator_settings`、`game_settings`、`hero_test`、`six_realms`、`meta_demon`、`dye_trials` 等菜单常量，并清理了大部分已删除任务常量。
- `lib/config/translation/i18n_cn.dart`：`_cn_menu` 已按后端当前菜单更新；已为 `Dokan`、`SixRealms`、`HeroTest`、`MetaDemon`、`DyeTrials` 等新增/保留任务补充配置字段中文翻译。
- `lib/config/translation/i18n.dart`：已移除已删除任务翻译 map 的引用。
- `assets/i18n/zh-CN.json` 与 `en-US.json`：已创建为空对象，避免启动时读不到文件的报错。

### 2.2 仍存在的问题
| 问题 | 影响 | 涉及文件 |
|------|------|----------|
| `pubspec.yaml` 未注册 `assets/i18n/*.json` | 若后续代码改用 `rootBundle` 读取会报错；当前 `flutter analyze` 也可能提示未声明资源 | `OASX-master/pubspec.yaml` |
| 前端离线回退菜单 `nav_menu.json` 仍包含大量后端已删除的任务 | API 异常或离线时菜单会显示无效任务（年兽、花合战、小猫咪等） | `OASX-master/lib/controller/nav_menu/nav_menu.json` |
| 尚未运行 `flutter analyze` | 无法确认是否还有因删除常量/翻译 map 导致的静态错误 | 整个 `OASX-master` |
| 尚未连接后端实际验证 | 无法确认菜单、任务配置页、更新器按钮等是否真正可用 | 前端 + 后端运行时 |

### 2.3 后端菜单事实来源
后端 `module/config/config_menu.py` 当前返回的 `/script_menu` 结构为：
```json
{
  "Overview": [],
  "GlobalSettings": ["EmulatorSettings", "Restart", "GameSettings"],
  "Soul Zones": ["Orochi", "Sougenbi", "FallenSun", "EternitySea", "SixRealms"],
  "Daily Task": ["DailyTrifles", "AreaBoss", "GoldYoukai", "ExperienceYoukai", "DemonEncounter"],
  "Liver Emperor Exclusive": ["BondlingFairyland", "EvoZone", "GoryouRealm", "Exploration", "Hyakkiyakou", "HeroTest"],
  "Guild": ["KekkaiUtilize", "KekkaiActivation", "RealmRaid", "RyouToppa", "Dokan", "Hunt", "AbyssShadows", "GuildBanquet", "DemonRetreat", "GuildActivityMonitor"],
  "Weekly Task": ["RichMan", "Secret", "WeeklyTrifles"],
  "Activity Task": ["ActivityShikigami", "MetaDemon", "DyeTrials"]
}
```
前端回退菜单必须与上述结构一致。

## 3. 待实施改动

### 步骤 A：注册静态资源（低风险）
**文件**：`OASX-master/pubspec.yaml`
**操作**：在 `flutter: assets:` 段新增两行：
```yaml
assets:
  - assets/release.txt
  - assets/images/Icon-app.png
  - assets/i18n/zh-CN.json
  - assets/i18n/en-US.json
```
**原因**：`assets/i18n/` 下的 JSON 已创建，必须在 `pubspec.yaml` 中声明后 Flutter 才会打包；也能消除 `flutter analyze` 对未注册资源的潜在警告。

### 步骤 B：同步前端离线回退菜单
**文件**：`OASX-master/lib/controller/nav_menu/nav_menu.json`
**操作**：按后端 `module/config/config_menu.py` 重写该 JSON，规则如下：
1. 删除 `TaskList` 一级分组（后端 `gui_menu_list` 已移除）。
2. 删除 `Tools` 一级分组（后端 `/script_menu` 不再返回）。
3. `GlobalSettings` 子项改为 `["EmulatorSettings", "Restart", "GameSettings"]`。
4. `Soul Zones` 增加 `SixRealms`。
5. `Daily Task` 删除 `Nian`、`TalismanPass`、`Pets`、`SoulsTidy`、`Delegation`、`WantedQuests`、`Tako`。
6. `Liver Emperor Exclusive` 增加 `Hyakkiyakou`、`HeroTest`。
7. `Guild` 增加 `Dokan`、`AbyssShadows`、`GuildBanquet`、`DemonRetreat`、`GuildActivityMonitor`；删除 `CollectiveMissions`。
8. `Weekly Task` 删除 `TrueOrochi`、`MysteryShop`、`Duel`。
9. `Activity Task` 增加 `MetaDemon`、`DyeTrials`。

目标内容：
```json
{
    "Overview": [],
    "GlobalSettings": ["EmulatorSettings", "Restart", "GameSettings"],
    "Soul Zones": ["Orochi", "Sougenbi", "FallenSun", "EternitySea", "SixRealms"],
    "Daily Task": ["DailyTrifles", "AreaBoss", "GoldYoukai", "ExperienceYoukai", "DemonEncounter"],
    "Liver Emperor Exclusive": ["BondlingFairyland", "EvoZone", "GoryouRealm", "Exploration", "Hyakkiyakou", "HeroTest"],
    "Guild": ["KekkaiUtilize", "KekkaiActivation", "RealmRaid", "RyouToppa", "Dokan", "Hunt", "AbyssShadows", "GuildBanquet", "DemonRetreat", "GuildActivityMonitor"],
    "Weekly Task": ["RichMan", "Secret", "WeeklyTrifles"],
    "Activity Task": ["ActivityShikigami", "MetaDemon", "DyeTrials"]
}
```

### 步骤 C：静态检查与清理
**命令**：在 `OASX-master` 目录执行 `flutter analyze`。
**预期处理**：
- 修复任何因删除常量/翻译 map 导致的 `undefined_identifier` 错误。
- 修复未使用导入、未注册资源等警告。
- 若发现新的已删除任务残留引用，一并删除。

### 步骤 D：运行时验证
**环境**：先启动后端（`oas-backend` 或等效命令），再运行 OASX。
**验证清单**：
1. 登录/连接成功，无 `LocaleService._loadLocaleMessage` 相关崩溃。
2. 左侧二级菜单与后端 `/script_menu` 完全一致，没有年兽、花合战等已删除任务。
3. 点击 `GlobalSettings` -> `模拟器设置/游戏设置/重启` 能正常加载配置。
4. 点击 `道馆`、`六道之门`、`英杰试炼`、`超鬼王`、`灵染试炼` 等新任务能加载参数并显示中文标签。
5. 更新器页面显示当前分支 `master` 且“手动更新”按钮可点击并返回更新结果。
6. 切换配置（`oas1` 等）后任务菜单仍正常渲染。

### 步骤 E：文档与收尾
- 若运行时验证发现某些字段翻译缺失，在 `i18n_cn.dart` 对应任务 map 中补全，并在验收文档中记录。
- 生成 `docs/oasx_adapter/ACCEPTANCE_oasx_adapter.md` 记录验证结果与剩余 TODO（如字段翻译补全、构建发布命令等）。

## 4. 关键决策与假设
- **后端为事实来源**：后端任务列表、菜单分组、API 响应不变；前端只做适配。
- **不修改后端翻译文件**：`module/config/i18n/zh-CN.json`、`zh_CN.xml` 等后端文件保持现状，依赖前端启动时通过 `/home/chinese_translate` 推送翻译。
- **回退菜单必须同步**：`nav_menu.json` 是前端本地回退数据，需要与后端当前菜单一致，避免 API 失败时显示无效任务。
- **Flutter 版本假设**：当前 `pubspec.yaml` 已声明 `sdk: ">=3.5.0 <4.0.0"`，验证时直接使用项目现有 Flutter 环境。

## 5. 验证通过标准
- `flutter analyze` 无 error（warning 尽量清零）。
- 后端运行时，OASX 能正确渲染当前全部任务菜单。
- 至少验证 `Dokan`、`SixRealms`、`HeroTest`、`MetaDemon`、`DyeTrials`、`ActivityShikigami` 的 args 页面中文标签可正常显示。
- 更新器接口 `/home/update_info` 与 `/home/execute_update` 调用无异常。
