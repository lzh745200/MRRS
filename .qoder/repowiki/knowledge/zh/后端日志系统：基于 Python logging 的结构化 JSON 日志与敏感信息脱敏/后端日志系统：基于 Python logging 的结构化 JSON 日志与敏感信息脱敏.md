---
kind: logging_system
name: 后端日志系统：基于 Python logging 的结构化 JSON 日志与敏感信息脱敏
category: logging_system
scope:
    - '**'
source_files:
    - backend/app/core/logging_config.py
    - backend/app/core/logging.py
    - backend/app/main.py
    - backend/app/core/config.py
    - backend/logs/app.log
---

## 1. 使用的框架与工具

- 标准库 `logging`，未引入第三方日志框架（如 loguru、structlog）。
- 通过自定义 `Formatter`、`Filter` 和 `RotatingFileHandler` 子类扩展能力。
- 日志输出目标：控制台（stdout）+ 文件（按大小或按天轮转）。

## 2. 核心文件与职责

| 文件 | 职责 |
|---|---|
| `backend/app/core/logging_config.py` | 唯一日志实现入口：定义 `SensitiveDataFilter`、`JsonFormatter`、`ColoredFormatter`、`SafeTimedRotatingFileHandler`、`SafeRotatingFileHandler`，并提供 `configure_logging()` / `init_logging()` |
| `backend/app/core/logging.py` | 向后兼容的模块级 `logger = logging.getLogger("assistance_management")` 及 `init_logging()` 代理 |
| `backend/app/main.py` | 应用启动时调用 `init_logging()`，并通过 `logging.getLogger("assistance_management")` 统一记录业务日志 |
| `backend/app/core/config.py` | Settings 类中的 `LOG_LEVEL`、`LOG_FILE`、`LOG_FORMAT`、`LOG_ROTATION`、`LOG_MAX_SIZE_MB`、`LOG_BACKUP_COUNT` 等配置项 |
| `backend/logs/` | 运行时日志目录，包含 `app.log` 及按日期轮转的 `app.log.YYYY-MM-DD` |

## 3. 架构与约定

### 3.1 初始化流程
- 入口在 `backend/app/main.py` 模块顶层：`from app.core.logging_config import init_logging; init_logging()`。
- `init_logging()` 从 `app.core.config.settings` 读取 `LOG_LEVEL`、`LOG_FORMAT`、`LOG_FILE`、`LOG_MAX_SIZE_MB`、`LOG_BACKUP_COUNT`、`LOG_ROTATION`，再调用 `configure_logging()`。
- `configure_logging()` 会关闭并移除 root logger 上所有旧 handler（避免句柄泄漏导致 Windows WinError 32），然后重新注册 console 与 file handler。
- 若 `LOG_ROTATION` 非空（如 `"10 days"`），使用 `SafeTimedRotatingFileHandler(when="midnight")` 按天轮转；否则使用 `SafeRotatingFileHandler(maxBytes=...)` 按大小轮转。

### 3.2 结构化日志格式
- 文件输出默认使用 `JsonFormatter`，每条日志为单行 JSON，字段包括：`timestamp`（UTC ISO）、`level`、`logger`、`message`、`module`、`function`、`line`，异常时附加 `exception` 字段。
- 控制台在非 TTY 环境使用普通文本格式，在 TTY 环境使用带 ANSI 颜色的 `ColoredFormatter`。

### 3.3 敏感信息脱敏
- `SensitiveDataFilter` 作为全局 filter 挂载到所有 handler，对每条日志消息执行正则替换：
  - 身份证号（18 位，末位可为 X/x）→ `***`
  - 手机号（1[3-9] 开头 + 9 位数字）→ `***`
  - 邮箱 → `***`
  - 键值对形式的口令/令牌（`password|token|secret|api_key|csrf_secret` 等 key）→ 值替换为 `***`
- 脱敏失败不会阻断日志输出（try/except pass）。

### 3.4 日志级别策略
- root logger 级别由 `settings.LOG_LEVEL` 控制（默认 `INFO`）。
- 控制台 handler 级别：DEBUG 模式下为 DEBUG，否则 INFO。
- 文件 handler 固定为 DEBUG，以保留更详细的调试信息。
- 静默第三方噪音日志：`uvicorn.access`、`sqlalchemy.engine`、`PIL` 被强制设为 WARNING。

### 3.5 日志命名空间
- 项目统一使用 logger name `assistance_management`（`logging.getLogger("assistance_management")`），由 `app.core.logging` 暴露兼容入口。
- 业务代码中直接 `import logging; logger = logging.getLogger(__name__)` 亦可，但推荐复用该命名空间以便集中过滤。

### 3.6 Windows 健壮性
- `SafeTimedRotatingFileHandler` 与 `SafeRotatingFileHandler` 在 `doRollover` / `rotate` 中捕获 `PermissionError`（WinError 32），最多重试 5 次（间隔递增），最后一次失败则跳过轮转并继续写入原文件，避免后续日志全部丢失。

## 4. 约定与约束

- **统一入口**：`app.core.logging_config.init_logging()` 是唯一初始化点，`app.core.logging` 仅做向后兼容代理（注释明确说明 SafeLogger 已移除）。
- **配置来源**：所有日志行为由 `Settings` 中的 `LOG_*` 环境变量驱动，支持覆盖默认值。
- **脱敏强制**：敏感数据脱敏是全局且不可绕过的——每个 handler 都挂载了 `SensitiveDataFilter`，即使 SQL echo、异常栈、请求体落入日志也会被替换。
- **轮转策略**：生产环境默认启用按天轮转（`LOG_ROTATION="10 days"`），同时保留 `LOG_MAX_SIZE_MB` 与 `LOG_BACKUP_COUNT` 作为尺寸兜底。
- **第三方日志降噪**：`uvicorn.access`、`sqlalchemy.engine`、`PIL` 被显式压制到 WARNING，避免污染日志流。
- **PyInstaller 兼容**：`main.py` 在导入 FastAPI/Uvicorn 前将 `sys.stdout`/`sys.stderr` 重定向到 `os.devnull`，防止 windowed EXE 下 Uvicorn AccessFormatter 崩溃。
- **日志路径**：默认输出至 `./logs/app.log`，由 `Settings.LOG_DIR` 与 `Settings.LOG_FILE` 共同决定。