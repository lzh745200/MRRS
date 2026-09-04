---
kind: configuration_system
name: 配置系统 — 基于 pydantic-settings 的环境变量 + 运行时密钥持久化 + 路径抽象
category: configuration_system
scope:
    - '**'
source_files:
    - backend/app/core/config.py
    - backend/app/utils/runtime_secrets.py
    - backend/app/utils/paths.py
    - backend/start.py
    - backend/.env.example
    - frontend/.env.example
    - frontend/vite.config.ts
    - backend/secrets/master.key
---

## 1. 总体方案

本仓库采用 **环境变量驱动 + Pydantic Settings 类型化加载 + 运行时密钥自动持久化** 的三层配置体系：

- 后端（FastAPI）：`backend/app/core/config.py` 中的 `Settings(BaseSettings)` 是单一事实源，通过 `pydantic_settings.SettingsConfigDict` 声明 `.env` 文件搜索顺序（`backend/.env` → `.env` → `../.env`），所有业务配置以强类型字段定义并带默认值。
- 前端（Vue3/Vite）：通过 `frontend/.env*` 注入 `VITE_*` 前缀的环境变量，由 Vite 在构建期注入到 `import.meta.env`，用于控制 API 地址、应用模式、功能开关等。
- Electron/桌面壳：启动时通过 `start.py` 设置工作目录、检查端口、创建目录，再调用 `app.main:app` 启动 Uvicorn；打包后通过 `FRONTEND_DIST_PATH`、`DATABASE_URL` 等环境变量注入运行期参数。

## 2. 关键文件与职责

| 文件 | 职责 |
|---|---|
| `backend/app/core/config.py` | 定义 `Settings` 模型，集中声明全部可配置项（数据库、CORS、CSRF、日志、上传、加密、监控、告警等），并在 `model_post_init` 中执行生产环境安全加固、相对路径→绝对路径转换、动态数据目录解析 |
| `backend/app/utils/runtime_secrets.py` | 运行时密钥管理：从环境变量或 `runtime_secrets.json` 读取/生成 `SECRET_KEY`、`CSRF_SECRET_KEY`、`ENCRYPTION_FERNET_KEY` 等，原子写入并限制 Unix 权限为 `0o600` |
| `backend/app/utils/paths.py` | 平台无关的路径抽象：根据是否打包（`sys.frozen`）、Linux/Windows、开发标志（`BUMOFU_DEV_MODE`）决定数据/缓存/上传/日志/备份的实际落盘位置，并提供 `_safe_join` 防止路径遍历 |
| `backend/start.py` | 服务启动编排：初始化编码、修复 PyInstaller 控制台、确保目录、校验数据库完整性（必要时从 `backups/` 恢复）、校验前端静态资源、启动 Uvicorn |
| `backend/.env.example` | 完整的环境变量清单（80+ 项），含数据库、服务器、认证、CORS、CSRF、速率限制、日志、缓存、上传、加密、监控、迁移等分类注释 |
| `frontend/.env.example` | 前端环境变量模板，包含 `VITE_API_BASE_URL`、`VITE_APP_MODE`、`VITE_CSRF_ENABLED`、`VITE_OFFLINE_MODE`、地图瓦片路径等 |
| `frontend/vite.config.ts` | Vite 构建配置，将 `process.env.*` 注入构建产物，并通过 proxy 转发 `/api`、`/uploads` 到后端 |
| `backend/secrets/master.key` | 可选的主密钥文件，配合 `USE_ENCRYPTED_SECRETS=true` 从 `encrypted_config.json` 解密覆盖敏感配置 |

## 3. 架构与设计约定

### 3.1 配置加载优先级（后端）
1. 环境变量（最高优先级，包括进程内 `os.environ` 注入）
2. `.env` 文件（按 `backend/.env` → `.env` → `../.env` 顺序查找）
3. `Settings` 类字段默认值
4. `model_post_init` 中的运行时推导（如 `DATABASE_URL` 为空时用 `get_database_path()` 计算）
5. 加密密钥文件（当 `USE_ENCRYPTED_SECRETS=true` 时，从 `SECRETS_FILE_PATH` 解密覆盖 `SECRET_KEY`、`CSRF_SECRET_KEY`、`SMTP_PASSWORD`、`DB_ENCRYPTION_KEY`）

### 3.2 运行时密钥策略
- `ensure_runtime_secrets()` 在 `config.py` 模块导入时即调用，保证后续任何组件都能读到 `SECRET_KEY` / `CSRF_SECRET_KEY`。
- 若环境变量长度 < 32 字符视为弱密钥，强制忽略并重新生成。
- 生成的密钥通过临时文件 + `os.replace` 原子写入 `runtime_secrets.json`，Unix 下 chmod `0o600`。
- `get_or_create_secret(key, generate=...)` 提供通用扩展点，被 `config.py` 用于生产环境自动生成 `ENCRYPTION_FERNET_KEY`。

### 3.3 路径抽象与安全
- 所有磁盘路径必须通过 `paths.py` 提供的 `get_data_path` / `get_uploads_path` / `get_cache_path` / `get_log_path` / `get_backup_path` 获取，禁止直接使用 `Path.cwd()`。
- `_safe_join(base, sub_path)` 会 `resolve()` 后校验子路径未逃逸基础目录，否则抛出 `PathTraversalError`。
- 打包/生产模式下数据目录自动切换到 `%APPDATA%/bumofu-assistance`（Windows）或 `~/.bumofu`（Linux），避免 Program Files 等只读目录写入失败。

### 3.4 前端配置
- 仅 `VITE_*` 前缀的环境变量会被 Vite 注入构建产物。
- 通过 `vite.config.ts` 的 `proxy` 将 `/api`、`/uploads` 代理到 `http://127.0.0.1:8000`，E2E 测试可通过 `E2E_BACKEND_URL` 覆盖。
- 构建期通过插件生成 `version.json`，版本来源为 `package.json` 的 `version` 字段。

### 3.5 启动期安全门
- `start.py` 在启动时执行 SQLite `PRAGMA integrity_check`，每 24h 一次；损坏时优先从 `BACKUP_DIR`（默认 `./backups`）恢复，无备份则停止启动并保留现场，除非显式设置 `ALLOW_DB_RESET=1`。
- 前端静态资源完整性校验失败时拒绝启动（调用 `scripts/audit_static_assets.py`）。

## 4. 约束与规则

- **禁止硬编码密钥**：`.env.example` 明确警告“不要在此处硬编码密钥”，实际密钥由 `runtime_secrets.json` 自动生成。
- **生产环境强制安全降级**：`ENVIRONMENT=production` 时强制关闭 `DB_ECHO`（防止 SQL 日志泄露敏感字段），并强制要求 `ENCRYPTION_KEY` 非空（自动从运行时存储生成）。
- **CSRF 默认开启**：`CSRF_ENABLED=True` 为安全基线，即使单机部署也应启用。
- **Token 有效期上限**：ACCESS_TOKEN 默认 480 分钟（8 小时），符合安全基线 ≤8h 的要求。
- **路径遍历防护**：所有用户可控路径拼接必须经过 `_safe_join`，否则抛出异常。
- **`.env` 不得提交**：`.env.example` 顶部注释明确要求勿提交 `.env` 到版本库。
- **Electron 注入 DATABASE_URL**：打包后的 Electron 主进程会注入绝对路径的 `DATABASE_URL`，`paths.get_database_path()` 优先使用此值而非推断路径，避免备份/恢复作用错误文件。
- **受控的端口占用处理**：`start.py` 仅允许终止 `python.exe` 等开发后端进程，绝不强杀 `assistance-backend.exe` 等打包版桌面应用进程，防止中断用户操作。

## 5. 适用性判断

该仓库具备完整的配置系统实现：类型化的 Settings 模型、环境变量模板、运行时密钥持久化、跨平台路径抽象、启动期安全校验、前后端各自的环境变量约定。属于 **high** 置信度的已建立系统。