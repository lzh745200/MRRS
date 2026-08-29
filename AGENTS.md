# AGENTS.md - Agent Quick Reference

## Project Identity

Assistance Management Information System (帮扶管理信息系统) - Offline-first desktop app for military-civilian rural aid.
FastAPI + Vue 3 + Electron + SQLite. Windows primary, Linux ARM64 (Kylin V10) secondary.

**Full context**: See `CLAUDE.md` and `.cursorrules` for architecture details, API formats, and security requirements.

## Quick Commands

### Backend

```bash
cd backend
.venv\\Scripts\\python start.py                          # Start server (http://localhost:8000)
python -m pytest tests/ -v --tb=short -q --timeout=60   # Run all tests (~10100, 死代码清理后)
python -m pytest tests/unit/test_xxx.py -v              # Run single test file
python -m flake8 app/ --max-line-length=120             # Lint (CI gate, 0 errors)
python -m mypy app/ --config-file=mypy.ini --ignore-missing-imports  # Type check (non-blocking)
python -m bandit -r app/ -ll                            # Security scan
```

### Frontend

```bash
cd frontend
npm run dev                                             # Dev server (http://localhost:5173)
npm run test -- --run                                   # Run all tests (~5759, 300 test files, 死代码清理后)
npx vitest run tests/unit/views/xxx/xxx.test.ts        # Run single test file (tests live under tests/unit/)
npm run lint                                            # ESLint (CI gate, --max-warnings=0)
npx vue-tsc --noEmit                                    # Type check (CI gate)
npm run build                                           # Production build
npx lint-staged                                         # Lint only git-staged *.vue/*.ts/*.tsx files
```

### Combined

```bash
make test           # Run backend + frontend tests
make test-backend   # Backend tests only
make test-frontend  # Frontend tests only
make deploy-check   # Full pre-deploy validation
make clean          # Clean test artifacts
```

### Docker E2E Tests

```bash
# Playwright browser-based E2E (uses docker/docker-compose.e2e.yml)
docker compose -f docker-compose.yml -f docker/docker-compose.e2e.yml --profile e2e up

# Locust performance testing
docker compose -f docker-compose.yml -f docker/docker-compose.e2e.yml --profile performance up

# Full E2E + performance
docker compose -f docker-compose.yml -f docker/docker-compose.e2e.yml --profile full up
```

## Architecture Gotchas

### Dual API Response Format

The API uses **two response formats** - this causes most integration bugs:

| Format | Shape | Used by |
|--------|-------|---------|
| Bare | `{total, page, page_size, items}` | 0 endpoints (all converted to envelope) |
| Envelope | `{code:200, data:{...}, message:"成功"}` | `/auth/login`, `/users`, `/rbac`, `/supported-villages`, `/funds`, `/projects`, `/schools` |

**Unification progress (2026-07-05)**: 4 main list endpoints (`supported-villages`, `funds`, `projects`, `schools`) converted from bare → envelope via `ok_list()` helper in `backend/app/core/response.py`:
```python
def ok_list(items, total, page=1, page_size=20, message="成功", **kwargs):
    return success_response(data={"items": items, "total": total, ...}, message=message, **kwargs)
```
When adding new list endpoints, **use `ok_list()`** (envelope) — not bare dict.

Frontend stores use `_unwrapList()` / `_unwrapSingle()` to normalize both. The Axios response interceptor auto-expands `data.data` fields to top level of `response.data`, making envelope format transparent to frontend stores.

**Unification progress (2026-07-08)**: All list endpoints now use `ok_list()` (envelope). Previously bare-format endpoints converted: `/machine-codes`, `/pass-codes`, `/system/backup`, `/system/update-logs`, `/reports/templates`, `/funds/contracts`, `/funds/transfers`, `/funds/anomalies`, `/users` (list + pending), `/projects/{id}/funds`, `/projects/{id}/tasks`, `/data/reports/villages`, `/data/reports/subscriptions`, `/data/data-reports/pending`, `/data/data-reports/received`. Earlier conversions (2026-07-05): `/work-logs`, `/scholarship-students`, `/rural-works`, `/policies`, `/organizations`, `/audit-logs`, `/operation-logs`, `/data-sync/*`, `/import-export/*`, `/map/*`.

### Data Isolation

- `organization_id` field is **mandatory** on all queries
- Use `filter_by_data_scope(query, model, user, db=db)` from `app/core/data_permission.py`
- Missing this = security vulnerability (military audit will fail)

### Soft Delete Pattern

Models use `is_active` column (Boolean, default=True, nullable=False) for soft deletes:
- `is_active=False` = deleted (hidden from default queries)
- `include_deleted=true` query param shows all records (admin only)
- `to_dict()` exposes `isDeleted` (camelCase) and `is_deleted` (snake_case) fields
- Currently applied to: `SupportedVillage`, `School`, `Project`, `Fund`
- Migration: `alembic/versions/village_softdel_001_add_is_active.py`
- List endpoints filter `is_active=True` by default; detail endpoints show soft-deleted records (for audit)
- Cross-org access returns **403** (not 404) to distinguish "exists but not yours" from "doesn't exist"

**Permission Convergence (2026-07-20 Security Hardening)**:
- `include_deleted` parameter is converged via `enforce_admin_include_deleted` dependency in `app/api/v1/deps.py`
- Non-admin users passing `include_deleted=true` get **silently downgraded** to `False` (no 403 to avoid exposing the parameter)
- Admin users (role=`admin`/`super_admin` or `is_superuser=True`) get `True` passed through
- All 4 soft-delete endpoints use `Depends(enforce_admin_include_deleted)` — no inline permission checks
- Detail endpoints return `viewableBecause` metadata via `build_viewable_because(current_user, record)`:
  - `"admin"` when admin views a soft-deleted record
  - `null` for active records or non-admin viewers
- `SoftDeleteMixin` in `models/base.py` now includes `deleted_by` column (Integer, nullable) for audit tracking
- Regression tests: `tests/unit/api/test_include_deleted_enforcement.py` (49 tests: unit + API integration)
- E2E tests: `tests/unit/test_soft_delete_e2e.py` (2 tests: full lifecycle for supported-villages + funds)

### Route Registration

New backend routes must be registered in `app/api/v1/__init__.py`:
- Sub-packages (auth, data, import_export, system): add explicit import
- Business modules: add name to `_BUSINESS_MODULES` list (line 112)

### Frontend Route Loading

All routes use lazy loading: `component: () => import('@/views/xxx/List.vue')`

## Testing

### Backend Coverage

- Minimum: 98% (CI gate via `--cov-fail-under=98`)
- Local target: 98% (Makefile)
- Nightly: 98% (`.github/workflows/nightly-full.yml`)
- Test env vars: `ENVIRONMENT=test`, `SECRET_KEY=test-secret-key-for-ci`

### Frontend Coverage

- Vitest with V8 coverage provider
- Coverage thresholds in `vitest.config.ts`

### Codecov Integration

Coverage is uploaded to Codecov via `codecov/codecov-action@v4` in two workflows:
- **PR Checks** (`.github/workflows/pr-checks.yml`): Shows coverage diff on each pull request
- **Nightly Full** (`.github/workflows/nightly-full.yml`): Uploads with `backend-nightly` / `frontend-nightly` flags for trend tracking

### Pre-commit Hooks (Staged Strategy)

Installed via `pre-commit install`. Uses a two-stage strategy defined in `.pre-commit-config.yaml`:

| Stage | Hooks | Scope |
|-------|-------|-------|
| **pre-commit** | ruff (Python lint+fix, line-length=120), trailing-whitespace, YAML/JSON validation, Dockerfile tail check | Changed files only (fast) |
| **pre-push** | flake8, bandit (security scan), vue-tsc (frontend type check) | Full project (quality gate) |

All stage-2 hooks are orchestrated through `scripts/pre_commit_hooks.py`.

**lint-staged** (`frontend/package.json` `"lint-staged"` config): Runs `eslint --fix` only on git-staged `*.vue`, `*.ts`, `*.tsx` files. Use `npx lint-staged` before committing frontend changes to catch issues early.

### Docker E2E Testing

`docker/docker-compose.e2e.yml` provides two optional service profiles:

- **e2e**: Playwright-based browser automation (`mcr.microsoft.com/playwright:v1.45.0-jammy`), runs `tests/e2e/test_e2e.py`
- **performance**: Locust load testing (`locustio/locust:2.28`), runs `tests/performance/locustfile.py`

Both depend on `assistance-system` service with `condition: service_healthy`. Use `--profile e2e|performance|full` to select.

## Transaction Management (with_transaction Refactoring)

`backend/app/core/transaction.py` provides 6 convenience functions for transaction control:

| Function | Type | Purpose |
|----------|------|---------|
| `transaction(db)` | Context manager | Basic transaction, auto commit/rollback |
| `transactional` | Decorator | Auto-detect db param or create new session |
| `with_transaction(isolation_level, readonly)` | Decorator | Isolation levels (READ COMMITTED/REPEATABLE READ/SERIALIZABLE) + read-only mode |
| `nested_transaction(db)` | Context manager | Nested transaction via savepoints |
| `savepoint(db, name)` | Context manager | Named savepoint, independently rollback-able |
| `retry_on_deadlock(max_retries)` | Decorator | Deadlock auto-retry (default 3 attempts) |

Isolation levels are validated at decorator definition time via a whitelist (`_VALID_ISOLATION_LEVELS`) to prevent SQL injection.

Also includes `BatchOperation` class with `batch_insert` / `batch_update` / `batch_delete` (1000 records/batch).

## Build Pipeline

### Frontend Build

```bash
cd frontend && npm run build  # Outputs to frontend/dist/
```

**Sass**: v1.101.0 with modern-compiler API (`vite.config.ts` → `css.preprocessorOptions.scss.api: 'modern-compiler'`). Significantly faster compilation.

### Sync to Backend (for production)

```bash
bash scripts/build/sync-frontend-dist.sh   # Copies dist/ → resources/frontend/ with integrity check
python scripts/audit_static_assets.py --verbose  # Verify static assets
```

### Electron Packaging

```bash
# PyInstaller 打包后端（内含 Python 解释器 + 全部 pip 依赖 + SQLite）
cd backend && python -m PyInstaller assistance-backend.spec --clean --noconfirm

# electron-builder 打包 NSIS 安装包
npx electron-builder --win --x64    # Windows x64

# 或通过 Makefile
make build-win-x64                  # 一键构建 Windows x64
make build-kylin                    # Linux ARM64 DEB
```

安装包结构：Electron 运行时 + `assistance-backend.exe`（PyInstaller）+ Vue3 前端 + VC++ Redistributable（NSIS 钩子静默安装）。目标机器零依赖。

### DEB Packages (Docker cross-compile)

```bash
make build-deb-amd64    # x86_64
make build-deb-arm64    # ARM64 (for Kylin V10)
make build-kylin        # Kylin V10 standalone (no Electron, pure web)
```

## CI Workflows

### PR Checks (`.github/workflows/pr-checks.yml`)

Triggered on every PR. Runs backend tests, frontend tests, flake8, and uploads coverage to Codecov.

### Nightly Full (`.github/workflows/nightly-full.yml`)

Scheduled daily at 2:00 UTC + manual trigger (`workflow_dispatch`). Three jobs:
- `backend-full`: Full test suite with HTML/JSON coverage + JUnit XML + Codecov upload
- `frontend-full`: Full test suite with coverage + Codecov upload
- `quality-report`: Aggregated pass/fail summary artifact (depends on both)

### CI Workflow Permissions

| Workflow | Explicit permissions | Rationale |
|----------|---------------------|-----------|
| `pr-checks.yml` | `contents: read`, `pull-requests: read` | Read-only; no releases |
| `build-arm64.yml` | `contents: write` | Needs write for `softprops/action-gh-release` |
| `build-windows.yml` | `contents: write` | Needs write for `electron-builder` + gh-release |
| `nightly-full.yml` | `contents: read` | Read-only; artifacts only |

## Migration Management

### Baseline Consolidation

`backend/alembic/versions/012_consolidate_baseline.py` consolidates early scattered migration scripts into a single baseline migration, reducing the Alembic migration chain length for faster new-environment initialization.

## Known Issues & Fixes

### Pytest Config Conflict (Fixed 2026-07-15)

Previously, both `pytest.ini` and `pyproject.toml` had `[tool.pytest.ini_options]` sections, causing pytest to warn: `WARNING: ignoring pytest config in pyproject.toml!`. Fixed by consolidating all pytest config into `pytest.ini` and removing the `[tool.pytest.ini_options]` section from `pyproject.toml`. The `pyproject.toml` now only retains `[tool.coverage.*]` sections.

### Misplaced `safe_commit` Import (Fixed 2026-07-15)

A previous automated edit inserted `from app.core.transaction import safe_commit` at wrong indentation levels inside 20+ API files, causing `SyntaxError`/`IndentationError` in 11 route modules. All instances have been removed — the import belongs at module top-level (already present in most files) or should use `safe_commit(db)` at call site without a local import.

### `with_transaction` Missing Return (Fixed 2026-07-15)

`_execute_in_transaction()` in `app/core/transaction.py` was missing `return` before `_execute_with_existing_session()` call, causing all `@with_transaction`-decorated functions with an existing session to return `None`. Fixed by adding the missing `return` statement.

### `pytest.skip()` Removal (Fixed 2026-07-15)

Removed all 3 `pytest.skip()` calls in `test_comprehensive_coverage.py` — tests now fail on import errors instead of silently skipping. Also updated `SCHEMA_FILES` list to reference actual existing schema modules.

### Vue setAttribute('0') Page Crash (Fixed 2026-08-01)

`ErrorBoundary.vue` used `v-if`/`v-else` dual-root elements inside `<transition>`, causing Vue's patch algorithm to call `setAttribute('0')` — crashing the page. Fixed by wrapping in a single root `<div style="display:contents">`.

### Passcode Validation False Rejection (Fixed 2026-08-01)

Windows `wmic` generates inconsistent machine codes across process restarts. `machine_code_service.py` `verify_pass_code()` now has a third-level fallback: match by pass_code only (ignoring machine_code), then auto-update the `machine_code` binding.

### Role Simplification (2026-08-01)

System roles reduced from 7+ to 4: `super_admin`/`admin`/`user`/`viewer`. `normalize_role()` in `app/core/constants.py` maps deprecated roles (`approval_leader`/`manager`→`admin`, `operator`→`user`). `data_permission.py` uses `normalize_role()` for backward compatibility. Frontend default role is now `user` (not `operator`).

### files.py Response Format (Fixed 2026-08-01)

`files.py` upload endpoint was returning bare dict instead of `{code:200, data:{...}, message:"成功"}` envelope. Fixed to use `success_response()`. Removed unused `db` param. Added audit logging.

### Backup Upload-Restore (2026-08-09)

`POST /api/v1/system/backup/upload-restore` — the "import any backup package" endpoint:
- Supports **encrypted** backups via `password` Form field (PBKDF2+Fernet, same as `BackupService._decrypt_to_temp`)
- **Streams** upload to disk in 8MB chunks (never `await file.read()` whole — OOM risk with multi-GB packages); 10GB defensive cap → 413
- Pre-validates after save: encrypted marker requires password; plain ZIP must be a valid zip containing `data/rural_revitalization.db`; `BackupRestoreError` → 400 (user error, not 500)
- All rejection paths (HTTPException) delete the temp file — zero disk residue
- `GET /system/backup` list returns `is_encrypted` per item (frontend restore dialog shows password field only then)

### Token Blacklist Is Unified (2026-08-09)

The in-memory `TokenBlacklist` class in `app/core/security.py` was **deleted** (dead code — JWT validation goes through `app/core/token_manager.py` → `app/core/token_blacklist.py` module with DB persistence). `app/services/token_blacklist_service.py` (async service, zero app references) also deleted. Admin force-logout uses `revoke_token()`; sessions stats use `core/token_blacklist.count()`. NEVER add a third blacklist implementation — use `app.core.token_blacklist`.

### ENCRYPTION_KEY Auto-Provision (2026-08-09)

Production mode with empty `ENCRYPTION_KEY` now auto-loads/generates a persisted Fernet key via `runtime_secrets.get_or_create_secret("ENCRYPTION_FERNET_KEY")` (per-machine random, survives restarts, same key the encryption service falls back to — no data-compat break). The old "默认测试密钥" warning is gone; a warning only fires if even auto-generation fails.

### WinError 10054 (Connection Reset)

Auto-fixed by `app/utils/win_proactor_fix.py`. Loaded by `start.py` and `main.py`. No action needed.

> **v1.2.0 Logger Fix**: The logger in `win_proactor_fix.py` was refactored to use `logging.getLogger(__name__)` at module level with defensive instantiation, avoiding `KeyError` / `"No section: 'formatters'"` errors that occurred when the logging system wasn't yet initialized during early module import.

### bcrypt Login Timeout

Passlib + bcrypt 5.x incompatibility fixed in `app/core/security.py`. Verify `verify_password()` takes ~200ms, not 30s.

### PasswordPolicy REQUIRE_SPECIAL

`PasswordPolicy` class in `app/core/security.py` has `REQUIRE_SPECIAL = True` attribute (added 2026-07-05 — was missing, caused `AttributeError` when `validate()` referenced it). Also defines `SPECIAL_WHITELIST = set("!@#$%^&*()-_=+[]{}|;:,.<>?")`. When adding new password rules, ensure the class attribute exists BEFORE `validate()` references it.

### Frontend 404 on Static Files

After `npm run build`, run `scripts/build/sync-frontend-dist.sh` to sync. Browser cache may need clearing.

### ARM64 Build: Never Use --no-cache

`build-arm64.yml` uses Docker buildx with QEMU (ARM64 emulation on x86 CI runners). Docker layer caching is the only reason builds finish in ~30min instead of hours. Never add `--no-cache` to the `docker buildx build` command.

### Dockerfile Output Truncation (Intentional)

`Dockerfile.kylin-standalone` pipes RUN commands through `tail -N` (npm ci: `-5`, build: `-10`, pip: `-10`, pyinstaller: `-20`) to keep CI logs manageable. Downstream `test -f`/`test -d` commands in the same stage still catch failures. Don't remove `tail` pipes.

### Pre-commit Hooks: Dockerfile Check

`.pre-commit-config.yaml` includes a `check-dockerfile-tail` hook that rejects Dockerfile RUN commands ending in `2>&1` without `| tail`. This prevents accidental removal of output truncation in ARM64 builds.

### Audit Log Persistence (Military Compliance)

AuditLogger.log() writes to both Python logging (app.log) AND database (audit_logs + login_attempts tables). The DB persistence was added 2026-06-23 after discovering audit events were only going to file logs. End-to-end verified: login failure → login_attempts table count increments.

### Database Path (Packaged Mode)

In packaged (Electron) mode, the SQLite database is stored at Windows: `%APPDATA%/<appName>/database/rural_revitalization.db` (Electron `userData/database/`) / Linux: `~/.bumofu/data/` — NOT the install directory (Program Files requires admin write). Electron main.js injects `DATABASE_URL` env var to backend.exe.

## Common Frontend Bug Patterns (Fixed 2026-07-05)

Three bug patterns were found across the codebase and batch-fixed. **When adding new views/API calls, verify these patterns are followed.**

### 1. `response.success` on raw AxiosResponse

**Bug**: Files using `import request/api from './request'` (raw axios) checked `response.success` — but `AxiosResponse` has no `.success` property (only the envelope body does). Silent `undefined` → no error thrown → code path skipped.

**Fix**: Use `response.data.success` (access the envelope body first). Affected files (6 fixed): `PackageVersion.vue`, `ConflictResolution.vue`, `Export.vue`, `Import.vue`, `MapTileManager.vue`.

**Rule**: 
- `import { get, post, apiRequest } from '@/api/request'` → returns auto-unwrapped `res.data` → use `response.success`
- `import request/api from './request'` → returns raw `AxiosResponse` → use `response.data.success`

### 2. `get()` params double-wrapping

**Bug**: `get(url, { params: { marker_type } })` is WRONG for the auto-unwrapped wrapper from `@/api/request`. The wrapper passes the 2nd arg directly as `params` to axios — nesting it under `params` again means the marker_type never reaches the backend.

**Fix**: Use `get(url, { marker_type })` (flat params as 2nd arg). Only raw `request.get()` uses `{ params: {...} }`.

**Rule**: ALL api files MUST use `{ get, post, apiRequest } from '@/api/request'`. NEVER `import api/request from './request'` (returns raw AxiosResponse). Blob downloads: API funcs must chain `.then(r => triggerDownload(r.data, name))` internally; callers just `await`, don't access `res.data`.

### 3. Pagination reset missing in list views

**Bug**: Create/edit/delete/import handlers called `loadData()`/`fetchData()` without first resetting pagination to page 1. If user was on page 2+, the new item was invisible (page 2 of a shorter result set = empty).

**Fix**: ALL list view create/edit/delete/import handlers MUST reset pagination to page 1 BEFORE calling `loadData`/`fetchData`:
```typescript
// ✅ Correct
const handleCreate = async () => {
  await createApi(payload)
  currentPage.value = 1   // ← reset BEFORE loadData
  await loadData()
}
// ❌ Wrong (omitted reset)
const handleCreate = async () => {
  await createApi(payload)
  await loadData()         // ← user stays on page 2, sees nothing
}
```
Fixed in 16 files (43 handler instances): `funds/{ContractManage,TransferVoucher,EnhancedList,AnomalyList}.vue`, `projects/{List,ProjectManagement}.vue`, `schools/List.vue`, `policies/List.vue`, `system/{UserManagement,TaskManager,UpdateLogs}.vue`, `dataPackage/{List,ReceivePackage}.vue`, `ruralWorks/Task.vue`, `organization/PassCodeManagement.vue`, `admin/MachineCodeManagement.vue`.

### 4. `router.push()` without error handling

**Bug**: Raw `router.push()` returns a Promise; if navigation is aborted (e.g., duplicate route) it throws `NavigationFailureType.aborted` — an unhandled rejection.

**Fix**: Use `pushSafe()` from `@/composables/useRouterSafe` (wraps `router.push` with try/catch + optional fallback to `window.location.href`). Fixed in 9 files: `analytics/map/index.vue`, `analytics/supported-villages/YearlyIndex.vue`, `auth/{ForgotPassword,LoginEnhanced}.vue`, `dashboard/{index,PageHeader}.vue`, `dataSync/{ConflictResolution,Import}.vue`, `funds/index.vue`.

**Rule**: `useRouterSafe()` MUST be called at Vue `<script setup>` top level (NOT inside event handlers — `inject()` only works during setup).

### 5. ErrorBoundary multi-root in `<transition>` (Fixed 2026-08-01)

**Bug**: `ErrorBoundary.vue` used `v-if`/`v-else` with two separate root elements inside a `<transition>` wrapper. Vue's patch algorithm treated the numeric index `0` as an attribute name and called `setAttribute('0')`, crashing the page with `Failed to execute 'setAttribute' on 'Element': '0' is not a valid attribute name`.

**Fix**: Wrap both branches in a single root element (`<div class="error-boundary-root" style="display:contents">`) so Vue's diff sees one vnode root.

**Rule**: When using `<transition>` or `<KeepAlive>`, the child MUST have exactly one root element. If you need `v-if`/`v-else` branching, wrap both in a single root `<div style="display:contents">` to preserve layout semantics.

## Test-Writing Conventions (Added 2026-07-17)

The 2026-07 coverage sprint introduced **244 failing tests** written against assumed APIs. These conventions prevent recurrence.

### Frontend (vitest)

1. **Mock ALL named exports the source imports**: `vi.mock('@/api/request')` must return every named export the module under test imports (`get`/`post`/`put`/`del`/`apiRequest`), plus `default` if the source uses it, plus `parseContentDisposition`/`downloadBlob` when `src/api/helpers/blobDownload.ts` is in the import chain. Missing export → `No "X" export is defined on the mock`. Define mock fns via `vi.hoisted`.
2. **Helpers return the unwrapped body**: `get/post/put/del/apiRequest` auto-unwrap the envelope — `mockResolvedValue(body)` NOT `mockResolvedValue({ data: body })`.
3. **`get(url, params)` takes params directly** (2nd arg), NOT axios-style `{ params: {...} }`. Assert `toHaveBeenCalledWith(url, { page: 1 })`.
4. **Never mock `@/utils/request`** — the module does not exist.
5. **Blob downloads** go through `downloadBlobAsFile`: mock `downloadBlob` and assert it received `(Blob, filename)` instead of spying on DOM anchor clicks.

### Backend (pytest)

6. **List endpoints return the `ok_list()` envelope**: assert `resp.json()["data"]["total"]`, never `resp.json()["total"]`.
7. **`dependency_overrides` is app-global**: two fixtures overriding `get_current_user` cannot be used in the same test (last one wins for BOTH). Switch identity explicitly per phase inside one test with try/finally restore (see `test_security_data_isolation.py`).
8. **Data scope semantics** (`get_data_scope`): role `user` → OWN (own records only); `admin`/`manager`/`approval_leader` → OWN_DEPT; `super_admin` → ALL. Write `check_record_access` assertions accordingly.
9. **Verify model class names** against `app/models/` before importing in tests (e.g., `TeaPlantation` not `Industry`, `FundStatusHistory` not `FundHistory`, `Issue` not `IssueTracking`).
10. **No leaked threads/timers in tests**: functions submitted to the global executor must finish in ≤2s even when testing timeouts (a `sleep(100)` leaked thread once hung the whole suite at 18%).
11. **No module-level `os.environ` mutation** in test files — use a `monkeypatch` fixture (`monkeypatch.setattr` on the target module constant).
12. **Before `mock.patch(target)`, confirm the attribute exists** on the current source module (refactors rename things; stale patch targets fail with AttributeError).

## Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/auth/login` | 5 | 60s |
| `/auth/register` | 3 | 60s |
| `/auth/refresh` | 10 | 60s |
| `/auth/csrf-token` | 30 | 60s |

Implementation: `app/core/security.py` → `check_rate_limit()` (sliding window, in-memory).
CSRF token rate limiting added in `app/api/v1/auth/auth.py` line ~509.

## Security Checklist (Military Audit Required)

Every new feature must verify:
1. [ ] Write operations call `write_work_log()`
2. [ ] Data queries use `filter_by_data_scope()`
3. [ ] Sensitive fields encrypted via `EncryptionService`
4. [ ] Frontend displays masked data via `DataMaskingService`
5. [ ] Errors logged (logger.error + audit log)

## Key Files Reference

| Purpose | Path |
|---------|------|
| Version number | `backend/app/core/config.py` → `Settings.PROJECT_VERSION` (v1.10.0) |
| DB schema source | `backend/app/models/` + `backend/alembic/versions/` |
| Baseline migration | `backend/alembic/versions/012_consolidate_baseline.py` |
| API router registry | `backend/app/api/v1/__init__.py` → `_BUSINESS_MODULES` |
| Envelope list helper | `backend/app/core/response.py` → `ok_list()` |
| Transaction utilities | `backend/app/core/transaction.py` (6 helper functions) |
| Soft delete migration | `backend/alembic/versions/village_softdel_001_add_is_active.py` |
| Password policy | `backend/app/core/security.py` → `PasswordPolicy` class |
| Role constants & normalization | `backend/app/core/constants.py` → `normalize_role()`, `PRACTICAL_ROLES` |
| Machine code & passcode service | `backend/app/services/machine_code_service.py` → `verify_pass_code()` (3-level fallback) |
| ErrorBoundary component | `frontend/src/components/common/ErrorBoundary.vue` (single-root pattern) |
| Frontend HTTP client | `frontend/src/api/request.ts` |
| Safe router composable | `frontend/src/composables/useRouterSafe.ts` |
| Design tokens | `frontend/src/styles/tokens.scss` |
| SCSS vars injection (no CSS rules allowed) | `frontend/src/styles/tokens-vars.scss` (vite `additionalData`; rules live in tokens.scss via index.scss only) |
| lint-staged config | `frontend/package.json` → `"lint-staged"` |
| Pre-commit config | `.pre-commit-config.yaml` (staged strategy: pre-commit + pre-push) |
| E2E Docker compose | `docker/docker-compose.e2e.yml` |
| Guizhou region data | `frontend/src/data/guizhouRegion.ts` |
| Electron main | `electron/main.js` |
| PyInstaller spec | `backend/assistance-backend.spec` |
| NSIS hook | `build-scripts/electron-builder-nsis-hook.nsh` |
| CI pipeline | `.github/workflows/build-windows.yml` |
| ARM64 build | `.github/workflows/build-arm64.yml` + `docker/Dockerfile.kylin-standalone` |
| PR checks | `.github/workflows/pr-checks.yml` |
| Nightly CI | `.github/workflows/nightly-full.yml` |
| WinError 10054 fix | `backend/app/utils/win_proactor_fix.py` |

## W1 安全不变量（2026-08-24，违反即回归）

以下约束由回归测试锁定，改动相关代码前必读（安全边界详见 docs/adr/0008 破窗恢复；各条的锁定测试以行内路径为准）：

1. **认证唯一出口**：\get_current_user\ 已接入黑名单+类型校验；access token 必带 jti；登出递增 token_version。不要绕过 \	oken_manager.validate_token\ 另建校验路径。
2. **限流签名 fail-closed**：\check_rate_limit(key, *, request, limit, window)\ —— key 为首个参数且必填，缺失抛 ValueError；禁止位置传参字符串到旧 request 位。
3. **loopback 门禁**：machine-code 校验码/密码重置、permission-packages import/confirm 未认证调用仅限本机（基于 request.client.host，禁读 X-Forwarded-For）。判定函数：各模块 \_client_is_loopback\。
4. **公开重置排除管理员**：admin/super_admin 账号走管理端通道，公开端点恒 403。
5. **通行码 HMAC**：\PASS_CODE_SECRET\ 未显式配置时自验证路径拒绝（fail-closed）；回退改绑机器码必须 write_work_log。
6. **错误细节不出站**：api/v1 响应字段禁止内插异常对象——源码扫描测试 \	ests/unit/api/test_no_error_detail_leak.py\ 会拦截；新 except 分支 detail 用泛化文案 + logger.error(exc_info=True)。
7. **删库守卫**：start.py integrity 失败默认 SystemExit(1) 保留现场；自动重建需环境变量 ALLOW_DB_RESET=1。
8. **测试禁令**：禁止对 machine_code_service 等 services 模块 importlib.reload（类对象分裂导致跨文件 patch 失效）；用 monkeypatch.setattr 打模块常量。

## CI 协调须知（2026-08-24）

- **不要取消** `Nightly Full Test Suite` 的 `backend-full` 任务（90 分钟预算属正常耗时；
  runs #10/#11 均于约 30 分钟被外部取消，需各会话协调停止该操作）。
- 安装包工作流已收敛为 **仅 tag v* / 手动触发**；push main 只跑 PR Checks。
- 仓库已转为 public，托管 runner 私仓配额限制解除（8/15-8/24 的全线秒败即配额所致）。

