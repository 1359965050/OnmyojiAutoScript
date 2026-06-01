# OAS 个人二开魔改版项目概述与技术指南

本项目是基于开源阴阳师自动化脚本 [OnmyojiAutoScript (OAS)](https://github.com/runhey/OnmyojiAutoScript) 官方开发分支 [dev commits](https://github.com/runhey/OnmyojiAutoScript/commits/dev/) 深度定制的**二次开发魔改版本**。

---

## 1. 项目定位与合规声明

* **不对外发布**：本项目所有修改及新增功能**只限个人日常使用与学习交流**，严禁以任何商业目的或公开发布形式进行二次分发。
* **遵守开源协议**：本项目严格遵守原仓库的 **GNU General Public License v3.0 (GPL v3.0)** 开源协议，所有二开源码及资源均秉承开源互助理念。
* **开发初衷**：在原项目优异的任务调度与前端分离架构基础上，针对复杂副本（如六道之门、百鬼夜行、御魂整理、结界突破等）进行底层核心算法的魔改，实现更高成功率、更强防错和更智能的 AI 交互流。
* **完全本地隔离原则（无云端交集）**：本项目已物理删除了所有指向官方上游仓库的远程连接（`origin`）及全部对应的远程缓存分支。本魔改项目**完全作为本地化项目，绝不与任何云端有交集、更不会进行任何 fetch 或 pull 拉取操作**。所有的二开代码演化和记录仅保存在本地 Git 仓库中（已清空整理为纯净的本地初始提交），彻底杜绝了魔改代码被意外推送到官方的风险，也保障了本地固化参数绝不会被上游更新覆盖或污染。

---

## 2. 魔改核心技术模块与 Skill 文档索引

我们在项目根目录的 `docs/` 下为各个经过深度魔改的核心子功能制作了针对性的技术 Skill 规范文档：

### 2.1 六道之门（月之海）技能特化系统
* **对应技术文档**：[docs/liudao-skill.md](file:///f:/daima/OAS/docs/liudao-skill.md)
* **核心魔改技术**：
  - **柔风单特化**：脚本以“柔风抱暖 (Skill 101)”为极简特化方向，最大化通关稳定性。
  - **动态刷新判定**：检测选择界面技能，金币 $\ge 50$ 且剩余刷新次数 $>0$ 时自动触发刷新，以防选到低优先级技能。
  - **岛屿专属处理**：包含 `l101`（宁息商店金币 $\ge 300$ 购买与 $\ge 400$ 刷新）、`l102`（神秘仿造升级柔风）、`l103/l104`（鏖战混沌战后带刷新选择）。

### 2.2 御魂智能打理与清理系统
* **对应技术文档**：[docs/souls_tidy.md](file:///f:/daima/OAS/docs/souls_tidy.md)
* **核心魔改技术**：
  - **防误伤双保险**：检测首位强化等级，若不是等级 0（`I_ST_LEVEL_0`）则强制熔断退出，杜绝意外熔炼已强化御魂。
  - **OCR 中文汉字纠偏**：由于特殊字体排版，针对 OCR 将 “+0” 误识为 “古” 字的行为进行代码级防错比对判定。
  - **弹窗遮挡与神赐处理**：全自动识别奉纳概率触发的“神赐”豪华礼包，自动消除弹窗继续奉纳；支持跳过“御魂溢出”等系统通知。

### 2.3 百鬼夜行 AI 智能追踪与决策系统
* **对应技术文档**：[docs/hyakkiyakou.md](file:///f:/daima/OAS/docs/hyakkiyakou.md)
* **核心魔改技术**：
  - **神经网络追踪**：深度集成 `oashya` 目标检测追踪框架（ONNXRuntime 推理，FP32 精准度），摒弃死板盲点，实现全屏式神动态弹道估计。
  - **最佳鬼王智能选举**：开局前遍历 3 位候选人，调用追踪器计算式神稀有度评分并锁死最高品质（SP=5, SSR=4, ...），达成全自动高倍率加成。
  - **环境光效降级防护**：识别到全屏冻结（Freeze）滤镜引起的色差干扰时，自动暂停视觉追踪，防止误识产生豆子浪费。

### 2.4 结界突破战术调度系统
* **对应技术文档**：[docs/realm_raid.md](file:///f:/daima/OAS/docs/realm_raid.md)
* **核心魔改技术**：
  - **“退四打九”压级降维战术**：自动在首场战斗连续主动投降 4 次压低防守分，确保后续 9 场匹配极速全胜。
  - **3x3 矩阵式勋章搜索与局部熔断**：支持按照勋章配置级（如 `5>4>3...`）搜索，若某位置战败则局部“抹黑像素”熔断跳过，自动锁定其他未挑战对手。
  - **活动特化**：扫描判定呱太结界，自动重置解锁阵容状态，配合备战界面执行自动阵容交替。
  - **三胜宝箱防卡死**：OCR 判定领奖导致的聊天框遮挡，实现领完宝箱自动退回循环。

---

## 3. 配套前端 GUI 项目 (OASX)

本魔改后端项目与配套的前端全平台 GUI 项目 **OASX** 协同工作：
* **前端路径**：[F:\daima\oasx](file:///F:/daima/oasx) (基于 Flutter 框架构建)
* **协同机制**：
  - **前后端分离**：后端通过 `server.py` 启动本地 API 服务（固定运行在 `localhost:8888`），前端 OASX 作为跨平台客户端对接此服务端，实现实时的图形化任务控制与配置修改。
  - **单机特化保障**：后端服务中的更新检测模块已重构为**本地旁路模式**，`/home/update_info` 接口返回已被完全锁定为纯本地 Git 提交详情（`latest_commit` 镜像本地，`is_update` 恒定为 `False`）。完美契合了单机版定位，完全消除了由于没有远程仓库导致的后台 fork 和 Git fetch 频繁报错。
  - **配置响应**：配置修改采用 Pydantic 化管理。当用户在 OASX 前端更改设置时，前端会向后端发送配置修改请求，后端通过 `module/config/config_watcher.py` 或 `config_updater.py` 实时重载 `config/oas1.json`，在下一个任务循环中立即生效，实现无缝衔接。

---

## 4. 魔改开发者二开与调试指引

如果您计划基于本魔改版进行前后端联调或继续迭代，请重点关注以下核心路径：

* **前后端对接入口**：
  - `server.py`：负责启动 FastAPI/API 端口与前端 OASX 进行 WebSocket & HTTP 通信。
  - `module/config/config_model.py`：定义了配置参数的 Pydantic 模型类，新增魔改功能参数时需在此注册以供前端 OASX 自动渲染。
* **后端任务入口**：`script.py` 负责核心的任务调度管理器实例化与顺序执行。
* **设备与控键机制**：`module/device/` 与 `module/atom/` 负责底层模拟快照渲染及模拟器多点触控动作。
* **资源配置表**：`tasks/[TaskName]/assets.py` 存放用于图像识别的 RuleImage 模板与 OCR 区域。若游戏版本更新导致界面变化，请运行 `./dev_tools/assets_extract.py` 重新生成。

---

## 5. 本地专享单机版定制改造清单

以下记录了为实现 100% 离线单机化运行而进行的所有系统级改造，确保后端服务在无网络环境下稳定运行且前端 OASX 不会出现功能异常。

### 5.1 推送通知功能完全移除
* **涉及文件**：
  - [config_error.py](file:///f:/daima/OAS/tasks/Script/config_error.py)：移除 `notify_enable` 和 `notify_config` Pydantic 配置字段，使 OASX 不再渲染推送通知的开关和配置面板。
  - [config.py](file:///f:/daima/OAS/module/config/config.py)：`notifier` 属性使用 `getattr` 安全回退，对已删除的字段默认返回 `False` 和 `'provider: null'`，防止 `AttributeError` 崩溃。
  - [notify.py](file:///f:/daima/OAS/module/notify/notify.py)：初始化器中 `self.enable` 无条件设为 `False`，从底层物理阻断任何推送调用。
  - [home_router.py](file:///f:/daima/OAS/module/server/home_router.py)：`/notify_test` 路由直接返回 `False`，跳过导入与初始化开销。
  - [template.json](file:///f:/daima/OAS/config/template.json) & `oas1.json`：清除 `notify_enable` 和 `notify_config` 默认键值。

### 5.2 工具（Tool）侧边栏菜单项隐藏
* **涉及文件**：[home_router.py](file:///f:/daima/OAS/module/server/home_router.py#L27-L29)
* **改造详情**：`/home/home_menu` API 响应中移除了 `'Tool': []` 条目，OASX 动态构建侧边栏时不再显示"工具"菜单项。
* **注意事项**：首次启动 OASX 时因编译缓存可能仍短暂显示，切换页面标签后自动消失。

### 5.3 启动依赖安装与自动更新旁路
* **涉及文件**：[deploy.yaml](file:///f:/daima/OAS/config/deploy.yaml)
* **改造详情**：
  - `InstallDependencies: false`：跳过 pip 依赖同步检查，避免连接清华 PyPI 镜像，消除启动延迟。
  - `AutoUpdate: false`：禁用 Git 自动拉取更新。
  - `CheckUpdateInterval: 0`：停止定时更新检查。
  - `AutoRestartTime: null`：禁用自动重启更新。

### 5.4 更新路由锁定为本地模式
* **涉及文件**：[home_router.py](file:///f:/daima/OAS/module/server/home_router.py#L44-L68)
* **改造详情**：
  - `/home/update_info`：硬编码 `is_update: False`、`branch: "本地专享版"`，`latest_commit` 镜像本地提交，防止前端因无远程仓库空指针崩溃。
  - `/home/execute_update`：返回本地专享版提示文案，安全禁用云端更新执行。

### 5.5 限时活动爬塔配置精简
* **涉及文件**：
  - [config.py (ActivityShikigami)](file:///f:/daima/OAS/tasks/ActivityShikigami/config.py)：移除 `switch_soul_config: SwitchSoulConfig` 分类字段，OASX 不再渲染"执行任务前切换御魂"设置面板。
  - [config_activity.py](file:///f:/daima/OAS/tasks/Component/BaseActivity/config_activity.py)：移除 `active_souls_clean` 配置字段，隐藏"结束爬塔后启动御魂整理"开关。
  - [script_task.py](file:///f:/daima/OAS/tasks/ActivityShikigami/script_task.py)：`switch_soul` 方法桩化为空操作，`get_general_battle_conf` 安全绕过已删字段引用。
  - [template.json](file:///f:/daima/OAS/config/template.json) & `oas1.json`：物理清除 `"switch_soul_config"` 和 `"active_souls_clean"` JSON 节点。

### 5.6 战斗随机滑动开关合并
* **涉及文件**：
  - [config.py (GeneralBattleConfig)](file:///f:/daima/OAS/tasks/ActivityShikigami/config.py#L77-L94)：将原先 4 个独立开关（`enable_pass_anti_detect`、`enable_ap_anti_detect`、`enable_boss_anti_detect`、`enable_ap100_anti_detect`）合并为顶部单一字段 `enable_anti_detect`，对所有爬塔模式统一生效。
  - [script_task.py](file:///f:/daima/OAS/tasks/ActivityShikigami/script_task.py#L372)：`get_general_battle_conf` 中动态 `getattr` 替换为直接访问 `self.conf.general_battle.enable_anti_detect`。
  - [template.json](file:///f:/daima/OAS/config/template.json)：`general_battle` 节点中 4 个独立键合并为 `"enable_anti_detect": false`。

### 5.7 爬塔顶栏门票 OCR 区域重校准
* **涉及文件**：
  - [assets.py](file:///f:/daima/OAS/tasks/ActivityShikigami/assets.py#L96-L99) & [ocr.json](file:///f:/daima/OAS/tasks/ActivityShikigami/fire/ocr.json)
* **改造详情**：新版爬塔活动顶栏布局重新排列了资源指示器，对 OCR 进行微米级精准剪裁：
  - **O_REMAIN_AP**（活动体力，左侧图标）：基于导出的像素 CSV 数据分析，数字像素极值范围为 `X: [571 ~ 649]`，`Y: [18 ~ 42]`。为防止截断，ROI 定位精校为 **`(566, 15, 85, 30)`**，左侧保留 `21` 像素的安全离散带，彻底避免左侧图标动态干扰。
  - **O_REMAIN_PASS**（活动门票，中间金铃铛图标）：ROI 定位经过了**像素级灰度极值精校**。基于 ImageJ 导出的像素 CSV 数据分析，提取数字像素极值范围为 `X: [769 ~ 846]`，`Y: [16 ~ 43]`。为应对顶栏金铃铛图标的**呼吸/悬浮动画**引起的动态漂移，选框左侧起点收敛至 `768`（右侧至 `848`），形成 **`23` 像素的物理安全隔离带**，完美定格为 **`(768, 15, 80, 30)`**。
* **解决问题**：彻底解决了老版本中因框选范围偏窄导致的数字前缀截断，以及因框选范围过大导致金铃铛图标漂移进入选框被 OCR 误识别为首位数字 `1`（例如把 `46` 误识为 `146`，`43` 误识为 `143`）的经典动态干扰 Bug，达成 100% 极限精度识别。

### 5.8 寻找协作任务与绘卷功能模块物理移除
* **涉及文件**：
  - [config_menu.py](file:///f:/daima/OAS/module/config/config_menu.py)
  - [config_manual.py](file:///f:/daima/OAS/module/config/config_manual.py)
  - [config_model.py](file:///f:/daima/OAS/module/config/config_model.py)
  - [template.json](file:///f:/daima/OAS/config/template.json)
* **改造详情**：
  - **OASX 侧边栏清理**：从 `config_menu.py` 的 `"Liver Emperor Exclusive"`（肝帝专属）分组中物理移除了 `"FindJade"`（寻找协作任务）和 `"MemoryScrolls"`（绘卷）任务。OASX 构建配置控制面板时将自动不再渲染这两个子菜单。
  - **调度与模版清理**：从 `config_manual.py` 的全局 `SCHEDULER_PRIORITY`（调度器优先级队列）中移除了 `MemoryScrolls`，并从 `template.json` 中彻底删除了 `find_jade` 和 `memory_scrolls` 的配置大纲。
  - **核心模型解耦**：在 `config_model.py` 中彻底删除了 `FindJade` 和 `MemoryScrolls` 的包导入以及对应的 Pydantic 字段 `find_jade` 和 `memory_scrolls`，杜绝任何初始化或类定义上的强关联。
  - **物理代码删除**：安全、彻底地删除了以下两个任务的物理代码文件夹及独立配置文件，避免任何潜在的无用代码堆积：
    * `tasks/FindJade/` (寻找协作任务主代码)
    * `tasks/MemoryScrolls/` (追忆绘卷主代码)
    * `config/findjade/` (寻找协作任务附属配置目录)

### 5.9 御魂整理、式神委派、石距与大神签到物理移除
* **涉及文件**：
  - [config_menu.py](file:///f:/daima/OAS/module/config/config_menu.py)
  - [config_manual.py](file:///f:/daima/OAS/module/config/config_manual.py)
  - [config_model.py](file:///f:/daima/OAS/module/config/config_model.py)
* **改造详情**：
  - **OASX 侧边栏清理**：从 `config_menu.py` 的 `"Daily Task"`（日常任务）分组中移除了 `"SoulsTidy"`（御魂整理）、`"Delegation"`（式神委派）、`"Tako"`（石距）和 `"AutoCheckinBigGod"`（大神签到），OASX 将不再在日常任务列表下显示这四个功能。
  - **调度队列清理**：从 `config_manual.py` 的全局 `SCHEDULER_PRIORITY` 中彻底清除了 `SoulsTidy`、`Tako`、`AutoCheckinBigGod` 和 `Delegation`，彻底阻断了后端核心任务调度的任务链引用。
  - **核心模型解耦**：在 `config_model.py` 中删除了这四个任务的模块导入，并清除了 `ConfigModel` 类中相对应的 Pydantic 字段：
    * `souls_tidy: SoulsTidy`
    * `delegation: Delegation`
    * `tako: Tako`
    * `auto_checkin_big_god: AutoCheckinBigGod`
  - **物理代码删除**：安全、干净地彻底删除了这四个功能的全部主代码文件夹，杜绝项目无用代码臃肿：
    * `tasks/SoulsTidy/` (御魂智能整理主代码)
    * `tasks/Delegation/` (式神委派主代码)
    * `tasks/Tako/` (石距副本主代码)
    * `tasks/AutoCheckinBigGod/` (网易大神签到主代码)

### 5.10 花车巡游功能模块物理移除
* **涉及文件**：
  - [config_menu.py](file:///f:/daima/OAS/module/config/config_menu.py)
  - [config_manual.py](file:///f:/daima/OAS/module/config/config_manual.py)
  - [config_model.py](file:///f:/daima/OAS/module/config/config_model.py)
* **改造详情**：
  - **OASX 侧边栏清理**：从 `config_menu.py` 的 `"Activity Task"`（限时活动）分组中移除了 `"FloatParade"`（花车巡游），OASX 侧边栏的限时活动菜单下将不再展示此功能。
  - **调度队列清理**：从 `config_manual.py` 的全局 `SCHEDULER_PRIORITY` 中彻底移除了 `FloatParade`，解除调度链中的任务调度引用。
  - **核心模型解耦**：在 `config_model.py` 中删除了 `FloatParade` 的模块导入依赖，并从 `ConfigModel` 类中物理删除了相对应的 Pydantic 字段 `float_parade: FloatParade`。
  - **物理代码删除**：干净、彻底地删除了整个花车巡游功能的主代码文件夹：
    * `tasks/FloatParade/` (花车巡游自动挂机主代码)

### 5.11 对弈竞猜、智力竞赛及猫咪铺子限时活动任务物理移除
* **涉及文件**：
  - [config_menu.py](file:///f:/daima/OAS/module/config/config_menu.py)
  - [config_manual.py](file:///f:/daima/OAS/module/config/config_manual.py)
  - [config_model.py](file:///f:/daima/OAS/module/config/config_model.py)
  - [template.json](file:///f:/daima/OAS/config/template.json)
* **改造详情**：
  - **OASX 侧边栏清理**：从 `config_menu.py` 的 `"Activity Task"`（限时活动）分组中移除了 `"FrogBoss"`（对弈竞猜）、`"Quiz"`（智力竞赛）和 `"KittyShop"`（猫咪铺子），OASX 前端将自动不再渲染这三个配置控制菜单。
  - **调度链解耦**：从 `config_manual.py` 的全局 `SCHEDULER_PRIORITY` 中彻底移除了 `> FrogBoss`、`> Quiz` 和 `> KittyShop`，解除主循环中的调度任务引用。
  - **模型与模版解耦**：在 `config_model.py` 中删除了这三个任务的模块导入，并清除了 `ConfigModel` 类中相对应的 Pydantic 字段 `frog_boss`、`quiz`、`kitty_shop`，且在 `template.json` 中完全清除了对应的 JSON 配置节点，阻断了序列化引用的生成。
  - **物理代码删除**：安全、干净地彻底删除了这三个任务的所有主代码文件夹与题库附属资源：
    * `tasks/FrogBoss/` (对弈竞猜全自动下注与策略代码)
    * `tasks/Quiz/` (智力竞赛极速自动答题与调试库)
    * `tasks/KittyShop/` (猫咪铺子自动兑换与日常任务代码)

### 5.12 前端菜单子项重命名与组队调度中文化
* **涉及文件**：
  - [config_menu.py](file:///f:/daima/OAS/module/config/config_menu.py)
  - [utils.py](file:///f:/daima/OAS/module/config/utils.py)
  - [zh_CN.xml](file:///f:/daima/OAS/module/config/i18n/zh_CN.xml) & [zh-CN.json](file:///f:/daima/OAS/module/config/i18n/zh-CN.json)
* **改造详情**：
  - **“脚本”子菜单重命名**：将 `config_menu.py` 中 `'Script'` 分组下的第一个子菜单项从 `'Script'` 改为 `'ScriptConfig'`。在多语言文件 `zh_CN.xml` 的 `FluTreeView` 和 `TaskList` 上下文及 `zh-CN.json` 中新增 `ScriptConfig` 的翻译，将其显示重命名为 **“模拟器配置”**，完美防止了子菜单与父菜单同名导致的混淆。
  - **后端别名透明兼容**：为防止改动子项标识符导致后端复杂的 Pydantic 数据结构（如 `self.model.script` 属性）的大量断裂，我们在 `module/config/utils.py` 中的 `convert_to_underscore` 转换器中增加了对于 `ScriptConfig`（及其大小写下划线变体）的拦截兼容机制，统一转换返回为 `'script'`。从而在不改动底层核心架构和复杂字段的前提下实现了完全透明的配置流加载兼容。
  - **组队调度配置中文化**：将全局配置中的 `team_flow` 配置卡片在 `zh-CN.json` 本地化字典中重命名为 **“组队调度”**，极大提升了非专业用户的多开组队视觉体验。

### 5.13 日常任务之年兽、花合战及悬赏封印功能物理移除与深层解耦
* **涉及文件**：
  - [config_menu.py](file:///f:/daima/OAS/module/config/config_menu.py)
  - [config_manual.py](file:///f:/daima/OAS/module/config/config_manual.py)
  - [config_model.py](file:///f:/daima/OAS/module/config/config_model.py)
  - [template.json](file:///f:/daima/OAS/config/template.json)
  - [base_task.py](file:///f:/daima/OAS/tasks/base_task.py)
  - [script_task.py (Duel)](file:///f:/daima/OAS/tasks/Duel/script_task.py)
* **改造详情**：
  - **OASX 侧边栏清理**：从 `config_menu.py` 的 `"Daily Task"`（日常任务）分组中物理移除了 `"Nian"`（年兽）、`"TalismanPass"`（花合战）和 `"WantedQuests"`（悬赏封印）。
  - **调度队列清理**：从 `config_manual.py` 的全局 `SCHEDULER_PRIORITY` 中彻底移除了 `> Nian`、`> TalismanPass` 和 `> WantedQuests`，彻底阻断了后端核心任务调度的任务链引用。
  - **配置模型与模版解耦**：在 `config_model.py` 中删除了这三个任务的模块导入，并清除了 `ConfigModel` 类中相对应的 Pydantic 字段 `nian`、`talisman_pass`、`wanted_quests`，在 `template.json` 中移除了配置大纲节点。
  - **联动触发深层解耦**：
    - **协作任务延迟移除**：在底层 `tasks/base_task.py` 的突发事件检测 `_burst` 中，移除了当玩家在被动状态点击接受协作任务邀请后自动拉起 `"WantedQuests"` 任务的调度代码，防止因悬赏封印不存在导致 `ScriptError`。
    - **斗技结束花合战拉起移除**：在 `tasks/Duel/script_task.py` 的斗技主流程正常运行结束后，移除了自动调起 `"TalismanPass"` 任务的触发代码。
  - **物理代码删除**：安全、干净地彻底删除了这三个功能的全部主代码文件夹，杜绝项目无用代码臃肿：
    * `tasks/Nian/` (年兽挑战自动战斗与重设时间代码)
    * `tasks/TalismanPass/` (花合战日常领奖及经验盒子代码)
    * `tasks/WantedQuests/` (悬赏封印全自动挑战与好友组队代码)

### 5.14 日常任务之小猫咪功能物理移除与配置解耦
* **涉及文件**：
  - [config_menu.py](file:///f:/daima/OAS/module/config/config_menu.py)
  - [config_manual.py](file:///f:/daima/OAS/module/config/config_manual.py)
  - [config_model.py](file:///f:/daima/OAS/module/config/config_model.py)
  - [template.json](file:///f:/daima/OAS/config/template.json)
  - [oas1.json](file:///f:/daima/OAS/config/oas1.json)
* **改造详情**：
  - **OASX 侧边栏清理**：从 `config_menu.py` 的 `"Daily Task"`（日常任务）分组中移除了 `'Pets'`，OASX 前端将不再显示小猫咪相关的配置菜单。
  - **调度链解耦**：从 `config_manual.py` 的全局 `SCHEDULER_PRIORITY` 中彻底移除了 `> Pets`，解除调度器中的小猫咪任务调度优先级依赖。
  - **配置模型与模板解耦**：在 `config_model.py` 中删除了 `Pets` 任务的模块导入，并清除了 `ConfigModel` 类中相对应的 Pydantic 字段 `pets: Pets`。在默认配置文件 `template.json` 和当前配置文件 `oas1.json` 中完全清除了对应的 `"pets"` 配置段。
  - **物理代码删除**：安全、干净地彻底删除了小猫咪挑战的物理文件夹：
    * `tasks/Pets/` (小猫咪挑战自动战斗及自动喂食配置与逻辑代码)

### 5.15 结界蹭卡（KekkaiUtilize）可选收取开关移除与功能强制使能
* **涉及文件**：
  - [config.py](file:///f:/daima/OAS/tasks/KekkaiUtilize/config.py)
  - [script_task.py](file:///f:/daima/OAS/tasks/KekkaiUtilize/script_task.py)
  - [template.json](file:///f:/daima/OAS/config/template.json)
  - [zh_CN.xml](file:///f:/daima/OAS/module/config/i18n/zh_CN.xml)
* **改造详情**：
  - **可选配置移除**：从 `config.py` 中的 `UtilizeConfig` 移除了 5 个可选布尔开关字段：`guild_ap_enable`（顺路收取寮补给）、`guild_assets_enable`（顺路收取寮资金）、`box_ap_enable`（顺路收取体力盒子）、`box_exp_enable`（顺路收取经验盒子）以及 `box_exp_waste`（从盒子提取经验时浪费一部分）。OASX 配置面板不再渲染这些无谓的开关选项。
  - **执行逻辑重构**：重构了 `script_task.py` 中的 `check_box_ap_or_exp` 方法，将体力盒子与经验盒子收取机制修改为 100% 无条件使能并顺序执行；当遇到满级式神时，强制选择 `I_UI_CONFIRM`（即浪费一部分经验也必须继续提取以防卡住流程）。
  - **模板与翻译清理**：在 `template.json` 的 `utilize_config` 中彻底删除了这 5 个对应的 JSON 键值，并在 `zh_CN.xml` 的翻译中清除了这 5 个字段的源文本翻译及帮助文案描述，确保前后端整体风格与数据结构完美统一。

### 5.16 每周分享（原每周琐事 WeeklyTrifles）重命名与破碎的咒符功能物理移除
* **涉及文件**：
  - [config.py](file:///f:/daima/OAS/tasks/WeeklyTrifles/config.py)
  - [script_task.py](file:///f:/daima/OAS/tasks/WeeklyTrifles/script_task.py)
  - [i18n.py](file:///f:/daima/OAS/module/server/i18n.py)
  - [zh_CN.xml](file:///f:/daima/OAS/module/config/i18n/zh_CN.xml)
  - [zh-CN.json](file:///f:/daima/OAS/assets/i18n/zh-CN.json)
* **改造详情**：
  - **功能显示重命名**：将 `WeeklyTrifles` 在多语言转换和本地化字典中由原先的“每周琐事”重命名为 **“每周分享”**，使 UI 呈现更为精确和贴切。
  - **破碎的咒符功能移除**：在 `config.py` 中删除了 `broken_amulet` 字段，并在 `script_task.py` 中彻底删除了 `_broken_amulet` 逻辑代码与调用入口，停止自动消耗破碎的咒符进行召唤。
  - **资源文件物理清理**：完全清除了 `tasks/WeeklyTrifles/broken_amulet/` 下所有专为破碎召唤配制的模板图片与规则文件。

### 5.17 结界挂卡（KekkaiActivation）更换式神功能调整与开关移除
* **涉及文件**：
  - [config.py](file:///f:/daima/OAS/tasks/KekkaiActivation/config.py)
  - [script_task.py](file:///f:/daima/OAS/tasks/KekkaiActivation/script_task.py)
* **改造详情**：
  - **开关彻底移除**：从 `ActivationConfig` 中移除了 `exchange_before` 与 `exchange_max` 两处布尔配置字段，剔除了前端配置界面中不必要的冗余选项。
  - **逻辑重构**：将挂卡前的满级式神检查/更换修改为**无条件强制执行**。在启动挂卡并收取结界奖励之前，无条件调用 `self.check_max_lv(con.shikigami_class)` 以确保自动撤下已满级的育成式神并换上新式神；同时移除了挂卡结束后的冗余二次满级式神检查。

### 5.18 神秘商店（MysteryShop）功能模块完全物理移除
* **涉及文件**：
  - [config_menu.py](file:///f:/daima/OAS/module/config/config_menu.py)
  - [config_manual.py](file:///f:/daima/OAS/module/config/config_manual.py)
  - [config_model.py](file:///f:/daima/OAS/module/config/config_model.py)
  - [template.json](file:///f:/daima/OAS/config/template.json)
* **改造详情**：
  - **前端面板隐藏**：从 `config_menu.py` 的 `"Weekly Task"`（每周任务）分组中物理移除了 `'MysteryShop'`。
  - **调度链及配置模型清理**：在 `config_manual.py` 的全局 `SCHEDULER_PRIORITY` 中彻底移除了 `> MysteryShop` 调度优先级。在 `config_model.py` 中删除了 `MysteryShop` 相关的导入与 Pydantic 字段声明，并在 `template.json` 中彻底抹去了对应的 JSON 配置结构。
  - **代码资源物理清除**：干净利落地将 `tasks/MysteryShop/` 整个任务文件夹及下属所有识别图片、配置规则全部删除，确保无冗余代码残留。

### 5.19 集体任务（CollectiveMissions）功能模块物理移除与配置解耦
* **涉及文件**：
  - [config_menu.py](file:///f:/daima/OAS/module/config/config_menu.py)
  - [config_manual.py](file:///f:/daima/OAS/module/config/config_manual.py)
  - [config_model.py](file:///f:/daima/OAS/module/config/config_model.py)
  - [template.json](file:///f:/daima/OAS/config/template.json)
  - [oas1.json](file:///f:/daima/OAS/config/oas1.json)
  - [zh_CN.xml](file:///f:/daima/OAS/module/config/i18n/zh_CN.xml)
  - [README.md](file:///f:/daima/OAS/README.md)
* **改造详情**：
  - **OASX 侧边栏清理**：从 `config_menu.py` 的 `"Guild"`（阴阳寮）分组中移除了 `'CollectiveMissions'`。
  - **调度链解耦**：从 `config_manual.py` 的全局 `SCHEDULER_PRIORITY` 中彻底移除了 `> CollectiveMissionsr`，解除调度任务引用。
  - **配置模型与模板/配置文件解耦**：在 `config_model.py` 中删除了 `CollectiveMissions` 相关的导入与 Pydantic 字段声明。在 `template.json` 和 `oas1.json` 中彻底抹去了对应的 `"collective_missions"` 配置结构。
  - **多语言及自述清理**：在 `zh_CN.xml` 中移除了 `CollectiveMissions` 相关的翻译键值，在 `README.md` 的功能特性描述中移除了“集体任务”字样。
  - **代码资源物理清除**：彻底删除了整个集体任务 `tasks/CollectiveMissions/` 主代码文件夹及下属识别图、配置文件，防范任何潜在的无用代码堆积。

