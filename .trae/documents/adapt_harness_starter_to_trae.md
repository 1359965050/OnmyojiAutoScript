# 将 Harness Starter 适配到 Trae/Kimi 环境

## Context

用户希望把 [Harness Starter](https://github.com/chenklein26-maker/Harness-Starter) 模板迁移到当前 OAS 项目的 Trae/Kimi 环境中。

- 目标平台：Trae IDE（不是 Claude Code），因此不保留 `.claude/` 目录。
- 规范来源： Harness 的通用 AI 行为准则 + 现有 `docs/skill.md` 中的项目特定约束。
- 覆盖范围：仅 Python 后端；`OASX-master/` Flutter 前端不在本次范围内。
- 关键背景：`.trae/rules/` 目录曾在远程提交 `acb0ab2` 中被删除，本次将重新创建并增强内容。

## Goals

1. 在 Trae 可识别的位置建立项目规则、Hook、Skill 三层机制。
2. 把 `docs/skill.md` 的硬性约束（网络隔离、导航规范、ROI、翻译同步等）转化为 AI 长期遵循的规则。
3. 引入 Harness 的通用原则（Think Before Coding / 安全拦截 / 自动审查闭环）。
4. 配置 Python 后端 LSP（pyright）。
5. 提供可运行的健康检查脚本，验证适配是否到位。

## Non-Goals

- 不保留或维护 `.claude/` 目录。
- 不覆盖 `OASX-master/` 前端。
- 不恢复已删除的游戏任务模块。
- 不自动提交或推送到 fork（规则本身会禁止这一点）。

## Proposed File Layout

```text
f:\daima\oas
├── .trae/
│   ├── hooks.json                         # 项目 Hook 注册表
│   ├── hooks/                             # Hook 执行脚本（Python）
│   │   ├── session_start.py
│   │   ├── pre_tool_check.py
│   │   ├── post_tool_check.py
│   │   └── session_review.py
│   ├── rules/                             # 项目规则（alwaysApply / glob 控制）
│   │   ├── project_overview.md
│   │   ├── coding_standards.md
│   │   ├── security_guardrails.md
│   │   ├── review_checklist.md
│   │   └── git_commit_message.md
│   ├── skills/                            # 按需加载的项目 Skill
│   │   ├── harness-init/SKILL.md
│   │   ├── harness-mode/SKILL.md
│   │   └── oas-backend/SKILL.md
│   └── reviews/                           # Stop Hook 审查报告
├── .lsp.json                              # pyright（兼容 Claude Code）
├── pyrightconfig.json                     # Trae / VS Code 插件实际读取
└── scripts/
    └── check.py                           # Python 版健康检查
```

## Implementation Steps

### Step 1: 创建项目规则 `.trae/rules/`

| 文件 | 触发方式 | 主要内容 |
|---|---|---|
| `project_overview.md` | `alwaysApply: true` | 项目身份、网络隔离、自动更新源、后端端口、保留模块、禁止恢复已删模块、翻译同步要求、`.env` 敏感配置约束。 |
| `coding_standards.md` | `globs: module/**/*.py, tasks/**/*.py, server.py, script.py` | Python 3.10 + Pydantic v2 + FastAPI 技术栈；新增配置/任务流程；命名规范；路径可移植（禁止硬编码 `F:\daima\oas`）；日志使用 `module.logger`；识别图更新入口。 |
| `security_guardrails.md` | `alwaysApply: true` | 禁止写入 `.env`；禁止高危 Git 命令（`rm -rf`、`git push --force`、`git reset --hard`、`git checkout .`、`git clean -f`）；禁止从 upstream `runhey/OnmyojiAutoScript` 拉取；禁止自动 commit/push；禁止改动 `toolkit/`、`deploy/launcher/` 等环境目录。 |
| `review_checklist.md` | `alwaysApply: true` | 多步骤任务先列计划、目标可机器验证、3 轮失败停止；Think Before Coding；讨论与执行分离；Simplicity First；Surgical Changes；测试优先；每次改动后自检。 |
| `git_commit_message.md` | `alwaysApply: true` | 恢复并保留原有提交信息规则：`type(scope): 中文描述`，正文 `- ` 列表，不写敏感信息。 |

### Step 2: 配置 Python LSP

- 创建 `.lsp.json`，将 language server 改为 `pyright-langserver`。
- 创建 `pyrightconfig.json`，指定 Python 3.10、`basic` 类型检查、包含 `module/` / `tasks/` / `server.py` / `script.py` / `deploy/`，排除 `OASX-master/`、`toolkit/`、`assets/`、`config/`、`log/`、`__pycache__`。

### Step 3: 创建 Hook 配置与脚本 `.trae/hooks.json`

注册 L2 核心 Hook（与 Harness 默认一致）：

- `SessionStart` → `.trae/hooks/session_start.py`
  - 注入当前分支、`git status --short` 改动数、后端 7788 端口状态、Harness mode/phase。
- `PreToolUse`（匹配 `Edit\|Write\|RunCommand` 等） → `.trae/hooks/pre_tool_check.py`
  - 拦截 `.env` 写入、高危命令、upstream 拉取。
- `PostToolUse`（匹配 `Edit\|Write`） → `.trae/hooks/post_tool_check.py`
  - 对变更的 `.py` 文件执行 `python -m py_compile`。
- `Stop` → `.trae/hooks/session_review.py`
  - `git diff --stat`、敏感文件检查、审查报告追加到 `.trae/reviews/YYYY-MM-DD.md`。

Hook 脚本统一使用 Python，通过 `sys.stdin.read()` 读取 Trae 传入的 JSON，按事件规范输出。

### Step 4: 迁移并新增 Skill `.trae/skills/`

- `harness-init/SKILL.md`：初始化/重置 Trae 适配，检查规则、Hook、LSP、依赖。
- `harness-mode/SKILL.md`：工作模式与阶段切换（`full/hotfix/tweak`、`design/build/fix`），读写 `.trae/.harness-state`。
- `oas-backend/SKILL.md`：OAS Python 后端专属助手，覆盖新增配置字段、新增任务、后端启动、常见坑。

### Step 5: 创建 Python 健康检查脚本 `scripts/check.py`

将原 `scripts/check.mjs` 的思路迁移为 Python：

- 检查 `.trae/rules/`、`hooks.json`、hooks、skills 是否存在。
- 检查 Python 版本是否为 3.10.x。
- 检查关键依赖是否已安装并可导入（`fastapi`、`pydantic`、`uiautomator2`、`ppocr-onnx`、`uvicorn`）。
- 检查关键项目导入：`module.logger`、`module.config.config_model.ConfigModel`。
- 检查 `pyright-langserver` 是否可用。
- 检查 `git remote get-url origin` 指向个人 fork，而非 upstream。
- 输出通过数/总数、关键失败项。

### Step 6: Trae 中启用并验证

1. 设置 → 规则：确认 5 条项目规则已加载，无 frontmatter 报错。
2. 设置 → Hooks：启用项目 Hook，确认 `.trae/hooks.json` 被读取。
3. 设置 → Hooks 运行方式：选择“本地自动运行”（Hook 需要调用本地 Python 和 git）。
4. 安装/启用 Python 类型检查插件（Pyright / BasedPyright）。
5. 运行 `toolkit/python.exe scripts/check.py` 或 `python scripts/check.py`。

## Verification Checklist

- [ ] `python scripts/check.py` 全部关键检查通过。
- [ ] Trae 设置 → 规则 中能看到 5 条规则且无解析错误。
- [ ] Trae 设置 → Hooks 中已启用项目 Hook，`.trae/hooks.json` 被识别。
- [ ] 新建会话后，AI 收到 SessionStart 注入的分支、改动文件数、后端状态。
- [ ] 让 AI 尝试写入 `.env`，PreToolUse 成功拦截并给出原因。
- [ ] 让 AI 尝试执行 `git pull https://github.com/runhey/OnmyojiAutoScript.git`，PreToolUse 拒绝或提示风险。
- [ ] 修改 `.py` 文件后，PostToolUse 触发 `py_compile`，无语法错误。
- [ ] 源代码管理面板使用 AI 生成提交信息，格式符合 `.trae/rules/git_commit_message.md`。
- [ ] `python -c "from module.config.config_model import ConfigModel"` 成功。
- [ ] `pyright-langserver --version` 或 BasedPyright 已安装并可调用。
- [ ] `.trae/` 已作为新 commit 推送到个人 fork（避免被自动更新误清理）。

## Risks & Notes

1. `.trae/rules/` 曾在 `acb0ab2` 被删除，重新创建后建议立即提交到个人 fork，防止 `deploy.yaml` 自动更新时因 untracked 文件冲突而失败。
2. Trae Hook 事件名、stdin 字段与 Claude Code 有差异，脚本中需使用 Trae 标准字段（`tool_name`、`tool_input`、`permissionDecision` 等）。
3. Hook 命令使用 `toolkit/python.exe` 或系统 `python`，需在实施时根据实际 PATH 调整。
4. `.trae/reviews/` 和 `.trae/.harness-state` 属于运行期产物，可加入 `.gitignore`。
5. 本计划不涉及前端 Flutter；如需覆盖，应在 `OASX-master/.trae/rules/` 下单独建规则。
