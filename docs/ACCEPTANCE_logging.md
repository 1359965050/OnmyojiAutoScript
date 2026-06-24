# 日志机制改造验收报告

## 验收范围
- 结构化日志模型与 JSON 序列化
- 子进程 → 主进程日志 IPC（Pipe 替换为 Queue）
- 热切换日志级别 API 与控制循环
- 前端日志面板解析 JSON 与级别过滤
- 导航修复与菜单重命名残留清理

## 验证结果

### 1. 后端结构化日志
- **验证文件**: `module/server/log_record.py`
- **验证命令**: `python tmp_verify_logging.py`
- **结果**: `LogRecord` 可正确从 `logging.LogRecord` 构造并序列化为 JSON；
  `set_structured_func_logger` 输出的 JSON 包含 `timestamp/level/script/module/message/formatted/context` 字段。

### 2. IPC 稳定性与级别热切换
- **验证文件**: `module/server/script_process.py`
- **验证命令**: `python tmp_verify_ipc.py`
- **结果**:
  - `multiprocessing.Queue` 在 Windows spawn 模式下可稳定传输 JSON 日志；
  - 子进程 `control_loop` 可接收 `set_log_level` 命令；
  - 切换到 `WARNING` 后，后续 `DEBUG/INFO` 日志被过滤，`WARNING/ERROR` 正常输出。

### 3. 前端代码静态检查
- **验证命令**: `flutter analyze --no-fatal-infos --no-fatal-warnings`
- **结果**: 修改相关文件无新增 error；剩余 11 条 warning/info 均为既有旧代码问题。

### 4. 前端日志面板
- **验证文件**:
  - `OASX-master/lib/component/log/log_mixin.dart`
  - `OASX-master/lib/component/log/log_widget.dart`
- **结果**:
  - `LogMixin.addLog` 可解析 JSON 结构化日志并回退到纯文本；
  - `setLogLevelFilter` 可重新应用过滤；
  - `OverviewController.setLogLevelFilter` 调用后端接口同步级别。

### 5. 菜单重命名与导航
- **验证文件**:
  - `module/config/config_menu.py`（后端菜单：GlobalSettings/EmulatorSettings/GameSettings）
  - `OASX-master/lib/controller/ctrl_nav.dart`（useablemenus 只收集叶子节点）
  - `OASX-master/lib/config/translation/i18n_cn.dart` / `i18n_us.dart`
- **结果**:
  - 目录名点击不再跳转；
  - 已移除旧的 `I18n.script` 与 `I18n.global_game` 翻译和常量定义。

## 遗留 TODO
- 当前 `state_queue` 同时承载子进程→主进程状态上报和主进程→子进程控制命令，
  在 `coroutine_broadcast_state` 中会对控制命令执行一次无意义广播。若后续需要更严格的命令隔离，
  可引入独立的 `command_queue`。
- 后端 `module/config/i18n/zh_CN.xml` 中仍保留 `ScriptConfig` / `GlobalGame` 等旧 source，
  这些用于配置表单字段翻译，未影响菜单显示，本次未做改动。

## 结论
P1 日志机制改造通过验收，可继续交付或进入下一轮迭代。
