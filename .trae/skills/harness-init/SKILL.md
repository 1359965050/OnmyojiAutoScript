---
name: harness-init
description: 初始化或重置 OAS 项目的 Trae 适配。检测 Python 后端环境、检查依赖、补全规则占位符、注册 Hook。
---

# Harness Init

## 适用场景

- 首次将 Harness Starter 概念迁移到本项目的 Trae 环境。
- 规则、Hook 或 LSP 配置被误删后需要重置。
- 项目结构发生重大变化后重新对齐。

## 初始化步骤

### Step 0：检查核心文件

确认项目根目录下是否存在：

- `.trae/rules/` 及 5 个规则文件
- `.trae/hooks.json`
- `.trae/hooks/` 及 4 个 Python Hook 脚本
- `.trae/skills/` 及 3 个 SKILL.md
- `.lsp.json`
- `pyrightconfig.json`
- `scripts/check.py`

缺失则从本仓库模板或历史提交中恢复。

### Step 1：检测 Python 后端信息

读取以下文件推断信息：

- `requirements.txt` → Python 依赖
- `server.py` / `script.py` → 启动入口
- `module/config/config_model.py` → 配置模型
- `deploy.yaml` → 自动更新配置

### Step 2：补全规则占位符

检查 `.trae/rules/project_overview.md`：

- 若含 `【待填写】` 占位符，用 Step 1 推断的信息替换。
- 若无法推断，询问用户：项目用途、主要技术栈、测试命令。

### Step 3：检查 Hook 注册

确认 `.trae/hooks.json` 包含：

- `SessionStart`
- `PreToolUse`
- `PostToolUse`
- `Stop`

### Step 4：检查并安装 LSP

- 检查 `pyright-langserver` 或 `basedpyright` 是否可用。
- 若不可用，提示用户执行：`pip install pyright` 或安装 Trae 的 BasedPyright 插件。
- 确认 `.lsp.json` 与 `pyrightconfig.json` 内容一致且针对 Python 3.10。

### Step 5：运行健康检查

执行：

```bash
toolkit/python.exe scripts/check.py
```

或：

```bash
python scripts/check.py
```

向用户展示结果，处理失败项。

### Step 6：完成提示

说明当前 Harness 状态：

- 已启用的 Hook：SessionStart / PreToolUse / PostToolUse / Stop
- 已安装的 LSP：pyright / basedpyright
- 还需要用户手动做的事：在 Trae 设置 → Hooks 中启用项目 Hook 并选择“本地自动运行”。
