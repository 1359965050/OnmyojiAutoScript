---
alwaysApply: false
globs: "module/**/*.py,tasks/**/*.py,server.py,script.py,deploy/**/*.py"
description: "OAS Python 后端编码规范"
---

# OAS Python 后端编码规范

## 技术栈

- Python 3.10
- Pydantic v2
- FastAPI
- uiautomator2
- ppocr-onnx（OCR 惰性加载，未启用 OCR 时不加载 C++ DLL）

## 新增配置字段流程

1. 在 `module/config/config_model.py` 中注册 Pydantic 字段。
2. 同步更新三处翻译源（`i18n_cn.dart`、`zh-CN.json`、`zh_CN.xml`）。
3. 在 `config/template.json` 和 `config/oas1.json` 中补充默认值。

## 新增任务模块流程

参考现有任务结构：

```text
tasks/<TaskName>/
├── config.py      # Pydantic 配置模型
├── assets.py      # 识别图/ROI/ocr 配置
├── script_task.py # 任务执行逻辑
└── (optional) run.py
```

## 命名与风格

- 函数/变量使用 `snake_case`。
- 类使用 `PascalCase`。
- 常量使用 `UPPER_SNAKE_CASE`。
- 日志统一使用 `module.logger.logger`，禁止 `print`。

## 路径与可移植性

- 使用 `pathlib.Path` 或项目已有的路径工具，禁止硬编码 `F:\daima\oas` 等绝对路径。
- `toolkit/python310._pth` 中项目根目录应使用相对路径 `..`。

## 识别图与 ROI

- 若游戏 UI 改版，运行 `dev_tools/assets_extract.py` 重制识别图。
- ROI 数据优先从 `docs/` 下的 CSV 文件读取，不要魔法数字。

## 改动纪律

- 只动必须改的代码，不顺手重构无关部分。
- 不要恢复已物理删除的模块（御魂整理、悬赏、年兽、真蛇、绘卷、花车、对弈等）。
- 不要改动 `toolkit/`、`deploy/launcher/` 等环境文件，除非用户明确授权。
