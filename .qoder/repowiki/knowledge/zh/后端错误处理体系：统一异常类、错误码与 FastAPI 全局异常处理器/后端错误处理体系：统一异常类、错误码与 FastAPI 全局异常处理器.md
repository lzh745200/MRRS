---
kind: error_handling
name: 后端错误处理体系：统一异常类、错误码与 FastAPI 全局异常处理器
category: error_handling
scope:
    - '**'
source_files:
    - backend/app/core/exceptions.py
    - backend/app/core/errors.py
    - backend/app/core/error_handler.py
    - backend/app/core/response.py
    - backend/app/main.py
---

## 1. 采用的系统/方案

后端基于 **FastAPI** 的异常处理机制，构建了一套三层错误处理体系：

- **领域异常类**（`app/core/exceptions.py`）：以 `AppError` 为基类，派生出 `BusinessError`、`ValidationError`、`NotFoundError`、`ConflictError`、`DatabaseError`、`InvalidCredentialsError`、`UserAlreadyExistsError` 等语义化异常。
- **统一错误码**（`app/core/errors.py`）：通过 `IntEnum ErrorCode` 集中管理所有业务/系统错误码（0~9002），并配套中文消息字典 `ERROR_MESSAGES` 与 `get_error_message()` 工具。
- **FastAPI 全局异常处理器**（`register_exception_handlers`，在 `backend/app/main.py` 启动时调用）：将 `AppError`、Pydantic `ValidationError`、以及未捕获的 `Exception` 分别映射到统一的 JSON 响应格式 `{code, message, success, [details]}`。

此外，`app/core/error_handler.py` 提供辅助函数 `error_response()` / `not_found_response()` / `forbidden_response()` / `server_error_response()`；`app/core/response.py` 提供成功响应构造器 `success_response()` / `ok_list()` / `paginated_response()`，形成“成功/失败”两套对称的统一响应体。

## 2. 关键文件与包

| 文件 | 职责 |
|---|---|
| `backend/app/core/exceptions.py` | 定义 `AppError` 及其子类、`register_exception_handlers` 注册三个 FastAPI 异常处理器 |
| `backend/app/core/errors.py` | `ErrorCode` 枚举、`ERROR_MESSAGES` 中文消息表、`get_error_message()`、并通过 PEP 562 `__getattr__` 懒加载 `AppError`/`ValidationError` 避免循环导入 |
| `backend/app/core/error_handler.py` | 历史遗留的错误响应构造器与兼容别名（`BusinessLogicError`） |
| `backend/app/core/response.py` | 统一成功/失败响应构造器（`success_response`、`error_response`、`ok_list`、`paginated_response`） |
| `backend/app/main.py` | 应用入口，调用 `register_exception_handlers(app)` 注册全局处理器，并挂载中间件链 |
| `backend/app/api/v1/*.py` | 业务路由，使用 `HTTPException`、`success_response`、`ok_list` 等返回结果 |

## 3. 架构与约定

### 3.1 异常层次
```
AppError (message, status_code, code, details)
├── BusinessError (默认 code=ErrorCode.BUSINESS_ERROR)
│   ├── InvalidCredentialsError (401)
│   └── UserAlreadyExistsError (409)
├── ValidationError (field → details.field)
├── NotFoundError (resource + identifier)
├── ConflictError (409)
└── DatabaseError (500)
```
每个异常都携带 `status_code`、`code`、`details`，并通过 `to_dict()` 输出 `{error: {code, message, details}}`。

### 3.2 全局异常处理器策略
- `AppError` → 直接按 `exc.status_code` 返回 `{code, message, success: False}`。
- Pydantic `ValidationError` → 422，附带 `errors: exc.errors()`。
- 未捕获 `Exception` → 500，记录 `logger.error(..., exc_info=True)`，对外仅返回通用“服务器内部错误”。

### 3.3 错误码分层
`ErrorCode` 按领域分组：通用(0/200/4xx/500)、认证(1001–1008)、权限(2001–2002)、资源(3001–3005)、文件(4001–4004)、数据库(5001–5003)、限流(6001)、外部服务(7001)、配置(8001)、业务(9001–9002)。同时保留 `_XXX_LEGACY` 与 `USER_NOT_FOUND`、`DATABASE_ERROR` 等向后兼容别名，确保旧消费者不受影响。

### 3.4 响应体约定
- 成功：`{code: 200, message, success: True, data: ...}`，列表用 `ok_list()` 包装为 `{items, total, page, page_size}`。
- 失败：`{code: <http_status>, message, success: False, [details/errors/detail]}`。

### 3.5 模块间依赖与循环保护
`errors.py` 通过 PEP 562 `__getattr__` 延迟从 `exceptions.py` 导入 `AppError`/`ValidationError`，因为 `exceptions.py` 顶层会 `from app.core.errors import ErrorCode`，直接相互 import 会导致后端启动崩溃。这是代码中显式注释说明的设计约束。

### 3.6 生产环境健壮性
- 迁移失败：`_run_alembic_upgrade` 在生产环境抛异常中止启动（fail-loud），开发/测试环境降级为自动补列兜底。
- 启动期初始化（审计事件钩子、备份调度、WAL checkpoint 等）全部用 `try/except` 包裹，失败仅 `logger.warning`，不阻断主进程。

## 4. 约定与约束

- **业务层应抛出领域异常而非裸 `raise Exception`**：`AppError` 及其子类是业务错误的唯一出口，保证 `code`、`message`、`details` 三件套一致。
- **前端只认统一响应体**：`response.py` 的 `success_response`/`error_response` 是 API 响应的唯一构造方式，禁止手写 JSON 绕过。
- **错误码必须来自 `ErrorCode`**：新增错误需先在 `errors.py` 的 `ErrorCode` 和 `ERROR_MESSAGES` 中登记，再在业务处引用，避免硬编码数字。
- **全局异常处理器不可被业务覆盖**：`main.py` 在路由注册前调用 `register_exception_handlers(app)`，任何重复注册的处理器会被覆盖。
- **Pydantic 验证错误统一走 422**：自定义 `_ValidationError` 重导出为 `ValidationError`，使业务可直接 `raise ValidationError(field="x")`。
- **向后兼容优先**：`errors.py` 中的 `_XXX_LEGACY` 与 `USER_NOT_FOUND` 等别名表明，修改错误码时必须保留旧值映射，不得破坏已有消费者。
- **日志与对外信息分离**：未捕获异常记录完整堆栈（`exc_info=True`），但对外仅返回通用 500 消息，防止泄露内部细节。

## 5. 前端侧配合

前端通过 `src/utils/request.ts`（或等效 axios 拦截器）解析统一响应体：`success === true` 取 `data`，否则读取 `code/message` 展示给用户。`response.py` 中 `ok_list` 的注释明确说明“前端 `_unwrapList` 据此取 `data.items` / `data.total`”，体现了前后端对错误/成功格式的契约约束。

## 6. 适用范围

该体系覆盖后端 FastAPI 服务的所有 HTTP 请求路径；Electron 主进程通过 HTTP 调用后端，复用同一套错误协议；前端 Vue3 应用根据统一响应体进行错误提示。当前仓库未发现独立的“前端错误类型定义”文件，前端主要依赖运行时解析后端返回的 `code/message`。