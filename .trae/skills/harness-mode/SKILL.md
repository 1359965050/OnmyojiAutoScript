---
name: harness-mode
description: 切换 OAS 项目的工作模式与阶段，控制审查严格度。
---

# Harness Mode

## 支持的命令

- `/harness-mode full` — 完整检查，所有规则生效。
- `/harness-mode hotfix` — 紧急修复，跳过部分非关键审查。
- `/harness-mode tweak` — 微调，仅保护敏感文件和 .env。
- `/harness-phase design` — 设计阶段，宽松审查，不检查调试残留。
- `/harness-phase build` — 构建阶段，正常审查。
- `/harness-phase fix` — 修复阶段，>5 个文件变更即告警。
- `/harness-status` — 显示当前 mode 和 phase。

## 状态文件

状态持久化在 `.trae/.harness-state`：

```json
{
  "mode": "full",
  "phase": "build"
}
```

## 模式联动

- 设置 `hotfix` 时，自动建议 `phase` 为 `fix`。
- 设置 `tweak` 时，自动建议 `phase` 为 `design`。

## 各模式对 Hook 的影响

### full

- PreToolUse 拦截所有高危命令和敏感文件写入。
- PostToolUse 对所有 `.py` 变更执行 `py_compile`。
- Stop Hook 生成完整审查报告，敏感文件改动阻断停止。

### hotfix

- 仍拦截 `.env` 写入和 upstream 拉取。
- 放宽文件数/调试残留检查。
- Stop Hook 仅记录关键风险。

### tweak

- 仅保护 `.env` 和敏感文件。
- 不主动阻断 Stop，仅追加审查日志。

## 阶段影响

### design

- 允许更多探索性改动。
- 不检查 TODO/FIXME。

### build

- 正常审查强度。

### fix

- 超过 5 个文件变更时，Stop Hook 建议拆分提交或确认范围。
