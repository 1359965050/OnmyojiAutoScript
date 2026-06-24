# OAS 日志机制完善建议书

## 1. 现状梳理

### 1.1 现有日志链路

```
脚本子进程
    │
    ├─► 控制台 (RichHandler → Console)
    ├─► 文件日志 (RichFileHandler → ./log/YYYY-MM-DD_<name>.txt)
    └─► Flutter/WebSocket 前端 (FlutterHandler → FlutterLogStream → log_pipe_in.send)
                                    │
主进程 log_pipe_out.recv() ◄────────┘
    │
    └─► WebSocket broadcast_log() → 前端 OASX

FastAPI 服务端
    │
    └─► ApiLoggingMiddleware → ApiLogger → ./log/api/YYYY-MM-DD_api.txt
```

### 1.2 关键源码位置

| 组件 | 文件 | 说明 |
|------|------|------|
| 核心 logger | `module/logger.py` | 配置 Rich 控制台/文件/Flutter 三端 Handler |
| 脚本子进程 | `module/server/script_process.py` | `multiprocessing.Pipe` + `state_queue` 双 IPC |
| 日志广播 | `module/server/script_websocket.py` | WebSocket 广播 state/log |
| 调度管理 | `module/server/main_manager.py` | 负责拉起/监控 state、log 协程 |
| API 日志 | `module/server/api_logger.py` | FastAPI 中间件，记录请求/响应 |
| 服务入口 | `module/server/app.py` | 注册 `ApiLoggingMiddleware` |

---

## 2. 当前痛点与风险

### 2.1 子进程日志 IPC 偶发崩溃（已触发）

**问题**：脚本子进程通过 `log_pipe_in.send()` 把日志打回主进程，主进程 `log_pipe_out.recv()` 读取后 WebSocket 广播。Windows + Python 3.12 + ProactorEventLoop 下，高并发写管道时偶发：

```
AssertionError in _ProactorBaseWritePipeTransport._loop_writing
```

**影响**：日志流中断，严重时脚本异常退出，前端日志面板空白或断连。

**根因**：
- `FlutterLogStream.write()` 同步调用 `log_pipe_in.send()`；Rich Console 在格式化复杂 traceback 时可能连续写多次。
- 管道写端处于 asyncio 事件循环中，`send()` 与事件循环回调存在竞态。
- 管道关闭（脚本退出/重启）时没有优雅排空残留日志。

### 2.2 日志级别与格式不统一

| 位置 | 格式 | 级别控制 |
|------|------|----------|
| 控制台 | `HH:MM:SS │ message` | 硬编码 INFO |
| 文件 | `YYYY-MM-DD HH:MM:SS.mmm │ filename:line │ LEVEL │ message` | 同上 |
| WebSocket 前端 | `| HH:MM:SS │ message` | 不可配置 |
| API 日志 | JSON Lines | 无按接口过滤 |

问题：
- 没有统一结构化日志（JSON/字段）。
- 前端无法按脚本/级别/模块过滤。
- `logger_debug` 硬编码，无法热切换。

### 2.3 日志文件管理粗放

- `cleanup_logs()` 只清理 7 天前文件，但单文件无大小上限，长时间运行可能膨胀。
- API 日志已有轮转，但普通脚本日志没有轮转。
- 异常/崩溃时的最后日志没有单独落盘，排查困难。

### 2.4 状态与日志协程生命周期脆弱

- `coroutine_broadcast_log()` 用 `while 1` + `sleep` 轮询管道，CPU 空转且延迟不稳定（50ms ~ 300ms）。
- 协程异常仅打印 `Log Error: {e}`，没有指数退避，异常风暴时会刷屏。
- 脚本重启/停止时，`log_pipe_in.close()` 可能把未发送的日志丢弃。

### 2.5 API 日志缺少敏感信息保护

- `ApiLoggingMiddleware` 记录请求体/响应体，可能包含用户配置、截图数据、token 等敏感信息。
- 无采样、无脱敏、无 skip 路径配置。

### 2.6 日志与业务 Metrics 未分离

- 当前日志既承载“人可读的运行日志”，又承载“前后端通信的调试信息”，还承载“API 审计日志”。
- 混在一起导致检索困难和存储浪费。

---

## 3. 改进目标

1. **稳定**：消除 Windows 下管道写断言崩溃，保证脚本退出时日志不丢。
2. **可观测**：统一结构化日志，支持按脚本/级别/模块过滤与检索。
3. **可控**：日志级别可在线切换，文件大小可轮转，历史可自动清理。
4. **安全**：API 日志脱敏，避免敏感配置/截图/凭证泄露。
5. **低耦合**：日志通道与业务执行通道分离，互不影响。

---

## 4. 架构设计方案

### 4.1 总体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          脚本子进程 (ScriptProcess)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   业务代码    │  │  文件 Handler │  │   QueueLogHandler        │  │
│  │   logger.xxx │  │  (本地落盘)   │  │   (发往 Queue)            │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
│         │                  │                        │                │
│         └──────────────────┴────────────────────────┘                │
│                            │                                         │
│                     本地日志队列 (deque / queue.Queue)                 │
│                            │                                         │
└────────────────────────────┼─────────────────────────────────────────┘
                             │  send_bytes / pickle
┌────────────────────────────┼─────────────────────────────────────────┐
│                       主进程  │                                        │
│  ┌─────────────────────────▼────────────┐                            │
│  │      LogCollector 协程                │                            │
│  │  从 Pipe/Queue 读取 → 解包 → 分发       │                            │
│  └────────────────┬─────────────────────┘                            │
│                   │                                                   │
│     ┌─────────────┼─────────────┬──────────────┐                      │
│     ▼             ▼             ▼              ▼                      │
│  WebSocket    API 审计     指标/告警      持久化文件                   │
│  前端实时      (可选)      (可选)        (可选)                        │
└───────────────────────────────────────────────────────────────────────┘
```

### 4.2 关键改造点

#### 4.2.1 用 `multiprocessing.Queue` 替换 Pipe（推荐优先做）

**方案**：把 `log_pipe_in.send()` 改为写入 `multiprocessing.Queue`。

**原因**：
- `Queue` 内部已做锁和缓冲区管理，对 Windows 更友好。
- 支持批量 `get_many`（可用 `get_nowait()` 循环取），减少协程空转。
- 退出时可批量排空残留日志。

**实现示意**：

```python
# script_process.py
self.log_queue: multiprocessing.Queue = multiprocessing.Queue()

# func() 子进程入口
from module.logger import set_func_logger
def queue_send(msg: str):
    try:
        log_queue.put(msg, timeout=0.5)
    except Exception:
        pass  # 避免日志反压导致业务阻塞
set_func_logger(queue_send)

# 主进程收集协程
async def coroutine_collect_log(self):
    while 1:
        if self.state == ScriptState.INACTIVE:
            await sleep(1)
            continue
        try:
            batch = []
            while len(batch) < 50:
                try:
                    batch.append(self.log_queue.get_nowait())
                except QueueEmpty:
                    break
            if batch:
                await self.broadcast_log("".join(batch))
            else:
                await sleep(0.05)
        except Exception as e:
            logger.error(f'Log queue error: {e}')
            await sleep(0.5)
```

#### 4.2.2 增加优雅退出与残留日志排空

```python
def signal_handler(signum, frame):
    logger.info(f'Script {config} received signal {signum}')
    # 先关闭文件 handler，确保文件落盘
    for h in list(logging.root.handlers):
        h.flush()
    # 排空日志队列（Queue 不会阻塞在 close）
    log_queue.close()
    # 等待一小段时间让主进程把队列取完
    time.sleep(0.2)
    state_queue.close()
    sys.exit(0)
```

#### 4.2.3 结构化日志 + 可配置级别

**统一日志记录模型**：

```python
class LogRecord:
    timestamp: str
    level: str          # DEBUG/INFO/WARNING/ERROR/CRITICAL
    script: str         # oas1 / oas2
    module: str         # tasks.Exploration.solo
    message: str
    context: dict       # 可选上下文
```

**改造 `set_func_logger`**：

- 子进程发送 JSON 序列化后的 `LogRecord`，而非纯文本。
- 前端按 `level` 着色，按 `module` 折叠，按关键字过滤。

**动态级别切换**：

```python
# 新增 API /logger/level
@router.post("/logger/level")
def set_level(script: str, level: str):
    # 通过 state_queue 通知子进程更新 logger.level
```

#### 4.2.4 文件日志轮转

为普通脚本日志增加 `RotatingFileHandler` 或按大小分割：

```python
class SizedRichFileHandler(RichFileHandler):
    def __init__(self, *args, max_bytes=10*1024*1024, backup_count=3, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.base_path = Path(self.console.file.name)

    def emit(self, record):
        if self.base_path.exists() and self.base_path.stat().st_size > self.max_bytes:
            self._rotate()
        super().emit(record)

    def _rotate(self):
        for i in range(self.backup_count - 1, 0, -1):
            src = self.base_path.with_suffix(f'.txt.{i}')
            dst = self.base_path.with_suffix(f'.txt.{i+1}')
            if src.exists():
                src.rename(dst)
        self.base_path.rename(self.base_path.with_suffix('.txt.1'))
```

#### 4.2.5 API 日志脱敏与采样

```python
SENSITIVE_PATHS = {"/login", "/config_update", "/upload_image"}
SENSITIVE_KEYS = {"password", "token", "serial", "secret"}

def _mask_body(body: str) -> str:
    try:
        data = json.loads(body)
        for key in SENSITIVE_KEYS:
            if key in data:
                data[key] = "***"
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        return "[unmaskable]"

class ApiLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        # 完全跳过静态资源/心跳/WebSocket
        if path in SKIP_PATHS or path.startswith("/ws"):
            return await call_next(request)
        # 采样：健康检查类接口只记录 1%
        ...
```

#### 4.2.6 分离 Metrics 通道

- 运行日志：仍走 WebSocket 实时推给前端。
- API 审计：独立落盘 `log/api/`，不进入前端实时流。
- 性能指标：使用 `state_queue` 发送结构化 metrics，由主进程聚合后可选推给前端或落盘。

---

## 5. 实施计划（推荐优先级）

### P0：修复 IPC 崩溃（立即）

1. 将 `log_pipe` 从 `multiprocessing.Pipe` 替换为 `multiprocessing.Queue`。
2. 优化 `coroutine_broadcast_log` 为批量读取，降低空转。
3. 增加退出信号处理，排空残留日志。

**验收**：连续运行 Exploration 1 小时不再出现 `_ProactorBaseWritePipeTransport AssertionError`。

### P1：结构化日志与可配置级别（1~2 天）

1. 定义 `LogRecord` 模型。
2. 改造 `set_func_logger` 发送 JSON。
3. 前端解析 JSON 并按级别/模块渲染。
4. 新增 `/logger/level` 接口支持热切换。

**验收**：前端可通过下拉框选择只显示 WARNING 及以上日志。

### P2：文件日志轮转与生命周期（1 天）

1. 普通脚本日志增加按大小轮转。
2. 启动/停止时打印生命周期日志。
3. 异常退出时捕获最后 N 条日志写入 `log/error/<script>/<timestamp>.txt`。

**验收**：单日志文件超过 10MB 自动切分；崩溃后有独立错误日志。

### P3：API 日志安全与采样（0.5 天）

1. 敏感路径/字段脱敏。
2. 跳过 `/ws`、`/static`、健康检查。
3. 大响应体截断。

**验收**：API 日志中不出现密码、token、完整截图 base64。

### P4：Metrics 通道分离（可选，2~3 天）

1. `state_queue` 统一发送结构化事件。
2. 主进程聚合 FPS、任务耗时、异常计数等。
3. 前端新增“运行指标”面板。

---

## 6. 风险与回退

| 风险 | 影响 | 回退方案 |
|------|------|----------|
| Queue 替换后前端日志延迟增加 | 用户体验 | 调整批量大小与 sleep 间隔 |
| JSON 日志破坏旧前端解析 | 前端空白 | 保留纯文本兼容模式 |
| 日志级别动态切换引发性能波动 | 脚本卡顿 | 限制切换频率，按模块分级 |
| 文件轮转时句柄切换丢日志 | 数据丢失 | 加锁或先 flush 再 rotate |

---

## 7. 预期收益

- **稳定性**：消除当前已触发的 Windows 管道断言崩溃。
- **可维护性**：统一日志格式，排查问题时可按脚本/模块/级别快速定位。
- **安全性**：API 审计日志不再泄露敏感信息。
- **可扩展性**：为后续“运行指标”“告警通知”打下数据通道基础。
