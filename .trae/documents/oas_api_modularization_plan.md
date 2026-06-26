# OAS API 模块化与固定参数封装计划

## 背景与目标

当前 OAS 后端 API（FastAPI）与前端的 HTTP/WebSocket 通信中存在大量硬编码参数：默认地址 `127.0.0.1:7788`、超时时间、CORS 配置、端点路径、WebSocket 命令字、日志阈值等。这些参数散落在 `app.py`、三个 router、`api_client.dart`、`websocket_service.dart` 等文件中，后续修改容易遗漏、新增接口时前后端也缺乏统一的端点定义参考。

本次重构的目标：**仅搬运常量、不改动业务逻辑和接口契约**，将前后端 API 相关的固定参数集中到独立的常量模块，提升可维护性并保持完全兼容。

## 范围边界

**会重构（仅常量提取）**
- 所有硬编码的字符串/数字常量提取到命名常量。
- 路由路径从字面量改为引用常量，参数化路径保持原有参数名不变。
- WebSocket 命令字、日期格式、日志级别集合等 API 契约常量化。

**不会改动（保持兼容）**
- 任何端点的实际 URL 路径。
- 请求/响应数据结构（Pydantic model、query/body 参数名）。
- 业务处理逻辑（`MainManager`、`ConfigManager`、annotator 等）。
- 鉴权/密码、CORS 最终生效值、默认端口号。
- HTTP 框架与 Dio 封装方式。

## 后端变更

### 新增文件

1. **`module/server/constants.py`**
   - FastAPI 应用元信息：`APP_TITLE`、`APP_DESCRIPTION`、`APP_VERSION`
   - CORS 配置：`CORS_ALLOW_ORIGINS`、`CORS_ALLOW_CREDENTIALS`、`CORS_ALLOW_METHODS`、`CORS_ALLOW_HEADERS`
   - 静态资源挂载路径：`ANNOTATOR_STATIC_PATH`
   - Router 前缀与 tags：`HOME_ROUTER_PREFIX/_TAGS`、`TOOL_ROUTER_PREFIX/_TAGS`
   - 通用 HTTP 状态码：`HTTP_400_BAD_REQUEST`、`HTTP_404_NOT_FOUND`、`HTTP_500_INTERNAL_SERVER_ERROR`
   - API 日志目录与阈值：`API_LOG_DIR`、`MAX_API_LOG_FILES`、`MAX_API_LOG_SIZE`

2. **`module/server/endpoints.py`**
   - `HomeEndpoints`：/test、/home_menu、/kill_server、/update_info、/execute_update、/chinese_translate、/additional_translate
   - `ScriptEndpoints`：/test、/script_menu、/config_list、/config_copy、/config_new_name、/config_all、/config、/config/task/copy、/config/task/group/copy，以及参数化端点 `/{script_name}/start`、`/{script_name}/stop`、`/{script_name}/logger/level`、`/{script_name}/{task}/args`、`/{script_name}/{task}/{group}/{argument}/value`、`/{script_name}/{task}/sync_next_run`、WebSocket `/ws/{script_name}`
   - `ScriptWsCommands`：get_state、get_schedule、start、stop
   - `ScriptValidation.VALID_LOG_LEVELS`
   - `DateTimeFormats.DATETIME`、`DateTimeFormats.TIME`
   - `ToolEndpoints`：所有 `/tool/annotator/...` 端点

### 修改文件

- **`module/server/app.py`**：使用 `constants.py` 中的应用元信息、CORS、静态路径、状态码。
- **`module/server/api_logger.py`**：从 `constants.py` 导入日志目录与阈值。
- **`module/server/home_router.py`**：使用 `HomeEndpoints` 和 router 前缀常量。
- **`module/server/script_router.py`**：使用 `ScriptEndpoints`、`ScriptWsCommands`、`ScriptValidation`、`DateTimeFormats` 和 HTTP 状态码常量。
- **`module/server/tool_router.py`**：使用 `ToolEndpoints` 和错误码/关闭原因常量。

## 前端变更

### 新增文件

1. **`OASX-master/lib/config/api_constants.dart`**
   - `ApiConstants.defaultAddress = '127.0.0.1:7788'`
   - `ApiConstants.httpScheme`、`ApiConstants.wsScheme`
   - Dio 连接超时 `connectTimeout`、缓存 `maxStale`、`allowPostMethod`
   - 拦截器最大打印长度 `interceptorMaxLen`
   - WebSocket 重连次数、重连间隔、默认超时

2. **`OASX-master/lib/api/api_endpoints.dart`**
   - `HomeEndpoints`：所有 `/home/...` 端点
   - `ScriptEndpoints`：所有脚本端点，含参数化构造方法
   - `ToolEndpoints`：所有 `/tool/annotator/...` 端点

### 修改文件

- **`OASX-master/lib/api/api_client.dart`**：引入 `api_constants.dart` 和 `api_endpoints.dart`，替换硬编码地址、超时、缓存策略和所有端点路径字符串。
- **`OASX-master/lib/service/websocket_service.dart`**：引入 `api_constants.dart`，替换默认 WS URL 模板、重连次数、重连间隔、默认超时。
- **`OASX-master/lib/api/api_interceptor.dart`**（可选但建议）：使用 `ApiConstants.interceptorMaxLen` 替换 `_maxLen`。

## 迁移步骤（按依赖顺序）

1. **创建后端常量文件**
   - 新建 `module/server/constants.py`
   - 新建 `module/server/endpoints.py`（纯常量，零业务依赖）

2. **后端入口与日志**
   - 修改 `app.py` 引用 `constants.py`
   - 修改 `api_logger.py` 引用 `constants.py`

3. **后端三个 router**
   - 按 `home_router.py` → `script_router.py` → `tool_router.py` 顺序替换为常量
   - 每改完一个 router 执行 `python -m py_compile`

4. **创建前端常量文件**
   - 新建 `OASX-master/lib/config/api_constants.dart`
   - 新建 `OASX-master/lib/api/api_endpoints.dart`

5. **前端核心替换**
   - 修改 `api_client.dart`
   - 修改 `websocket_service.dart`
   - 可选修改 `api_interceptor.dart`

6. **静态检查**
   - 后端：`python -m py_compile module/server/*.py`
   - 前端：`cd OASX-master && flutter analyze`

7. **运行时冒烟测试**
   - 启动后端服务
   - curl 验证：`/test`、`/home/test`、`/home/home_menu`、`/script_menu`、`/config_list`、`/tool/annotator/api/configs`
   - 启动 OASX，验证登录、菜单、配置列表、脚本 WebSocket 状态同步

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 端点字符串提取时拼写错误 | 404 | 使用查找替换；改完后对每个 router 跑 curl 验证 |
| 参数化路径变量名被改 | FastAPI 参数绑定失败 | 保持 `{script_name}`、`{task}` 等变量名与源码完全一致 |
| 常量模块循环导入 | 启动失败 | `constants.py` 与 `endpoints.py` 只放纯常量，不导入 router 或业务模块 |
| 前端地址 scheme 处理差异 | WS 连接失败 | 保留现有 `http://` 剥离逻辑，仅把默认模板和参数常量化 |
| 日期/日志级别常量改错 | 业务解析异常 | 保持原值不变，通过单元测试/常量断言验证 |

## 验证方式

### 静态验证

```bash
# 后端
python -m py_compile module/server/app.py module/server/api_logger.py module/server/home_router.py module/server/script_router.py module/server/tool_router.py module/server/constants.py module/server/endpoints.py

# 前端
cd OASX-master
flutter analyze
```

### 运行时冒烟

```bash
curl http://127.0.0.1:7788/test
curl http://127.0.0.1:7788/home/test
curl http://127.0.0.1:7788/home/home_menu
curl http://127.0.0.1:7788/script_menu
curl http://127.0.0.1:7788/config_list
curl http://127.0.0.1:7788/tool/annotator/api/configs
```

前端：启动 OASX，测试地址连接、菜单渲染、配置列表、脚本状态同步、`/home/kill_server`。

## 建议

- 分两次提交：第一次后端常量，第二次前端常量，降低 review 与回滚成本。
- 常量命名风格与现有代码保持一致：Python 使用大写下划线，Dart 使用大写驼峰/驼峰。
- 如发现常量值前后端不一致（如端口号、路径参数名），本次任务中只记录，不擅自修改数值。
