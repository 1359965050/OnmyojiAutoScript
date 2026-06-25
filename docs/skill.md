OAS 魔改版项目上下文（AI 速查精简版）
1. 项目身份与硬性约束
定位：基于 OAS 官方 dev 分支的本地单机二开版，仅供个人学习。

网络隔离：

100% 无云端：已物理删除远程 origin，禁止 fetch/pull。

强制离线：/home/update_info 锁定 is_update=False；deploy.yaml 中 AutoUpdate=false。

推送禁用：所有推送通知（Notifier）已在底层硬编码关闭（enable=False）。

前后端协同：

后端 API 固定运行于 localhost:7788。

前端 OASX (Flutter) 通过 API 通信，配置修改实时生效（通过 config_watcher.py 热重载）。

2. 核心功能现状（可用模块）
当前调度器（SCHEDULER_PRIORITY）仅保留以下核心玩法，其余原 OAS 任务（御魂整理、悬赏、年兽、真蛇、绘卷、花车、对弈等）已被物理删除，不可用：

日常/周常：结界突破（退四打九战术）、结界挂卡/蹭卡（强制收取）、百鬼夜行（AI 追踪）、每周分享。

活动/副本：

六道之门（预留孔雀国适配）：已打通“选关 → 备战 → 战斗 → 首领结算”全流程；混沌之屿自动识别“精英”并挑战，非精英秒退；宁息之屿（商店）强制秒退，不购物。

兵藏秘境（英杰试炼）。

八岐大蛇（仅队长/队员/单刷，无野队）。

爬塔（ActivityShikigami）：仅保留门票战（Boss战）模式，已移除100体模式、体力战战斗配置、大富翁商店及体力战切换御魂等所有体力相关配置。默认运行顺序为 pass,boss。

配置细节：pass_battle_conf 现显示为“战斗配置”，专用于门票战；切换御魂选项仅保留“切换御魂/御魂分组/按名称切换/分组名称”。

底层组件：通用战斗（GeneralBattle）挂机。

3. 关键魔改逻辑（防坑与特性）
御魂/结算防卡死：

结算点击坐标已避开战利品图标，防止触发详情弹窗卡死。

爬塔/活动门票 OCR 已做像素级精校（防止图标动画干扰误识别）。

百鬼夜行：集成 ONNX 追踪器，自动锁定最高稀有度鬼王（SP>SSR>...），遇冻结滤镜自动暂停追踪。

结界挂卡：强制在挂卡前检查并更换满级式神（无可选开关）。

六道之门（孔雀国）闭环：（参见第 2 节活动/副本说明）。

4. 性能与启动优化（运维重点）
启动加速：OCR 库（ONNXRuntime）已改造为惰性加载（Lazy Import），若未启用 OCR 功能，启动时不加载 C++ DLL，大幅降低内存。

配置缓存：MainManager 已实现内存缓存，反复读取配置耗时从秒级降至毫秒级。

无任务处理：当无任务启用时，不再抛出异常导致 WebSocket 断开，而是返回空任务“Idle”，保持连接稳定。

5. 前端 GUI（OASX）适配须知
已隐藏菜单：侧边栏已移除“工具（Tool）”“统计服务（Stats）”“图像服务（Image）”；日常任务中删除了小猫咪、年兽、花合战等，周常中删除了真蛇、神秘商店。

本地化中文化：八岐大蛇身份选项已强制显示为“队长/队员/单独刷”。

翻译同步（重要）：

修改或新增配置字段时，必须同步更新以下三处翻译源，否则界面可能显示空标题或英文字段名：

前端编译翻译表：OASX-master/lib/config/translation/i18n_cn.dart（Flutter 编译时使用）
前端运行时覆盖：OASX-master/assets/i18n/zh-CN.json（前端启动时加载并覆盖应用缓存）
后端备用翻译源：module/config/i18n/zh_CN.xml（后端直接使用）
此外，后端 module/config/i18n/zh-CN.json 由前端启动时通过 PUT 写入，内容与 assets/i18n/zh-CN.json 保持一致；通常无需手动维护，但建议三处保持统一，以防意外。

6. 开发调试指引（二开必看）
新增配置：在 module/config/config_model.py 中注册 Pydantic 字段，OASX 会自动渲染。

新增配置字段的中文显示：除后端字段外，须同步更新第 5 节列出的三处翻译源（i18n_cn.dart、assets/i18n/zh-CN.json、zh_CN.xml）。

界面素材更新：若游戏 UI 改版，运行 ./dev_tools/assets_extract.py 重制识别图。

重要提醒：本项目所有 template.json 和 oas1.json 已清除了已删除模块的配置节点，请勿将旧版完整配置文件直接覆盖，否则会报 AttributeError。