# OAS 六道之门（月之海）技能选择系统技术文档

本指南详细介绍了 OnmyojiAutoScript (OAS) 项目中，针对“六道之门”副本（特别是“月之海”关卡）中的技能选择、升级与购买机制。文档旨在帮助开发者和用户理解其底层识别策略、关卡逻辑和配置参数。

---

## 1. 技能系统背景与核心策略

在六道之门·月之海副本中，技能的组合与等级对于挂机通关的稳定性至关重要。OAS 目前采用以**柔风（柔风抱暖，编号101）**为核心的单特化构筑策略：

* **核心技能**：**柔风** (Skill 101)。脚本将极力追求将其提升至满级（5级）。
* **辅助技能**：**洞察之力** (Skill 105)。当备选列表中没有出现柔风时作为替代选项。
* **默认降级选项**：当既没有柔风也没有洞察之力，且无法刷新时，默认选择第4个格子的选项（通常为“恢复生命”，即 Select 3）。

---

## 2. 核心架构与代码实现

技能相关的主要逻辑集中于 `tasks/SixRealms/moon_sea/skills.py` 中的 `MoonSeaSkills` 类，其包含以下几个核心步骤：

### 2.1 技能位置识别与判定 (`_select_skill`)
当技能选择界面弹出时，界面上一般会有 4 个选项（从左到右依次为 `SELECT_0` 至 `SELECT_3`）。
脚本会优先通过模板匹配检测技能图标：
```python
# 核心选择逻辑简析
if button is None and self.appear(self.I_SKILL101):
    self.cnt_skill101 += 1
    logger.info(f'Skill 101 level: {self.cnt_skill101}')
    button = self.I_SKILL101
elif button is None and self.appear(self.I_SKILL105):
    logger.info(f'Skill 105 level: {self.cnt_skill101}')  # 注：此处源码中日志打印可能存在拼写/变量复用偏置
    button = self.I_SKILL105
```
定位到技能按钮后，脚本会根据按钮的横坐标（X 轴位置）来决定点击哪一个选择框（`Select 0` ~ `Select 3`）。对应的横坐标分界线为：
* $X < 360$ $\rightarrow$ **Select 0**
* $360 \le X < 640$ $\rightarrow$ **Select 1**
* $640 \le X < 960$ $\rightarrow$ **Select 2**
* 其他 $\rightarrow$ **Select 3**

### 2.2 自动刷新机制 (`select_skill`)
在每次普通战斗或精英战斗结束后，会自动触发技能选择：
1. **钱币不足判定**：通过 OCR 识别右上角金币数量 (`O_COIN_NUM`)。如果金币少于 50，则认为没有足够的钱进行技能刷新。
2. **刷新次数判定**：通过 OCR 识别刷新文本 (`O_SKILL_REFRESH`)，用正则匹配获取 `"剩\d+次"`。如果剩余次数 $\le 0$，则停止刷新。
3. **刷新触发条件**：如果开启了 `refresh` 开关，但当前界面**没有出现柔风**，且金币足够、仍有刷新次数、柔风未满 5 级，脚本将自动点击刷新按钮 (`I_SKILL_REFRESH`) 并等待界面动画稳定。

---

## 3. 各岛屿（关卡）技能专属处理

月之海中的不同岛屿类型在脚本中有着高度模块化的独立处理类：

| 岛屿编号 | 岛屿名称 | OAS 处理类 | 核心技能逻辑 |
| :--- | :--- | :--- | :--- |
| **island101** | 宁息 (Store) | `MoonSeaL101` | **技能商店购物**：只要金币 $\ge 300$ 且柔风未满级，就会不断寻找并购买 `I_STORE_SKILL_101`。如果金币 $\ge 400$ 且无柔风，则自动刷新商店。 |
| **island102** | 神秘 (Mystery) | `MoonSeaL102` | **技能仿造**：如果在该关卡触发了“仿造 (Imitate)”，脚本会自动选定并仿造柔风 (`I_IMITATE_1`)，直接为柔风等级加一。如果是转赠技能，则不作处理直接退出。 |
| **island103** | 混沌 (Chaos) | `MoonSeaL103` | 精英战斗结束后，触发带刷新的技能选择逻辑 `self.select_skill(refresh=True)`。 |
| **island104** | 鏖战 (Battle) | `MoonSeaL104` | 战斗结束后，触发带刷新的技能选择逻辑 `self.select_skill(refresh=True)`。 |
| **island105** | 星之屿 (Star) | `MoonSeaL105` | 极高难度的普通怪，战斗后仅获取金币和结算奖励，不涉及任何技能选择判定。 |

---

## 4. 资源配置与定位 (Assets)

在 `tasks/SixRealms/assets.py` 中预定义了所有用于识别的模板匹配图像与 OCR 区域：

* **图像匹配 (Template Matching)**:
  * `I_SKILL101`: 柔风技能图标模板。
  * `I_SKILL105`: 洞察之力技能图标模板。
  * `I_SKILL_REFRESH`: 技能选择界面右下角的刷新按钮。
  * `I_STORE_SKILL_101`: 商店中柔风的技能卡片模板（用于点击购买）。
  * `I_IMITATE_1`: 仿造界面中柔风的图标。
* **文字识别 (OCR)**:
  * `O_COIN_NUM`: 界面右上角金币数的数字 OCR 区域。
  * `O_SKILL_REFRESH`: 刷新按钮附近的文本 OCR。
  * `O_STORE_REFRESH_TIME`: 商店中刷新剩余次数的文字 OCR。

---

## 5. 开发者建议与已知问题说明

> [!TIP]
> **关于 `cnt_skill101` 日志的提示：**
> 在 `skills.py` 中的 `_select_skill` 方法内，当匹配到洞察之力 (Skill 105) 时，日志输出会显示：
> `logger.info(f'Skill 105 level: {self.cnt_skill101}')`
> 这里的变量使用了追踪柔风等级的 `self.cnt_skill101`，而非 105 的独立计数。若后续需要实现多技能构筑特化（如特化细雨、暴虐等），建议将 `cnt_skill` 统一重构为字典映射结构（例如 `self.skills_level: dict[str, int]`）。
