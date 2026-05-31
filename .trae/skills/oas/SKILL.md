---
name: "oas"
description: "OAS (OnmyojiAutoScript) 阴阳师自动化脚本开发助手。Invoke when user asks about OAS development, creating new tasks, modifying existing tasks, or understanding the OAS framework architecture."
---

# OAS (OnmyojiAutoScript) 开发助手

## 项目概述

OAS 是一个基于 Python 的《阴阳师》手游自动化脚本，借鉴 Alas (AzurLaneAutoScript) 的设计思路，支持 7×24 小时长期运行。项目采用多实例化设计，支持多开游戏和任务配置。

### 核心特点
- **全程接管**：一键运行，无需繁琐设置
- **多实例支持**：通过 config 驱动每个脚本实例
- **通用设计**：`module/` 文件夹下为通用代码，`tasks/` 文件夹下为游戏相关代码
- **分辨率限制**：仅支持 1280x720 分辨率
- **平台限制**：仅支持 Windows + 安卓模拟器（不支持真机）

## 项目架构

```
OnmyojiAutoScript/
├── script.py              # 脚本主入口
├── gui.py                 # GUI 主入口
├── server.py              # 服务器入口
├── module/                # 通用模块
│   ├── atom/              # 原子操作（点击、滑动、OCR、图像匹配等）
│   ├── base/              # 基础工具类
│   ├── config/            # 配置管理
│   ├── device/            # 设备控制（模拟器、截图、操作）
│   ├── gui/               # GUI 实现（FluentUI for QML）
│   ├── ocr/               # OCR 识别（ppocr-onnx）
│   └── server/            # 服务端
├── tasks/                 # 游戏任务（每个任务一个文件夹）
│   ├── base_task.py       # 任务基类
│   ├── GameUi/            # 游戏界面导航
│   ├── Component/         # 通用组件（战斗、御魂切换等）
│   └── [TaskName]/        # 具体任务
│       ├── assets.py      # 资源定义
│       ├── config.py      # 配置定义
│       ├── script_task.py # 任务逻辑
│       └── res/           # 资源文件（图片、json）
└── deploy/                # 部署相关
```

## 核心概念

### 1. 脚本任务的三大核心

#### 用户选项 (User Options)
- 用户自定义设置，影响脚本执行
- 支持 string、int、float 等多种类型
- 通过 pydantic 管理配置

#### 控制设备 (Device Control)
- 模拟器控制、游戏启停
- 截图、点击、滑动操作
- 位于 `module/device/`

#### 过程元素 (Process Elements)
- 图片识别、点击位置等运行时参数
- 通过 Assets 管理系统配置
- 借助 GUI 快速生成任务所需参数

### 2. 基本运作模式

OAS 使用循环截图判断的模式，而非固定等待：

```python
while 1:
    self.screenshot()
    if self.appear_then_click(self.I_AREA_BOSS, threshold=0.6, interval=2):
        continue
    if self.appear_then_click(self.I_BATTLE_1, interval=1):
        continue
    if self.appear(self.I_FILTER, threshold=0.6):
        break
```

**优势**：
- 高配电脑运行快，低配电脑兼容好
- 点击失败自动重试
- 无需关心执行顺序

### 3. 异常处理

- **GameStuckError**：无操作连续截图超过 1 分钟（战斗中 5 分钟）
- **GameTooManyClickError**：最后 15 次操作中，某项操作 >= 12 次，或两项操作都 >= 6 次

## 开发规范

### 代码规范

1. **注释**：使用 PyCharm 默认模板
```python
"""
Description of the function or method.

:param parameter_name: Description of the parameter.

:return: Description of the return value.
"""
```

2. **类型注解**：强制使用类型注解，不在注释中说明类型

3. **代码长度**：
   - 函数注释占 1/3 ~ 1/2
   - 一个函数不超过一个屏幕
   - 一个 .py 文件不超过 500 行

4. **命名**：不允许使用中文或拼音

### 任务开发流程

#### 1. 创建任务目录

在 `tasks/` 下创建新任务文件夹：
```
tasks/NewTask/
├── __init__.py
├── assets.py      # 资源定义
├── config.py      # 配置定义
├── script_task.py # 任务逻辑
├── page.py        # 页面定义（可选）
└── res/           # 资源文件
    ├── image.json
    ├── click.json
    ├── ocr.json
    └── swipe.json
```

#### 2. 定义配置 (config.py)

```python
from pydantic import BaseModel, Field

from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.config_scheduler import Scheduler

class NewTaskConfig(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    # 自定义配置项
    enable_feature: bool = Field(default=True, description="Enable feature")
    count: int = Field(default=10, ge=1, le=100)
```

#### 3. 定义资源 (assets.py)

```python
from module.atom.image import RuleImage
from module.atom.click import RuleClick
from module.atom.ocr import RuleOcr
from module.atom.swipe import RuleSwipe
from tasks.base_task import BaseTask

class NewTaskAssets:
    # 图片资源
    I_BUTTON = RuleImage(
        roi_front=(x, y, w, h),  # 匹配区域
        roi_back=(x, y, w, h),   # 点击区域
        method="Template matching",
        file_name="button.png"
    )
    
    # 点击资源
    C_BUTTON = RuleClick(
        roi_front=(x, y, w, h),
        name="click_button"
    )
    
    # OCR 资源
    O_TEXT = RuleOcr(
        roi=(x, y, w, h),
        mode="Full",
        method="Default",
        keyword="目标文字"
    )
```

#### 4. 编写任务逻辑 (script_task.py)

```python
from tasks.base_task import BaseTask
from tasks.NewTask.assets import NewTaskAssets
from tasks.NewTask.config import NewTaskConfig
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_target
from module.exception import TaskEnd
from module.logger import logger

class ScriptTask(BaseTask, NewTaskAssets, GameUi):
    def run(self) -> bool:
        """任务主入口"""
        # 获取配置
        config: NewTaskConfig = self.config.new_task
        
        # 导航到目标页面
        self.ui_get_current_page()
        self.ui_goto(page_target)
        
        # 执行任务逻辑
        self.do_something()
        
        # 设置下次运行时间
        self.set_next_run(task='NewTask', success=True, finish=True)
        
        # 结束任务
        raise TaskEnd
    
    def do_something(self):
        """具体任务逻辑"""
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_BUTTON, interval=2):
                continue
            if self.appear(self.I_TARGET):
                break
```

### 常用 API

#### BaseTask 方法

```python
# 截图
self.screenshot()

# 图像匹配
self.appear(target: RuleImage, interval=None, threshold=None)
self.appear_then_click(target, action=None, interval=None, threshold=None)

# 多尺度匹配
self.appear_multi_scale(target, interval=None, threshold=None, scales=None, scale_range=None)
self.appear_then_click_multi_scale(target, action=None, interval=None, threshold=None, scale_range=None)

# OCR
self.ocr_appear(target: RuleOcr, interval=None)
self.ocr_appear_click(target, action=None, interval=None)

# 等待
self.wait_until_appear(target, skip_first_screenshot=False, wait_time=None)
self.wait_until_disappear(target)
self.wait_until_stable(target, timer=None, timeout=None)

# 点击/滑动
self.click(click: RuleClick | RuleImage | RuleOcr, interval=None)
self.swipe(swipe: RuleSwipe, interval=None)

# UI 导航
self.ui_get_current_page()
self.ui_goto(destination: Page, confirm_wait=0, timeout=60)
self.ui_click(click, stop, interval=1, timeout=None)
self.ui_click_until_disappear(click, interval=1)

# 列表操作
self.list_find(target: RuleList, name, max_swipe=10)
self.list_appear_click(target, interval=None, max_swipe=10)

# 设置下次运行
self.set_next_run(task, finish=False, success=None, server=True, target=None)
```

#### Device 方法

```python
# 截图
image = self.device.screenshot()

# 点击
self.device.click(x, y, control_name=None)
self.device.long_click(x, y, duration, control_name=None)

# 滑动
self.device.swipe(p1=(x1, y1), p2=(x2, y2), control_name=None)

# 应用控制
self.device.app_start()
self.device.app_stop()
self.device.app_is_running()

# 模拟器控制
self.device.emulator_start()
self.device.emulator_stop()
```

## 资源管理

### 资源文件格式

#### image.json
```json
{
  "I_BUTTON": {
    "roi_front": [100, 200, 50, 30],
    "roi_back": [100, 200, 50, 30],
    "file_name": "button.png"
  }
}
```

#### click.json
```json
{
  "C_BUTTON": {
    "roi_front": [100, 200, 50, 30]
  }
}
```

#### ocr.json
```json
{
  "O_TEXT": {
    "roi": [100, 200, 100, 30],
    "mode": "Full",
    "keyword": "目标文字"
  }
}
```

#### swipe.json
```json
{
  "S_SWIPE": {
    "roi_front": [100, 400, 50, 50],
    "roi_back": [100, 200, 50, 50]
  }
}
```

## 调试技巧

1. **单独运行任务**：
```python
if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.run()
```

2. **使用 logger**：
```python
from module.logger import logger

logger.info("信息日志")
logger.warning("警告日志")
logger.error("错误日志")
logger.exception("异常日志")  # 会打印堆栈
```

3. **保存调试图片**：
```python
from module.base.utils import save_image

save_image(self.device.image, "debug.png")
```

## 常见问题排查

### 1. Multiple devices found（检测到多个设备）

**错误信息**：
```
Multiple devices found, auto device detection cannot decide which to choose
```

**解决方法**：
修改 `config/<config_name>.json` 中的 `script.device.serial`：
```json
"script": {
  "device": {
    "serial": "127.0.0.1:16384"
  }
}
```

**MuMu 模拟器常见地址**：
- `127.0.0.1:16384` - MuMuPlayer-12.0-0
- `127.0.0.1:16448` - MuMuPlayer-12.0-2
- `127.0.0.1:7555` - 旧版 MuMu

### 2. Unknown ui page / Game page unknown（未知页面）

**错误信息**：
```
Unknown ui page
Please switch to a supported page before starting oas
```

**解决方法**：
1. 确保游戏已经完全启动并显示主界面（庭院）
2. 确保游戏在模拟器前台运行，不要最小化
3. 检查分辨率是否为 1280x720

### 3. ScrcpyError: Aborted（截图方式失败）

**错误信息**：
```
ScrcpyError: Aborted
Retry screenshot_scrcpy() failed
```

**解决方法**：
修改 `config/<config_name>.json` 中的截图方式：
```json
"script": {
  "device": {
    "screenshot_method": "ADB"
  }
}
```

**可用的截图方法**（注意大小写）：
- `auto` - 自动选择
- `ADB` - ADB 截图（最稳定，推荐）
- `ADB_nc` - ADB nc 截图
- `uiautomator2` - uiautomator2 截图
- `DroidCast` - DroidCast 截图
- `DroidCast_raw` - DroidCast raw 截图
- `scrcpy` - scrcpy 截图
- `window_background` - 窗口后台截图
- `nemu_ipc` - 网易 MuMu IPC 截图（仅 MuMu 模拟器）

### 4. 黑屏截图问题

**现象**：错误日志中的截图显示全黑

**解决方法**：
1. 确保游戏没有完全加载，等待进入主界面
2. 切换截图方式为 `ADB`
3. 检查模拟器渲染模式（DirectX/OpenGL 切换）
4. 确保模拟器窗口没有被最小化

### 5. pydantic ValidationError（配置值错误）

**错误信息**：
```
ValidationError: Input should be 'auto', 'ADB', 'ADB_nc', ...
```

**解决方法**：
确保配置值的大小写正确，例如：
- ❌ `"adb"` - 错误
- ✅ `"ADB"` - 正确

## 配置检查清单

启动 OAS 前，请检查：

1. **模拟器已启动**且游戏已加载到主界面
2. **分辨率**设置为 1280x720
3. **serial** 配置正确（如果多设备）
4. **screenshot_method** 设置正确（推荐使用 `ADB`）
5. 游戏窗口**没有被最小化**

## 注意事项

1. **interval 参数**：防止过于频繁的操作，建议设置 1-3 秒
2. **threshold 参数**：图像匹配阈值，默认 0.8，可适当调整
3. **TaskEnd 异常**：任务正常结束时抛出，被上层捕获
4. **配置继承**：新任务配置需要继承 `ConfigBase`
5. **资源命名**：使用大驼峰命名，如 `I_BUTTON`, `C_CLICK`
6. **配置值大小写**：枚举类型的配置值必须严格匹配大小写

## 参考文档

- [OAS 官方文档](https://runhey.github.io/OnmyojiAutoScript-website/)
- [开发文档 - Preamble](https://runhey.github.io/OnmyojiAutoScript-website/docs/development/preamble)
- [Alas 项目](https://github.com/LmeSzinc/AzurLaneAutoScript)
