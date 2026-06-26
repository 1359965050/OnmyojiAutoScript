# OASX 前端进一步封装建议书

## 背景

在完成 API 常量与端点路径的集中封装后，前端 `OASX-master/lib/` 仍存在较多可进一步模块化、组件化、抽象化的部分。本建议书基于对 `views/`、`controller/`、`service/`、`config/` 等目录的梳理，提出低风险、可逐步落地的封装方向。

## 目标

- 减少重复代码（UI 样式、布局、控制器模式、业务调用）
- 将散落在视图中的魔法数字/字符串集中到 `config/` 与 `component/`
- 提升新页面/新配置项的开发效率
- 保持现有 UI 与行为完全不变

## 现状观察

### 已完成的封装
- `api_constants.dart`：默认地址、超时、缓存、WS 参数
- `api_endpoints.dart`：所有后端端点路径
- `api_client.dart` / `websocket_service.dart`：已接入常量

### 仍存在的重复/硬编码
1. **UI 样式常量散落**：padding、borderRadius、card margin、icon size、constrained width 在多个 view 中重复。
2. **TitleBar 组件重复**：`MainTitleBar` / `LoginTitle` / `SettingTitle` / `ServerTitle` 结构几乎一致（图标 + 文字 + Flexible）。
3. **Card 容器重复**：`_WaitingWidget` / `_PendingWidget` / `_RunningWidget` / `ExpansionTileItem` 多处使用相同的 `.card(margin: EdgeInsets.fromLTRB(10, 0, 10, 10))` 和 `BorderRadius.circular(10)`。
4. **表格行重复**：`updater_view.dart` 中 `differHead` / `historyHead` / `genTableRow` 有大量重复 `.paddingAll(10)` 和文本样式。
5. **表单字段回调重复**：`args_view.dart` 中每种字段类型（string/number/integer/date_time/time_delta/time）都写几乎相同的 `timer?.cancel()` + `Timer(Duration(milliseconds: 1000), ...)` 防抖逻辑。
6. **Controller 模式重复**：多个 `GetxController` 都使用 `onInit` + storage 读取 + 数据加载，但没有统一基类或 mixin。
7. **业务校验硬编码**：`view_nav.dart` 中脚本重命名校验（`['Home', 'home']`、`name_duplicate`）直接写在 view 层。
8. **FutureBuilder 错误/加载 UI 重复**：`updater_view.dart` 的 `CircularProgressIndicator` / `Text('Error: ...')` 模式可在多处复用。

## 建议封装方向（按优先级）

### 1. UI 设计系统常量（高优先级 / 低风险）

新增 `lib/config/ui_constants.dart`，集中管理：

```dart
class UIConstants {
  UIConstants._();

  // 页面边距
  static const EdgeInsets pagePadding = EdgeInsets.fromLTRB(10, 0, 10, 10);
  static const EdgeInsets cardPadding = EdgeInsets.all(8);
  static const double cardBorderRadius = 10;

  // 常用尺寸
  static const double appBarHeight = 50;
  static const double appIconSize = 30;
  static const double titleSpacing = 8;
  static const double formFieldWidthLandscape = 200;
  static const double snackBarDurationSeconds = 1;

  // 常用约束
  static const BoxConstraints contentMaxWidth = BoxConstraints(maxWidth: 700);
}
```

**收益**：一次修改即可统一全应用边距、圆角、高度。

### 2. 通用 UI 组件（高优先级 / 中低风险）

新增 `lib/component/common/`：

| 组件 | 用途 | 替换位置 |
|------|------|----------|
| `OasCard` | 统一 card 容器（圆角、边距、背景色） | `_WaitingWidget`、`_PendingWidget`、`_RunningWidget`、`ServerView.path/deploy` |
| `OasTitleBar` | 统一标题栏（图标 + 标题 + 可选返回按钮） | `MainTitleBar` / `LoginTitle` / `SettingTitle` / `ServerTitle` |
| `OasSection` | 标题 + Divider + 子组件的垂直区块 | `overview_view.dart` 多处 |
| `AsyncView` | 统一 FutureBuilder 的 loading/error/success 状态 | `updater_view.dart` |
| `OasTableRow` / `OasTableCell` | 统一表格行/单元格样式 | `updater_view.dart` |

**收益**：减少 30% 以上的重复布局代码，提升一致性。

### 3. 表单字段防抖与校验封装（中优先级 / 低风险）

在 `lib/utils/` 或 `lib/component/form/` 中新增：

```dart
class DebouncedField {
  DebouncedField({this.delay = const Duration(milliseconds: 1000)});
  final Duration delay;
  Timer? _timer;

  void call(VoidCallback action) {
    _timer?.cancel();
    _timer = Timer(delay, action);
  }

  void dispose() => _timer?.cancel();
}
```

将 `args_view.dart` 中 `onStringChanged` / `onNumberChanged` / `onIntegerChanged` 等统一为：

```dart
timer.debounce(() => widget.setArgument(...));
```

**收益**：消除 6 处几乎相同的防抖代码，减少定时器泄漏风险。

### 4. Controller 基类 / Mixin（中优先级 / 中风险）

新增 `lib/controller/base/base_controller.dart`：

```dart
mixin LoadableController on GetxController {
  final isLoading = false.obs;
  final errorMessage = ''.obs;

  Future<void> runAsync(Future<void> Function() task) async {
    isLoading.value = true;
    errorMessage.value = '';
    try {
      await task();
    } catch (e) {
      errorMessage.value = e.toString();
    } finally {
      isLoading.value = false;
    }
  }
}
```

适用于 `ArgsController`、`UpdaterView` 的 FutureBuilder 逻辑、`ServerController` 的加载状态。

**收益**：统一加载/错误状态管理，减少 boilerplate。

### 5. 导航/对话框辅助（中优先级 / 低风险）

将 `view_nav.dart` 中的 `_showRenameDialog` / `_showDeleteDialog` / `_showContextMenu` / `tryCloseScriptWithReason` 抽成 `lib/utils/dialog_utils.dart`：

```dart
Future<bool> showConfirmDialog({required String title, required String message});
Future<String?> showRenameDialog({required String oldName, required List<String> existingNames});
void showContextMenu(BuildContext context, Offset position, List<PopupMenuEntry> items);
```

**收益**：将业务校验（Home/home 禁用、重复名检测）从 view 层移到可复用的工具/服务中。

### 6. 服务层进一步统一（低优先级 / 中风险）

- `LocaleService` / `ThemeService` 已存在，但 `LoginController` 直接操作 `GetStorage()`，可考虑通过 `SettingsService` 统一封装 storage key 读写。
- 新增 `lib/service/storage_service.dart`，将 `StorageKey` 与读写逻辑集中。

### 7. 路由常量（低优先级 / 低风险）

将 `'/'`、`'/login'`、`'/main'`、`'/settings'`、`'/server'` 集中到 `lib/config/route_names.dart`：

```dart
class RouteNames {
  RouteNames._();
  static const String login = '/login';
  static const String main = '/main';
  static const String settings = '/settings';
  static const String server = '/server';
}
```

## 推荐实施顺序

1. **第一批（低风险、高回报）**：
   - 创建 `ui_constants.dart`
   - 替换 `overview_view.dart`、`server_view.dart`、`args_view.dart` 中的硬编码 padding/radius/margin
   - 创建 `OasTitleBar` 替换 4 个 title bar

2. **第二批（结构优化）**：
   - 创建 `OasCard`、`AsyncView`、`OasSection`
   - 替换 `updater_view.dart` 表格与 `overview_view.dart` 区块

3. **第三批（行为抽象）**：
   - 创建 `DebouncedField`
   - 重构 `args_view.dart` 字段回调
   - 创建 `LoadableController` mixin 并迁移合适控制器

4. **第四批（可选）**：
   - 路由常量
   - StorageService
   - DialogUtils

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| UI 常量替换后视觉偏移 | 每次替换后运行 `flutter analyze` 并在不同平台截图对比 |
| 组件抽象后参数膨胀 | 仅封装当前已出现的模式，不预先支持未使用的功能 |
| 控制器 mixin 引入兼容问题 | 仅在新建或重构控制器时使用，不强制迁移所有旧控制器 |

## 验证方式

- 每次封装后：`flutter analyze`
- 关键 UI 变更：在不同窗口尺寸下运行应用，确认布局未变
- 行为变更（防抖、对话框）：手动测试配置保存、脚本重命名/删除

## 建议

- 保持"小步快跑"：每次只封装一类重复，避免单 PR 过大。
- 不预先设计未来用不到的抽象：当前重复出现 3 次以上的模式才考虑组件化。
- 文档同步：每新增一个 `component/` 或 `config/` 文件，在 `FINAL/TODO` 中记录用途。
