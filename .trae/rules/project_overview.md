---
alwaysApply: true
---

# OAS 魔改版项目概览

## 项目身份

- 本项目是基于 OAS 官方 dev 分支的本地单机二开版，仅供个人学习。
- 后端 API 固定运行于 `localhost:7788`。
- 前端 OASX (Flutter) 通过 API 与后端通信，配置修改通过 `module/config/config_watcher.py` 热重载。

## 网络与仓库约束

- `origin` 已重新指向个人 fork (`https://github.com/1359965050/OnmyojiAutoScript`)。
- 本地 `master` 以个人为准，禁止从 upstream (`runhey/OnmyojiAutoScript`) 直接 fetch/pull 覆盖本地改动。
- 本项目不会也不应将本地改动自动推送至 origin；任何提交/推送必须经用户明确确认。
- `deploy.yaml` 中 `AutoUpdate=true`、`KeepLocalChanges=true`，启动时会从个人 fork 自动拉取更新并保留本地改动。
- `git pull --ff-only` 可能因本地 untracked 文件与远程同名文件冲突而失败，遇冲突需手动清理后再拉取。

## 核心功能模块

当前调度器仅保留以下核心玩法，其余原 OAS 任务已被物理删除，不可用：

- 日常/周常：结界突破（退四打九战术）、结界挂卡/蹭卡（强制收取）、百鬼夜行（AI 追踪）、每周分享。
- 活动/副本：六道之门、兵藏秘境（英杰试炼）、八岐大蛇（仅队长/队员/单刷，无野队）、爬塔（ActivityShikigami，仅门票战模式）。
- 底层组件：通用战斗（GeneralBattle）挂机。

## 关键魔改逻辑

- 御魂/结算防卡死：结算点击坐标已避开战利品图标。
- 爬塔/活动门票 OCR 已做像素级精校。
- 百鬼夜行集成 ONNX 追踪器，自动锁定最高稀有度鬼王，遇冻结滤镜自动暂停。
- 结界挂卡强制在挂卡前检查并更换满级式神。
- ActivityShikigami 必须先进入主活动页 `page_act`，再进入具体模式子页，不可从 `page_main` 直接跳到子页。
- ActivityShikigami 标题 OCR ROI 为 `(149, 17, 130, 22)`，战斗按钮 ROI 为 `(245, 296, 29, 88)`，来自 CSV 文件。

## 配置与翻译

- 新增配置字段必须在 `module/config/config_model.py` 中注册 Pydantic 字段。
- 新增配置字段的中文显示必须同步更新三处翻译源：
  1. `OASX-master/lib/config/translation/i18n_cn.dart`
  2. `OASX-master/assets/i18n/zh-CN.json`
  3. `module/config/i18n/zh_CN.xml`
- 后端 `module/config/i18n/zh-CN.json` 由前端启动时通过 PUT 写入，通常无需手动维护。

## 敏感信息

- API Key、推送密钥、账号密码等敏感配置必须放入 `.env` 文件，不得写入源码或提交到仓库。
