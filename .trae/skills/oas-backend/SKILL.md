---
name: oas-backend
description: OAS Python 后端开发专属助手。处理新增配置、新增任务、接口调试、后端启动等。
---

# OAS Backend Skill

## 何时使用

- 用户要求新增/修改后端任务模块。
- 用户要求新增/修改配置字段。
- 用户要求调试后端接口或启动后端服务。
- 用户询问 OAS 后端常见坑或魔改逻辑。

## 新增配置字段

1. 在 `module/config/config_model.py` 中注册 Pydantic 字段。
2. 同步更新三处翻译源：
   - `OASX-master/lib/config/translation/i18n_cn.dart`
   - `OASX-master/assets/i18n/zh-CN.json`
   - `module/config/i18n/zh_CN.xml`
3. 在 `config/template.json` 和 `config/oas1.json` 中补充默认值。
4. 运行 `python -c "from module.config.config_model import ConfigModel"` 验证导入。

## 新增任务模块

参考现有结构创建 `tasks/<TaskName>/`：

```text
tasks/<TaskName>/
├── config.py      # Pydantic 配置模型
├── assets.py      # 识别图 / ROI / OCR 配置
├── script_task.py # 任务执行逻辑
└── (optional) run.py
```

- 配置模型中引入 `GeneralBattleConfig` 时，按金币妖怪等示例复用。
- 战斗调用统一使用 `self.run_general_battle(config=...)`。

## 后端启动方式

- 快捷脚本：`oas-backend.bat`
- 直接启动：`toolkit/python.exe server.py` 或 `python server.py`
- API 固定端口：`127.0.0.1:7788`

## 常见坑

### ActivityShikigami 导航

- 必须先进入主活动页 `page_act`，再进入具体模式子页（如 `page_act_pass`）。
- 不可从 `page_main` 直接跳到子页，否则会触发无限重试。
- 默认运行顺序：`pass,boss`（仅门票战模式）。

### ROI 坐标

- 标题 OCR ROI：`(149, 17, 130, 22)`
- 战斗按钮 ROI：`(245, 296, 29, 88)`
- 来自 CSV 文件，禁止随意魔改。

### 配置热重载

- 修改配置后，OASX 通过 API 写入，`config_watcher.py` 热重载。
- 手动改 JSON 后建议重启后端确认生效。

### OCR 惰性加载

- ONNXRuntime 已改造为惰性加载，未启用 OCR 时不加载 C++ DLL。
- 不要强制在顶层导入重型 OCR 模块。

### 路径可移植

- 禁止使用 `F:\daima\oas` 等硬编码绝对路径。
- 使用项目已有的路径工具或 `pathlib.Path`。

## 调试命令

```bash
# 检查后端菜单
http://127.0.0.1:7788/script_menu

# 检查配置列表
http://127.0.0.1:7788/config_list

# 检查具体任务参数
http://127.0.0.1:7788/oas1/{task}/args

# 检查更新信息
http://127.0.0.1:7788/home/update_info
```
