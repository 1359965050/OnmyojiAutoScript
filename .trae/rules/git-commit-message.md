---
alwaysApply: true
scene: git_message
---

# Git 提交信息生成规则

## 格式
- 标题：`type(scope): 简短中文描述`
- 类型：
  - feat: 新功能
  - fix: 修复 bug
  - refactor: 重构
  - docs: 文档
  - test: 测试
  - chore: 杂项/构建/依赖
- scope: 本次改动的模块名，如 Config、Updater、ActivityShikigami、金币妖怪；不确定时用 *
- 标题长度不超过 50 字，结尾不加句号
- 标题后空一行，正文用 `- ` 列表列出关键改动

## 正文要求
- 每条说明一个独立的改动点
- 包含"做了什么"和"目的/影响"
- 优先列出用户可见的行为变化，内部细节次之
- 不涉及的秘密配置、API 密钥等不要写入

## 示例
feat(Config): 添加任务导入导出功能

- 新增 ConfigTaskError 异常类处理任务配置错误
- 添加任务键名校验和归一化方法 validate_task_key
- 实现任务 JSON 解析、校验和导入功能
- 添加任务配置导入导出接口 endpoint
- 支持单个任务配置的复制和传输功能
- 实现任务配置的脱敏导出机制
