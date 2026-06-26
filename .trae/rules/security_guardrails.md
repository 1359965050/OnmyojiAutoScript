---
alwaysApply: true
---

# 安全护栏

## 敏感文件保护

- 禁止直接写入 `.env`、`.env.local`、`*_local.yaml` 等敏感配置文件。
- 禁止在源码中硬编码 API Key、账号密码、推送密钥等敏感信息。

## Git 高危操作禁止

- 禁止执行 `rm -rf` 删除项目文件或目录。
- 禁止执行 `git push --force`、`git push -f`。
- 禁止执行 `git reset --hard`、`git checkout .`、`git clean -f` 等会丢弃本地改动的命令。
- 禁止从 upstream (`runhey/OnmyojiAutoScript`) fetch/pull/merge 覆盖本地。
- 禁止自动 `git commit` / `git push`；提交前必须经用户确认。

## 项目边界

- 禁止恢复已删除的模块：御魂整理、悬赏、年兽、真蛇、绘卷、花车、对弈等。
- 禁止修改 `Notifier` 启用状态；所有推送通知已在底层硬编码关闭。
- 禁止改动 `toolkit/`、`deploy/launcher/`、`toolkit/python310._pth` 等环境文件，除非用户明确授权。
- 涉及文件删除、移动、重命名前需询问用户。

## 网络与更新

- 自动更新源只能是个人 fork，禁止指向 upstream。
- 不要尝试绕过沙箱或 Hook 安全校验。
