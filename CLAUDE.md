# CLAUDE.md - 帮扶管理信息系统

## 项目概述

帮扶管理信息系统 - 完全离线的单机版桌面应用，支持多机协同数据同步。
基于 Python FastAPI 后端 + Vue 3 TypeScript 前端 + Electron 桌面壳。

> **平台说明**: 以下命令示例以 Windows 为主（`.venv\\Scripts\\`）。Linux/macOS 用户请将路径替换为 `.venv/bin/`、将 `\\` 替换为 `/`。

> **Python 环境**: 推荐使用 Python 3.11 64-bit（`C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python311\\python.exe`）。

## 项目结构

```
├── backend/app/              # 后端（FastAPI）
│   ├── api/v1/               # API 路由（41 个路由模块）
│   │   ├── auth/             # 认证模块
│   │   ├── data/             # 数据分析
│   │   ├── import_export/    # 异步导入导出
│   │   ├── system/           # 系统管理
│   │   └── ...               # 地图、经费、项目、帮扶村、学校、政策等
│   ├── core/                 # 核心：config, security, database, cache, data_permission, transaction
│   ├── models/               # SQLAlchemy 数据模型
│   ├── schemas/              # Pydantic 数据校验
│   ├── services/             # 业务逻辑层
│   ├── middleware/            # CSRF, 审计, 请求日志, 指标
│   └── utils/                # 工具类（含 win_proactor_fix 等平台修复）
├── backend/tests/            # 后端测试
│   ├── unit/                 # 单元测试
│   ├── integration/          # 集成测试
│   └── security/             # 安全测试
├── backend/alembic/versions/ # Alembic 数据库迁移（Schema 权威来源）
├── frontend/src/             # 前端（Vue 3 + TypeScript）
│   ├── views/                # 页面视图
│   │   ├── dashboard/        # 工作台（QuickActions, layout editor）
│   │   ├── system/           # MonitoringDashboard 等系统页面
│   │   ├── analytics/        # 数据分析与帮扶村管理
│   │   └── ...
│   ├── components/           # 通用组件 + 业务组件
│   ├── stores/               # Pinia 状态管理
│   ├── router/               # 路由配置与守卫
│   ├── api/                  # API 请求层
│   └── utils/                # 工具函数
├── electron/                 # Electron 桌面壳
├── scripts/                  # 运维脚本
├── build-scripts/            # 构建脚本（Windows .exe / Linux ARM64 .deb）
├── docker/                   # Docker 配置（含 E2E 测试环境）
├── docs/                     # 项目文档（01-快速开始 ~ 04-部署文档 + ER图）
└── resources/                # 图标、前端构建产物、瓦片地图
```

## 常用命令

### 开发环境启动

```bash
cd backend && python -m venv .venv && .venv\\Scripts\\activate && pip install -r requirements.txt && python start.py
cd frontend && npm install && npm run dev
```

### 测试

```bash
cd backend && python -m pytest tests/ -v          # 后端测试（10045 passed）
cd frontend && npm test -- --run                  # 前端测试（1622 passed，125 个测试文件）
cd backend && python -m flake8 app/ --max-line-length=120
cd frontend && npm run lint && npm run typecheck

# lint-staged：仅检查 git 暂存文件（加速提交）
cd frontend && npx lint-staged

# Docker E2E 测试（Playwright 浏览器自动化 + Locust 性能测试）
docker compose -f docker-compose.yml -f docker/docker-compose.e2e.yml --profile e2e up
docker compose -f docker-compose.yml -f docker/docker-compose.e2e.yml --profile performance up
```

**已修复的测试问题**（2026-07-15）：
- ✅ 修复 20+ 个后端 API 文件中 `from app.core.transaction import safe_commit` 错误缩进导致的 `SyntaxError`/`IndentationError`（影响 11 个路由模块加载失败）
- ✅ 修复 `test_comprehensive_coverage.py` 中 3 个 `pytest.skip()` 调用 → 改为直接断言，消除所有跳过的测试
- ✅ 修复 `test_core_transaction.py` 中 `with_transaction` 装饰器 `_execute_in_transaction` 函数缺少 `return` 语句导致返回 `None`（4 个失败测试）
- ✅ 修复 `pyproject.toml` 与 `pytest.ini` 配置冲突警告（统一到 `pytest.ini`，移除 `[tool.pytest.ini_options]` 段）
- ✅ 修复 `test_comprehensive_coverage.py` 中 `SCHEMA_FILES` 列表引用不存在的 schema 模块（`rbac`/`approval`/`audit`/`effectiveness`）→ 更新为实际存在的模块
- ✅ 修复前端 `smoke.test.ts` 中 Vite 动态导入警告（添加 `.ts` 文件扩展名 + `@vite-ignore` 注释）

**历史上的已知预存测试错误已全部修复**（2026-08-14 复核，全部通过）：
- ✅ `test_import_export_history_service_full` + `test_token_blacklist_service_full`（原 16 errors）→ 已修复，86 项相关测试全部通过
- ✅ `test_chart.py` 导入错误（matplotlib 未安装）→ 已解决
- ✅ `test_batch_operations.py` "Unknown table: projects" → 已修复

### 构建

```bash
cd frontend && npm run build
bash scripts/build/sync-frontend-dist.sh          # 同步 + 完整性校验
python scripts/audit_static_assets.py --verbose   # 静态资源审计
build-scripts\\build_windows_complete.bat          # Windows 安装包
bash build-scripts/build-linux-arm64.sh           # Linux ARM64 安装包
```

## 访问地址与默认账号

- 前端: http://localhost:5173（开发）/ http://localhost:8000（生产）
- API 文档: http://localhost:8000/docs
- 默认账号: `admin` / `admin123`

## 关键设计约定

- 项目完全离线运行，安装包内置所有运行时
- Schema 权威来源: `backend/app/models/` 和 Alembic 迁移；`database/init.sql` 已删除
- `.env` 文件不纳入版本控制
- 版本号在 `backend/app/core/config.py` → `Settings.PROJECT_VERSION`（当前 1.5.0）
- 数据库: `backend/data/rural_revitalization.db`
- 生产部署前清除测试数据: `DELETE FROM supported_villages; DELETE FROM schools;`
- **`SupportedVillage.is_revitalization_tier`** 是 Boolean（是否振兴梯队），原来的 `revitalization_tier` (String) 和 `tiered_development_level` (String) 已删除
- `TieredDevelopmentLevel` 查找表已删除
- **帮扶经费** 支持动态年度（用户可选择年份添加），不再固定 2021-2026
- **工作台自定义布局**: 支持预设布局 + 拖拽排序 + 可见性切换，状态持久化到 localStorage
- **QuickActions**: 4 组 26 个快捷入口（核心业务/数据同步/审批协作/系统管理）
- **软删除模式** (2026-07-05): 模型使用 `is_active` 列（Boolean, default=True）。`is_active=False`=已删除。列表端点默认过滤 `is_active=True`，`include_deleted=true` 显示全部（管理员）。`to_dict()` 暴露 `isDeleted`/`is_deleted`。已应用于 `SupportedVillage`、`School`、`Project`、`Fund`。
- **软删除权限收敛** (2026-07-20): `include_deleted` 参数通过 `enforce_admin_include_deleted` 依赖（`app/api/v1/deps.py`）统一收敛。非管理员传入 `include_deleted=true` 静默降级为 `False`（不抛 403）。4 个端点（supported-villages/schools/projects/funds）均使用 `Depends(enforce_admin_include_deleted)`。详情端点返回 `viewableBecause` 元数据（`build_viewable_because()` 函数）。`SoftDeleteMixin` 预留 `deleted_by` 审计字段。回归测试：`tests/unit/api/test_include_deleted_enforcement.py`（49 项）、E2E：`tests/unit/test_soft_delete_e2e.py`（2 项）。
- **统一列表响应** (2026-07-08): 所有列表端点已使用 `ok_list()` (envelope)。新增列表端点必须使用 `ok_list()` 而非裸 dict。前端 `_unwrapList()` 仍兼容两种格式以保证向后兼容。
- **密码策略** (2026-07-05): `PasswordPolicy` 类必须包含 `REQUIRE_SPECIAL=True` 属性（此前缺失导致 AttributeError）。`SPECIAL_WHITELIST` 与前端正则一致。
- **前端 API 调用规则** (2026-07-05): ① 所有 api 文件必须 `import { get, post, apiRequest } from '@/api/request'`（自动解包），禁止 `import request from './request'`（返回原始 AxiosResponse）。② `get()` 第二参数直接是 params：`get(url, { refresh:true })`，不是 `get(url, { params:{ refresh:true } })`。③ Blob 下载：API 函数内部链式 `.then(r=>triggerDownload(r.data,name))`，调用方只 `await`。
- **列表视图分页重置** (2026-07-05): 所有列表视图的 create/edit/delete/import 处理器必须在调用 `loadData`/`fetchData` 之前重置 `page.value=1`/`currentPage.value=1`/`pagination.page=1`。遗漏会导致用户在第2页+时看不到新建项。
- **安全路由导航** (2026-07-05): 使用 `pushSafe()` from `@/composables/useRouterSafe` 替代 `router.push()`，避免 `NavigationFailureType.aborted` 未捕获拒绝。`useRouterSafe()` 必须在 `<script setup>` 顶层调用。
- **ErrorBoundary 单一根元素** (2026-08-01): `ErrorBoundary.vue` 必须包裹单一根元素 `<div class="error-boundary-root">`（设 `display:contents`）后内部再用 `v-if`/`v-else` 切换。**禁止**在 `<transition>` 内直接使用多根元素的 `v-if`/`v-else`，否则 Vue patch 算法会异常调用 `setAttribute('0')` 导致页面白屏崩溃。
- **角色精简与归一化** (2026-08-01): 系统角色精简为 4 个：`super_admin`/`admin`/`user`/`viewer`。旧角色值通过 `normalize_role()`（`app/core/constants.py`）自动映射：`approval_leader`/`manager` → `admin`，`operator` → `user`。`data_permission.py` 已适配。前端角色选择器默认值必须为 `user`（非 `operator`）。
- **通行码验证三级回退** (2026-08-01): `machine_code_service.py` 的 `verify_pass_code()` 增加第三级回退逻辑：当机器码+通行码匹配失败时，仅凭通行码匹配 `status=pending` 的记录并自动更新 `machine_code` 绑定。解决 Windows 下 `wmic` 命令不稳定导致机器码变化的问题。
- **files API 响应格式统一** (2026-08-01): `files.py` 上传端点必须使用 `success_response()` 返回信封格式，禁止返回裸 dict。所有文件上传操作必须补充审计日志（`AuditLogger`）。

## Pre-commit Hooks（分阶段策略）

通过 `.pre-commit-config.yaml` 配置，分两个阶段执行：

| 阶段 | Hooks | 说明 |
|------|-------|------|
| **pre-commit** | ruff（Python 快速 lint+fix）、trailing-whitespace、YAML/JSON 检查、Dockerfile tail 检查 | 仅检查变更文件，毫秒级完成 |
| **pre-push** | flake8、bandit（安全扫描）、vue-tsc（前端类型检查） | 全量质量门禁，推送前执行 |

安装: `pip install pre-commit && pre-commit install`

前端 lint-staged 配合使用（`frontend/package.json` → `"lint-staged"` 配置）：
```bash
npx lint-staged   # 仅对 git 暂存的 *.vue/*.ts/*.tsx 文件执行 eslint --fix
```

## 事务管理（with_transaction 重构）

`backend/app/core/transaction.py` 提供完整的事务管理工具链，共 6 个便捷函数：

| 函数 | 类型 | 说明 |
|------|------|------|
| `transaction(db)` | 上下文管理器 | 基础事务，自动 commit/rollback |
| `transactional` | 装饰器 | 自动查找 db 参数或创建新会话 |
| `with_transaction(isolation_level, readonly)` | 高级装饰器 | 支持隔离级别（READ COMMITTED/REPEATABLE READ/SERIALIZABLE）和只读模式 |
| `nested_transaction(db)` | 上下文管理器 | 嵌套事务（savepoint） |
| `savepoint(db, name)` | 上下文管理器 | 命名保存点，可独立回滚 |
| `retry_on_deadlock(max_retries)` | 装饰器 | 死锁自动重试（默认3次） |

辅助工具: `BatchOperation` 类（`batch_insert` / `batch_update` / `batch_delete`），每批 1000 条。

## CI/CD

### PR Checks（`.github/workflows/pr-checks.yml`）

每次 PR 触发：后端测试、前端测试、flake8 检查、覆盖率报告上传到 Codecov。

### Nightly Full Test（`.github/workflows/nightly-full.yml`）

每天凌晨 2:00 UTC 自动运行，也可手动触发（`workflow_dispatch`）：
- 后端全量测试 + HTML/JSON 覆盖率报告 + JUnit XML 结果
- 前端全量测试 + 覆盖率
- Codecov 上传（backend-nightly / frontend-nightly flags）
- 质量报告汇总（Artifact）

### Codecov 集成

PR Checks 和 Nightly 工作流均上传覆盖率到 [Codecov](https://codecov.io/)：
- PR 中显示覆盖率变更 diff
- Nightly 用独立 flags 追踪趋势
- 使用 `codecov/codecov-action@v4`

## 技术栈升级记录

### Sass 1.101.0（modern-compiler API）

前端 `frontend/package.json` → `devDependencies.sass: "^1.101.0"`，使用 modern-compiler API（`vite.config.ts` 中配置 `css.preprocessorOptions.scss.api: 'modern-compiler'`），编译速度显著提升。

### 数据库迁移整合

`backend/alembic/versions/012_consolidate_baseline.py` 将早期分散的迁移脚本整合为单一基线迁移，减少 Alembic 迁移链长度，便于新环境初始化。

## 故障排查

### 启动崩溃 - WinError 1392（文件或目录损坏）

**症状**: 后端启动时 `OSError: [WinError 1392] 文件或目录损坏且无法读取`，堆栈在 `starlette/staticfiles.py`。

**修复**: 重命名损坏目录 → 重建 → 清理。
```bash
mv resources/frontend resources/frontend_corrupted
mv frontend/node_modules frontend/node_modules_corrupted
cd frontend && npm install && npm run build && cp -r dist ../resources/frontend
```
**根本修复**: 管理员权限运行 `chkdsk D: /F` 修复文件系统。

### 前端 404 - JS/CSS Not Found

**症状**: 文件存在但浏览器 404，部分文件正常加载。

**修复**: 彻底重建 + 同步脚本 + 清除浏览器缓存。
```bash
cd frontend && npm run build
bash scripts/build/sync-frontend-dist.sh    # 先清后拷 + 校验
python scripts/audit_static_assets.py --verbose
```

### WinError 10054 - 连接重置

已在 `backend/app/utils/win_proactor_fix.py` 通过三层纵深防御修复（monkey-patch ProactorEventLoop），`start.py` 和 `main.py` 自动加载。

> **v1.2.0 Logger 修复**: `win_proactor_fix.py` 中的 logger 从 `__name__` 方式获取，避免在模块导入早期阶段因日志系统未初始化而导致的 `KeyError` / `"No section: 'formatters'"` 错误。使用 `logging.getLogger(__name__)` 并确保 logger 实例在函数调用时才被引用。

### 登录超时（bcrypt 5.x 兼容性）

`backend/app/core/security.py` 已注入 `_bcrypt.__about__` 使 passlib 能加载 bcrypt C 扩展，`verify_password()` 耗时从 ~30s 降至 ~200ms。

### 页面白屏 - setAttribute('0') is not a valid attribute name

**症状**: 工作台首页等使用 `<transition>` 包裹 `ErrorBoundary` 的页面白屏，控制台报 `Failed to execute 'setAttribute' on 'Element': '0' is not a valid attribute name`。

**根因**: `ErrorBoundary.vue` 在 `<transition>` 组件内使用 `v-if`/`v-else` 双根元素切换，Vue 的 patch 算法在处理 transition 的 `patchProp` 时将数字索引 `0` 误作为属性名调用 `setAttribute`。

**修复**: 包裹单一根元素 `<div class="error-boundary-root">` 并设 `display:contents`，内部再用 `v-if`/`v-else` 切换。

### 注册时"通行码无效或已被使用"

**症状**: 新用户注册时明明通行码正确，但系统提示"通行码无效或已被使用"。

**根因**: Windows 环境下 `wmic` 命令生成的机器码可能因进程重启、系统更新或权限变化而不一致，导致机器码+通行码双重匹配失败。

**修复**: `machine_code_service.py` 新增第三级回退逻辑，仅凭通行码匹配 `status=pending` 的记录并自动更新 `machine_code` 绑定。
