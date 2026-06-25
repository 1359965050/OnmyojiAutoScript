# OAS 项目目录结构与功能说明

## 项目概述

OAS (OnmyojiAutoScript) 是一款基于 Alas 框架开发的阴阳师游戏自动化脚本。它实现了游戏内各种任务的自动执行，包括日常任务、副本挑战、活动玩法等，帮助玩家解放双手，自动完成游戏内的重复性操作。

**技术栈**:
- Python 3.10+
- FastAPI (Web 服务器)
- Pydantic (配置管理)
- OpenCV (图像处理)
- ppocr-onnx (OCR识别)
- Flutter (GUI客户端 - OASX)

---

## 目录结构总览

```
OAS/
├── .trae/                    # Trae IDE 配置
│   └── skills/
│       └── oas/
│           └── SKILL.md
├── OASX-master/              # Flutter GUI 客户端
│   ├── android/              # Android 构建配置
│   ├── assets/               # Flutter 资源
│   ├── ios/                  # iOS 构建配置
│   ├── linux/                # Linux 构建配置
│   ├── macos/                # macOS 构建配置
│   ├── web/                  # Web 构建配置
│   ├── windows/              # Windows 构建配置
│   └── pubspec.yaml          # Flutter 依赖配置
├── assets/                   # 静态资源
│   └── i18n/                 # 国际化资源文件
├── bin/                      # 二进制文件
│   ├── hermit/               # Hermit APK
│   └── scrcpy/               # Scrcpy 服务器
├── config/                   # 配置模板
│   └── template.json         # 配置模板文件
├── deploy/                   # 部署工具
├── dev_tools/                # 开发工具
├── docs/                     # 文档
│   └── skill.md              # 本文件
├── module/                   # 核心模块（重点）
│   ├── atom/                 # 原子操作
│   ├── base/                 # 基础工具
│   ├── config/               # 配置管理
│   ├── daemon/               # 守护进程
│   ├── device/               # 设备控制
│   ├── handler/              # 处理器
│   ├── notify/               # 通知模块
│   ├── ocr/                  # OCR识别
│   ├── server/               # Web服务器
│   ├── exception.py          # 异常定义
│   └── logger.py             # 日志系统
├── scratch/                  # 临时测试脚本
├── tasks/                    # 游戏任务（重点）
├── script.py                 # 脚本入口
├── server.py                 # Web 服务器入口
├── requirements.txt          # 依赖清单
└── requirements-in.txt       # 内部依赖清单
```

---

## 核心模块详解

### 1. module/base/ - 基础工具模块

**功能定位**: 提供通用的工具函数、装饰器、定时器等基础功能，被项目其他模块广泛依赖。

#### 1.1 utils/utils.py - 核心工具函数

**功能**: 提供图像处理、坐标计算、随机数生成、模块动态加载等通用工具函数。

**关键函数**:

| 函数名 | 参数 | 返回值 | 功能说明 |
|--------|------|--------|----------|
| `random_rectangle_point(area)` | `area`: 区域坐标 `(x1, y1, x2, y2)` | `tuple`: `(x, y)` | 在指定区域内随机取点，使用正态分布模拟人手操作 |
| `crop(image, area, copy=True)` | `image`: 图像数组, `area`: 裁剪区域 | `np.ndarray` | 裁剪图像，超出边界部分填充黑色 |
| `resize(image, size)` | `image`: 图像数组, `size`: 目标尺寸 `(w, h)` | `np.ndarray` | 调整图像大小 |
| `rgb2gray(image)` | `image`: RGB图像 | `np.ndarray` | RGB转灰度图 |
| `rgb2hsv(image)` | `image`: RGB图像 | `np.ndarray` | RGB转HSV颜色空间 |
| `color_similar(color1, color2, threshold=10)` | `color1, color2`: RGB颜色, `threshold`: 容差 | `bool` | 判断两种颜色是否相似 |
| `load_module(moduleName, moduleFile)` | `moduleName`: 模块名, `moduleFile`: 文件路径 | `module` | 动态加载Python模块 |
| `area_offset(area, offset)` | `area`: 区域, `offset`: 偏移量 | `tuple` | 移动区域坐标 |
| `area_limit(area1, area2)` | `area1`: 目标区域, `area2`: 限制区域 | `tuple` | 将区域限制在另一个区域内 |
| `point_in_area(point, area, threshold=5)` | `point`: 点坐标, `area`: 区域 | `bool` | 判断点是否在区域内 |

#### 1.2 timer.py - 定时器类

**功能**: 提供任务等待、超时检测的定时器功能。

**关键类**:

```python
class Timer:
    def __init__(self, limit, count=None)  # 初始化定时器
    def start(self)                         # 启动定时器
    def reset(self)                         # 重置定时器
    def reached(self)                       # 判断是否到达时间
    def current(self)                       # 获取当前时间
    def wait(self)                          # 等待直到到达时间
```

#### 1.3 decorator.py - 装饰器

**功能**: 提供各种装饰器，增强代码功能。

**关键装饰器**:

| 装饰器 | 功能说明 |
|--------|----------|
| `cached_property` | 缓存属性值，首次访问后缓存结果 |
| `run_once` | 确保函数只执行一次 |
| `del_cached_property` | 删除缓存的属性 |

#### 1.4 filter.py - 过滤器

**功能**: 用于任务调度时的条件过滤，支持正则表达式匹配。

---

### 2. module/atom/ - 原子操作模块

**功能定位**: 封装游戏交互的最小单元操作，包括图片匹配、OCR识别、点击、滑动等。

#### 2.1 image.py - 图片匹配

**功能**: `RuleImage` 类，封装图片模板匹配逻辑，支持单尺度和多尺度匹配。

**关键方法**:

| 方法名 | 参数 | 返回值 | 功能说明 |
|--------|------|--------|----------|
| `__init__(roi_front, roi_back, method, threshold, file)` | 见下方 | - | 初始化图片匹配规则 |
| `match(image, threshold=None)` | `image`: 截图, `threshold`: 匹配阈值 | `bool` | 执行模板匹配 |
| `match_multi_scale(image, scales, scale_range)` | 支持多尺度匹配 | `bool` | 多尺度模板匹配 |
| `match_all(image, threshold)` | 返回所有匹配结果 | `list[tuple]` | 返回所有匹配位置 |
| `coord()` | - | `tuple`: `(x, y)` | 获取匹配位置的随机点击坐标 |
| `front_center()` | - | `tuple`: `(x, y)` | 获取匹配区域的中心坐标 |

**参数说明**:
- `roi_front`: 前置ROI，匹配成功后更新为实际位置
- `roi_back`: 后置ROI，搜索区域
- `method`: 匹配方法 (`Template matching` 或 `Sift Flann`)
- `threshold`: 匹配阈值 (0.0-1.0，越高越严格)
- `file`: 模板图片路径

#### 2.2 ocr.py - OCR识别

**功能**: `RuleOcr` 类，封装文字识别逻辑。

**识别模式 (`OcrMode`)**:

| 模式 | 功能说明 |
|------|----------|
| `FULL` | 全匹配模式，检测区域内是否有文字 |
| `SINGLE` | 单字匹配模式，检测是否匹配指定关键字 |
| `DIGIT` | 数字匹配模式，检测是否匹配指定数字 |
| `DIGITCOUNTER` | 数字计数器模式 |
| `DURATION` | 时间匹配模式 |

#### 2.3 click.py / long_click.py - 点击操作

**功能**: 定义点击和长按操作的坐标规则。

#### 2.4 swipe.py - 滑动操作

**功能**: 定义滑动操作的起点、终点和时长。

#### 2.5 list.py - 列表操作

**功能**: 封装列表查找与操作，支持图片列表和OCR列表。

---

### 3. module/device/ - 设备控制模块

**功能定位**: 封装与设备的交互，包括截图、点击、滑动、应用管理等底层操作。

#### 3.1 device.py - 设备核心类

**功能**: `Device` 类是设备控制的核心，继承自 `Platform`, `Screenshot`, `Control`, `AppControl`。

**关键属性**:

| 属性 | 类型 | 功能说明 |
|------|------|----------|
| `detect_record` | `set` | 检测记录集合，用于防卡检测 |
| `click_record` | `deque(maxlen=15)` | 点击记录队列，用于检测重复点击 |
| `stuck_timer` | `Timer` | 防卡定时器 (60秒) |
| `stuck_timer_long` | `Timer` | 长防卡定时器 (300秒) |

**关键方法**:

| 方法名 | 功能说明 |
|--------|----------|
| `__init__(config)` | 初始化设备，自动启动模拟器（如果需要） |
| `screenshot()` | 截图，包含防卡检测 |
| `stuck_record_add(button)` | 添加防卡记录 |
| `stuck_record_clear()` | 清空防卡记录 |
| `stuck_record_check()` | 检查是否卡住，超时抛出 `GameStuckError` |
| `click_record_add(button)` | 添加点击记录 |
| `click_record_check()` | 检查重复点击，过多时抛出 `GameTooManyClickError` |
| `release_during_wait()` | 等待期间释放资源 |

#### 3.2 control.py - 控制操作

**功能**: `Control` 类，封装点击、长按、滑动等控制操作，支持多种控制方式。

**支持的控制方式**:

| 方式 | 说明 |
|------|------|
| `ADB` | 通过ADB命令控制 |
| `uiautomator2` | 通过uiautomator2库控制 |
| `minitouch` | 通过minitouch协议控制 |
| `window_message` | Windows窗口消息控制 |
| `scrcpy` | 通过scrcpy控制 |

**关键方法**:

| 方法名 | 参数 | 功能说明 |
|--------|------|----------|
| `click(x, y, control_name)` | `x, y`: 坐标, `control_name`: 控制名称 | 执行点击操作 |
| `long_click(x, y, duration)` | `duration`: 长按时长(秒) | 执行长按操作 |
| `swipe(p1, p2, duration)` | `p1, p2`: 起点和终点 | 执行滑动操作 |
| `swipe_vector(vector, box)` | `vector`: 滑动向量 | 带随机偏移的滑动 |
| `drag(p1, p2, segments)` | `segments`: 分段数 | 带抖动的拖拽 |

#### 3.3 screenshot.py - 截图操作

**功能**: `Screenshot` 类，封装截图操作，支持多种截图方式。

**支持的截图方式**:

| 方式 | 说明 |
|------|------|
| `ADB` | ADB命令截图 |
| `ADB_nc` | ADB命令截图(无压缩) |
| `uiautomator2` | uiautomator2截图 |
| `DroidCast` | DroidCast截图 |
| `scrcpy` | scrcpy截图 |
| `window_background` | Windows窗口背景截图 |
| `nemu_ipc` | Nemu模拟器IPC截图 |

**关键方法**:

| 方法名 | 功能说明 |
|--------|----------|
| `screenshot()` | 执行截图，包含屏幕尺寸和黑屏检查 |
| `save_screenshot(genre, interval)` | 保存截图到日志目录 |
| `screenshot_interval_set(interval)` | 设置截图间隔 |
| `check_screen_size()` | 检查屏幕尺寸是否为1280x720 |
| `check_screen_black()` | 检查是否为黑屏 |

#### 3.4 app_control.py - 应用管理

**功能**: `AppControl` 类，封装应用启动、停止、状态检查等操作。

**关键方法**:

| 方法名 | 功能说明 |
|--------|----------|
| `app_is_running()` | 检查游戏是否正在运行 |
| `app_start()` | 启动游戏应用 |
| `app_stop()` | 停止游戏应用 |
| `dump_hierarchy()` | 导出UI层级结构 |
| `xpath_to_button(xpath)` | 将XPath转换为按钮对象 |

---

### 4. module/config/ - 配置管理模块

**功能定位**: 管理用户配置、任务调度、配置文件读写等。

#### 4.1 config_model.py - 配置数据模型

**功能**: `ConfigModel` 类，基于 Pydantic 的配置数据模型，定义所有任务的配置结构。

**数据类型扩展**:

| 类型 | 说明 | 示例 |
|------|------|------|
| `TimeDelta` | 时间间隔 | `"01 02:30:00"` (1天2小时30分) |
| `DateTime` | 日期时间 | `"2024-01-01 12:00:00"` |
| `Time` | 时间 | `"12:00:00"` |
| `MultiLine` | 多行文本 | 用于GUI多行输入 |

#### 4.2 config.py - 配置管理核心

**功能**: `Config` 类，配置管理的核心类，继承自 `ConfigState`, `ConfigManual`, `ConfigWatcher`, `ConfigMenu`。

**关键方法**:

| 方法名 | 功能说明 |
|--------|----------|
| `__init__(config_name)` | 初始化配置，加载指定配置文件 |
| `reload()` | 重新加载配置 |
| `save()` | 保存配置到文件 |
| `update_scheduler()` | 更新任务调度器 |
| `get_next()` | 获取下一个要执行的任务 |
| `task_call(task, force_call)` | 调用指定任务 |
| `task_delay(task, success, target)` | 设置任务下次运行时间 |

**任务调度数据结构**:

```python
class Function:
    enable: bool          # 是否启用
    command: str          # 任务命令名
    next_run: datetime    # 下次运行时间
    priority: int         # 优先级
```

#### 4.3 scheduler.py - 任务调度器

**功能**: `TaskScheduler` 类，实现任务调度逻辑。

**调度规则 (`ScheduleRule`)**:

| 规则 | 说明 |
|------|------|
| `FILTER` | 使用过滤器规则调度 |
| `FIFO` | 先进先出，按时间顺序调度 |
| `PRIORITY` | 按优先级调度，同优先级按时间顺序 |

---

### 5. module/ocr/ - OCR识别模块

**功能定位**: 封装文字识别功能，基于 ppocr-onnx 实现。

#### 5.1 ppocr.py - OCR系统封装

**功能**: `TextSystem` 类，封装 ppocr-onnx 的识别功能。

**关键方法**:

| 方法名 | 功能说明 |
|--------|----------|
| `ocr_single_line(img)` | 识别单行文本 |
| `detect_and_ocr(img)` | 检测并识别图像中的所有文本 |

#### 5.2 rpc.py - OCR RPC服务

**功能**: 管理OCR服务的启动和停止，支持远程调用。

---

### 6. module/server/ - Web服务器模块

**功能定位**: 提供 HTTP API 接口，支持远程控制和状态查询。

#### 6.1 app.py - FastAPI应用

**功能**: FastAPI 应用入口，配置路由和中间件。

**路由注册**:

| 路由 | 功能说明 |
|------|----------|
| `/` | 首页路由 (`home_app`) |
| `/script/` | 脚本管理路由 (`script_app`) |
| `/tool/` | 工具路由 (`tool_app`) |

> 注：`/stats/`（统计服务）和 `/image/`（图像服务）已移除。

#### 6.2 script_router.py - 脚本管理

**功能**: 提供脚本启动、停止、状态查询等API。

#### 6.3 main_manager.py - 主进程管理

**功能**: 管理多个脚本实例的启动和停止。

---

### 7. module/exception.py - 异常定义

**功能定位**: 定义项目中使用的所有异常类型。

**异常类型**:

| 异常类 | 触发场景 | 处理方式 |
|--------|----------|----------|
| `ScriptError` | 脚本逻辑错误 | 记录日志，通知用户，退出 |
| `ScriptEnd` | 脚本正常结束 | 正常退出 |
| `GameStuckError` | 游戏卡住 | 保存错误日志，重启游戏 |
| `GameBugError` | 游戏客户端异常 | 保存错误日志，重启游戏 |
| `GameTooManyClickError` | 重复点击过多 | 保存错误日志，重启游戏 |
| `EmulatorNotRunningError` | 模拟器未运行 | 尝试启动模拟器 |
| `GameNotRunningError` | 游戏未运行 | 启动游戏 |
| `GamePageUnknownError` | 未知页面 | 等待用户切换到支持的页面 |
| `RequestHumanTakeover` | 需要人工干预 | 记录日志，通知用户，退出 |
| `TaskEnd` | 任务正常结束 | 继续下一个任务 |

---

### 8. module/logger.py - 日志系统

**功能定位**: 封装日志记录功能，支持控制台、文件、Flutter GUI多种输出方式。

**日志处理器**:

| 处理器 | 输出目标 | 格式 |
|--------|----------|------|
| `RichHandler` | 控制台 | 彩色格式化输出 |
| `RichFileHandler` | 文件 | 详细日志格式 |
| `FlutterHandler` | Flutter GUI | 简洁格式 |

**扩展方法**:

| 方法名 | 功能说明 |
|--------|----------|
| `hr(title, level)` | 输出分隔线 |
| `attr(name, text)` | 输出属性信息 |
| `attr_align(name, text, align)` | 对齐输出属性 |
| `set_file_logger(name)` | 设置文件日志 |
| `set_func_logger(func)` | 设置函数日志回调 |

---

## 游戏任务详解

### 1. tasks/base_task.py - 任务基类

**功能定位**: 所有游戏任务的基类，提供通用的任务执行框架。

**继承关系**: `BaseTask` → `GlobalGameAssets` → `CostumeBase`

**关键方法**:

| 方法名 | 功能说明 |
|--------|----------|
| `__init__(config, device)` | 初始化任务，加载配置和设备 |
| `screenshot()` | 截图，包含突发事件检测（如好友邀请） |
| `appear(target, interval, threshold)` | 判断目标是否出现，支持间隔控制 |
| `appear_then_click(target, action)` | 出现目标后执行点击操作 |
| `wait_until_appear(target, timeout)` | 等待目标出现，超时返回False |
| `wait_until_disappear(target)` | 等待目标消失 |
| `swipe(swipe, interval)` | 执行滑动操作 |
| `click(click, interval)` | 执行点击或长按操作 |
| `ocr_appear(target, interval)` | OCR识别目标是否出现 |
| `ocr_appear_click(target, action)` | OCR识别并点击 |
| `list_find(target, name, max_swipe)` | 在列表中查找目标 |
| `ui_reward_appear_click()` | 处理奖励弹窗 |
| `set_next_run(task, success, target)` | 设置任务下次运行时间 |

**突发事件处理**:

`BaseTask` 在截图时会检测以下突发事件：
- 好友邀请（勾协、粮协等）
- 网络异常
- 其他弹窗

---

### 2. tasks/GameUi/game_ui.py - 游戏UI管理

**功能定位**: 管理游戏内页面导航，自动识别当前页面并跳转到目标页面。

**继承关系**: `GameUi` → `BaseTask` → `GameUiAssets`

**关键方法**:

| 方法名 | 功能说明 |
|--------|----------|
| `ui_get_current_page()` | 获取当前页面，支持页面注册表 |
| `ui_goto_page(dest_page)` | 导航到指定页面 |
| `ui_goto(destination)` | 执行页面导航（内部方法） |
| `build_reverse_path_dict(destination)` | 构建页面导航路径（反向BFS） |
| `try_close_unknown_page()` | 尝试关闭未知页面 |
| `_execute_path(path)` | 执行页面导航路径 |

**页面注册机制**:

通过 `PageRegistry` 动态注册所有页面模块，支持自动发现 `tasks/**/page.py` 文件。

---

### 3. 任务分类

#### 日常任务类

| 任务目录 | 功能说明 | 主要文件 |
|----------|----------|----------|
| `DailyTrifles/` | 日常小杂事（签到、猫咪喂食等） | `script_task.py`, `page.py` |
| `WeeklyTrifles/` | 每周小杂事 | `script_task.py` |
| `GoldYoukai/` | 金币妖怪 | `script_task.py` |
| `ExperienceYoukai/` | 经验妖怪 | `script_task.py` |
| `DemonEncounter/` | 悬赏封印 | `script_task.py`, `data/answer.py` |

#### 副本挑战类

| 任务目录 | 功能说明 | 主要文件 |
|----------|----------|----------|
| `Orochi/` | 八岐大蛇（御魂副本） | `script_task.py` |
| `EvoZone/` | 觉醒副本 | `script_task.py` |
| `EternitySea/` | 永生之海 | `script_task.py` |
| `GoryouRealm/` | 业原火 | `script_task.py` |
| `SixRealms/` | 六道之门 | `script_task.py`, `oas_ocr.py` |
| `FallenSun/` | 日轮之城 | `script_task.py` |

#### 阴阳寮类

| 任务目录 | 功能说明 | 主要文件 |
|----------|----------|----------|
| `GuildBanquet/` | 寮宴会 | `script_task.py` |
| `GuildActivityMonitor/` | 寮活动监控 | `config.py` |
| `KekkaiActivation/` | 结界激活（上卡） | `script_task.py` |
| `KekkaiUtilize/` | 结界利用（蹭卡） | `script_task.py` |
| `RyouToppa/` | 结界突破 | `script_task.py` |
| `Dokan/` | 道馆 | `script_task.py`, `dokan_scene.py` |

#### 活动玩法类

| 任务目录 | 功能说明 | 主要文件 |
|----------|----------|----------|
| `AbyssShadows/` | 深渊暗影 | `script_task.py` |
| `ActivityShikigami/` | 式神活动 | `script_task.py`, `page.py` |
| `AreaBoss/` | 地域鬼王 | `script_task.py`, `config_boss.py` |
| `BondlingFairyland/` | 契灵 | `script_task.py`, `battle.py` |
| `DyeTrials/` | 染色试练 | `script_task.py` |
| `Hyakkiyakou/` | 百鬼夜行（AI智能撒豆） | `script_task.py`, `agent/`, `slave/` |
| `MetaDemon/` | 逢魔之时 | `script_task.py` |
| `OrochiMoans/` | 大蛇悲鸣 | `config.py` |
| `RealmRaid/` | 领地进攻 | `script_task.py` |
| `Secret/` | 秘闻副本 | `script_task.py` |
| `Sougenbi/` | 青吉鬼 | `script_task.py` |

#### 战斗类

| 任务目录 | 功能说明 | 主要文件 |
|----------|----------|----------|
| `Hunt/` | 狩猎战 | `script_task.py` |
| `Duel/` | 斗技 | `script_task.py` |
| `HeroTest/` | 试胆大会 | `script_task.py` |

#### 通用组件类

| 任务目录 | 功能说明 | 主要文件 |
|----------|----------|----------|
| `Component/` | 通用组件（购买、召唤等） | `Buy/`, `Summon/`, `SwitchSoul/` |
| `GameUi/` | 游戏UI管理（页面导航） | `game_ui.py`, `page.py`, `assets.py` |
| `GlobalGame/` | 全局游戏事件（好友邀请等） | `assets.py`, `config_emergency.py` |
| `General/` | 通用配置 | `config.py` |
| `GotoMain/` | 返回主界面 | `script_task.py` |
| `Restart/` | 重启游戏 | `script_task.py`, `login.py` |

---

### 4. 任务结构说明

每个任务目录通常包含以下文件：

| 文件 | 功能说明 | 示例 |
|------|----------|------|
| `script_task.py` | 任务主逻辑，继承 `BaseTask` | `class ScriptTask(BaseTask):` |
| `assets.py` | 资源定义（图片、OCR、点击等） | 通过JSON加载资源 |
| `config.py` | 任务配置类（基于 Pydantic） | `class TaskName(ConfigBase):` |
| `config_xxx.py` | 额外配置类（如特殊参数） | `config_boss.py`, `config_emergency.py` |
| `page.py` | 页面定义（如果任务需要） | `@register_page('PageName')` |
| `res/` 或 `xx/` | 资源目录，包含图片和JSON配置 | `image.json`, `click.json` |

**资源JSON配置格式**:

```json
// image.json
{
  "I_BUTTON_NAME": {
    "roi_front": [0, 0, 100, 100],
    "roi_back": [500, 300, 700, 500],
    "method": "Template matching",
    "threshold": 0.8,
    "file": "res/button.png"
  }
}

// click.json
{
  "C_BUTTON_NAME": {
    "coord": [600, 400]
  }
}

// ocr.json
{
  "O_TEXT_NAME": {
    "roi": [500, 300, 700, 350],
    "keyword": "确认",
    "mode": "SINGLE"
  }
}
```

---

## 部署与工具模块

### deploy/ - 部署工具

| 文件 | 功能说明 |
|------|----------|
| `installer.py` | 安装器，处理依赖安装和环境配置 |
| `adb.py` | ADB管理，包括安装、启动、版本检测 |
| `config.py` | 部署配置，读取 deploy.yaml |
| `emulator.py` | 模拟器管理，支持多种模拟器（MuMu、Nox等） |
| `git.py` | Git操作封装，包括克隆、拉取、版本检测 |
| `logger.py` | 部署工具专用日志 |
| `patch.py` | 补丁管理，应用更新补丁 |
| `pip.py` | Pip包管理，安装和升级依赖 |
| `process.py` | 进程管理，检查和杀死进程 |
| `utils.py` | 部署工具通用函数 |
| `launcher/` | 启动器相关资源 |
| `fluentui.py` | Fluent UI 风格的 GUI 组件 |

### dev_tools/ - 开发工具

| 文件 | 功能说明 |
|------|----------|
| `assets_extract.py` | 资源提取工具，从游戏截图中提取模板 |
| `decorator.py` | 开发用装饰器 |
| `generate_requirements.py` | 生成依赖清单 |
| `get_images.py` | 获取图片工具，从设备截图 |
| `template_update.py` | 模板更新工具，批量更新资源 |

---

## 入口文件说明

### script.py

**功能定位**: 脚本运行入口，负责任务调度和执行。

**核心流程**:

```
1. 初始化配置 (Config)
   ↓
2. 初始化设备 (Device)
   ↓
3. 设置文件日志 (set_file_logger)
   ↓
4. 进入调度循环 (loop)
   ↓
5. 获取下一个任务 (get_next_task)
   ↓
6. 检查设备状态
   ↓
7. 执行任务 (run(command))
   ↓
8. 处理任务结果
   ↓
9. 检查失败次数（连续3次失败退出）
   ↓
10. 返回步骤4
```

**关键方法**:

| 方法名 | 功能说明 |
|--------|----------|
| `run(command)` | 执行指定任务，动态加载模块 |
| `get_next_task()` | 获取下一个要执行的任务 |
| `_handle_wait_during_idle(next_run)` | 处理空闲期间的等待策略 |
| `_wait_close_game(next_run)` | 关闭游戏等待 |
| `_wait_goto_main(next_run)` | 返回主界面等待 |
| `_wait_stay_there(next_run)` | 原地等待 |
| `save_error_log()` | 保存错误日志和截图 |

### server.py

**功能定位**: Web服务器入口，提供 HTTP API。

**核心流程**:

```
1. 设置时区为北京时间
   ↓
2. 创建事件循环策略（Windows专用）
   ↓
3. 解析命令行参数（host, port, key, run）
   ↓
4. 启动OCR服务 (ensure_ocr_server_started)
   ↓
5. 启动FastAPI应用 (uvicorn.run)
   ↓
6. 监听指定端口
   ↓
7. 关闭时停止OCR服务
```

> 注：原流程中的图像服务 (`ensure_image_server_started`) 已移除。

---

## 配置文件说明

### config/template.json

**功能定位**: 配置模板，定义所有可配置参数的默认值和说明。

### module/config/argument/

| 文件 | 功能说明 |
|------|----------|
| `args.json` | 参数定义，包含所有任务的可配置参数 |
| `argument.yaml` | 参数默认值 |
| `default.yaml` | 默认配置 |
| `gui.yaml` | GUI相关配置（显示名称、分组等） |
| `menu.json` | 菜单配置，定义GUI菜单结构 |
| `override.yaml` | 覆盖配置，用于强制覆盖某些参数 |
| `task.yaml` | 任务配置，定义任务的调度规则 |

### 用户配置文件

用户配置文件存储在 `config/` 目录下，命名格式为 `<config_name>.json`，例如 `oas1.json`。

---

## 快速定位指南

### 开发新功能时

1. **确定任务类型**: 判断新功能属于日常任务、副本挑战、活动玩法还是通用组件
2. **创建任务目录**: 在 `tasks/` 下创建新目录
3. **编写配置类**: 创建 `config.py`，继承 `ConfigBase`，定义任务配置参数
4. **注册配置**: 在 `module/config/config_model.py` 中导入并注册新配置类
5. **定义参数**: 在 `module/config/argument/args.json` 中添加参数定义
6. **定义资源**: 创建 `assets.py`，通过JSON加载所需的图片、OCR、点击等资源
7. **编写任务逻辑**: 创建 `script_task.py`，继承 `BaseTask`，实现任务主逻辑
8. **添加资源文件**: 在资源目录中添加图片和JSON配置
9. **测试验证**: 运行脚本测试新功能

### 修复 Bug 时

1. **定位任务**: 根据 Bug 描述找到对应的任务目录
2. **检查资源**: 检查 `assets.py` 和资源配置文件，确认资源定义正确
3. **调试逻辑**: 修改 `script_task.py` 中的任务逻辑
4. **添加日志**: 在关键位置添加日志输出
5. **测试验证**: 运行脚本测试修复效果
6. **保存错误日志**: 如果问题复现，查看 `log/error/` 目录下的错误日志和截图

### 修改设备交互时

1. **定位模块**: 需要修改点击/滑动逻辑时，查看 `module/device/control.py`
2. **修改控制方式**: 在 `module/device/method/` 下找到对应的控制方式实现
3. **修改截图逻辑**: 查看 `module/device/screenshot.py`
4. **添加新控制方式**: 如果需要新的控制方式，在 `method/` 下创建新文件并在 `control.py` 中注册

### 修改配置系统时

1. **定位模块**: 需要修改配置结构时，查看 `module/config/config_model.py`
2. **修改参数定义**: 修改 `module/config/argument/args.json`
3. **修改调度逻辑**: 修改 `module/config/scheduler.py`
4. **修改配置模型**: 修改 `tasks/Component/config_base.py` 添加新的数据类型

### 处理游戏更新时

1. **更新资源**: 更新 `tasks/**/res/` 目录下的图片资源
2. **调整坐标**: 修改 `click.json`、`swipe.json` 中的坐标
3. **调整识别**: 修改 `image.json`、`ocr.json` 中的识别区域和阈值
4. **测试验证**: 运行脚本测试更新后的效果

---

## 关键数据流

```
用户配置 (config/<name>.json)
        ↓
ConfigModel (module/config/config_model.py) ← Pydantic验证和解析
        ↓
Config (module/config/config.py) ← 配置管理核心
        ↓
TaskScheduler (module/config/scheduler.py) ← 任务调度
        ↓
Script.loop() (script.py) ← 主循环
        ↓
Script.run(command) → 动态加载 TaskModule (tasks/*/script_task.py)
        ↓
BaseTask (tasks/base_task.py) ← 任务基类
        ↓
Device (module/device/device.py) ← 设备管理
        ↓
├── Screenshot (module/device/screenshot.py) ← 截图
│       ↓
│   ADB / Scrcpy / Droidcast ← 截图方式
├── Control (module/device/control.py) ← 控制操作
│       ↓
│   ADB / Minitouch / Scrcpy ← 控制方式
└── AppControl (module/device/app_control.py) ← 应用管理
        ↓
游戏设备（模拟器或手机）
```

---

## 异常处理流程

```
任务执行过程中
        ↓
发生异常
        ↓
├── TaskEnd → 正常结束，继续下一个任务
├── GameNotRunningError → 启动游戏，重新执行
├── GameStuckError / GameTooManyClickError → 保存错误日志，重启游戏，重新执行
├── GameBugError → 保存错误日志，重启游戏，重新执行
├── GamePageUnknownError → 保存错误日志，请求人工干预
├── ScriptError → 记录日志，通知用户，退出
├── RequestHumanTakeover → 记录日志，通知用户，退出
└── 其他异常 → 保存错误日志，通知用户，退出
```

---

## 日志系统说明

### 日志输出位置

| 输出目标 | 文件路径 | 说明 |
|----------|----------|------|
| 控制台 | 标准输出 | Rich彩色格式化 |
| 文件 | `log/<date>_<config_name>.txt` | 详细日志 |
| 错误日志 | `log/error/<timestamp>/` | 包含截图和日志 |
| Flutter GUI | 通过WebSocket | 实时推送 |

### 日志清理

日志系统会自动清理7天前的旧日志文件，由 `cleanup_logs()` 函数处理。

---

## 扩展阅读

- [OAS 文档网站](https://runhey.github.io/OnmyojiAutoScript-website/)
- [开发文档](https://runhey.github.io/OnmyojiAutoScript-website/docs/development/preamble)
- [用户手册](https://runhey.github.io/OnmyojiAutoScript-website/docs/user-manual/getting-started)
- [Alas 框架](https://github.com/LmeSzinc/AzurLaneAutoScript)
- [ppocr-onnx](https://github.com/triwinds/ppocr-onnx)