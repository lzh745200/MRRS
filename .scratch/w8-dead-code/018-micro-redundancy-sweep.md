---
labels: [done, severity-low]
blocks: ["w8-dead-code/016-message-module-slimming.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 018: 微冗余清扫包

**What to build:** 学校旧奖学金导入端点标记 deprecated 注释转发；getPolicyTypes/getLevelOptions 去重；YearlyIndex 过渡页移除（列表直达年度总览）；UserPermissions.vue 下线重定向；fetchRoles 空函数、ChartRow summary=true 幽灵参数清理。

**Acceptance criteria:**
- [x] 各清理点 grep 零残留
- [x] 相关页面功能回归绿
- [x] 政策/学校 API 行为不变（既有测试通过）

## Resolution（W19 完成）

### 逐项处置

**① 学校旧奖学金导入端点标记 deprecated（注释转发）**
- `backend/app/api/v1/school.py`：`POST /schools/scholarship/import` 装饰器加 `deprecated=True`，
  summary/docstring 指向替代端点 `POST /schools/{school_id}/scholarship-students/import`
  （显式学校 id + 数据权限校验 + 同校同年级去重）。函数体与响应结构零改动。
  旧端点按行内「学校名」解析 school_id，与新端点（路径携带 school_id）参数模型不同，
  无法做函数级转发，「转发」以 OpenAPI deprecated 标记 + docstring/文档指路表达。
- 锁定测试：`backend/tests/unit/test_r5_probe_locks.py::TestLegacyScholarshipImportDeprecation::test_route_marked_deprecated_with_successor_pointer`。
- 文档：`docs/03-开发文档/03-API文档/API接口文档.md` 该校行标注「已弃用」并给出替代端点。
- 前端 `frontend/src/api/schools.ts` 不动：其奖学金学生 CRUD/导入调用的是**新版**
  `/schools/{school_id}/scholarship-students/*`（`views/schools/Scholarship.vue` 6 处消费），与旧端点无关联。

**② getPolicyTypes / getLevelOptions 去重**
- `frontend/src/api/policy.ts`：删除 `getPolicyTypes`（与 `getLevelOptions` 同 URL
  `/policies/options/levels` 的复制函数，全仓零生产调用方）；层级选项统一 `getLevelOptions`。
- `frontend/tests/unit/api/policyRuralWork.test.ts`：同步删除其 import 与单测。
- 复验：`grep -rn "getPolicyTypes" frontend/src frontend/tests` → **0 命中**。

**③ 年度概览过渡页移除（列表直达年度总览）**
- `git rm frontend/src/views/analytics/supported-villages/YearlyIndex.vue`（冗余选择页）。
- `frontend/src/router/index.ts`：原 YearlyIndex 路由改为**静态重定向**
  `/supported-villages/yearly → /supported-villages`。保留重定向的两条硬理由：
  ① 旧书签与后端业务体检 entry（`business_health_service.ENTRY_VILLAGE_YEARLY`）继续可用；
  ② 若直接删路由，该路径会落到动态路由 `/supported-villages/:id`（id='yearly'）渲染详情页，
  产生接口报错的坏页面。
- 「列表直达年度总览」原本已具备：`views/analytics/supported-villages/List.vue` 行内
  「年度数据」→ `/supported-villages/{id}/yearly`，由 `ListCov.test.ts`（pushSafe 断言
  `/supported-villages/11/yearly`）锁定；本轮只移除冗余选择页。
- `views/dashboard/components/QuickActions.vue`：「年度概览」按钮由旧路径改指
  `/supported-villages`（应用内不再依赖兼容重定向）；`QuickActions.test.ts` 的 DATA_PATHS 同步。
- `tests/unit/router/router-index.test.ts` 兼容重定向表新增 `['/supported-villages/yearly', '/supported-villages']`。
- 复验：`grep -rn "YearlyIndex" frontend/src frontend/tests` → **0 命中**；文件已删除。

**④ UserPermissions.vue 下线重定向**
- 视图文件已于 v1.12.1 删除（复核 `frontend/src` 零引用；`menu-config.test.ts` 负向断言锁住菜单移除）。
- 本轮补回兼容重定向：`/system/user-permissions → /system/permission-packs`
  （route 无 menuKey，不复活菜单；不触碰 menu-config 断言）。
- `router-index.test.ts` 兼容表新增该重定向用例。
- 残留测试数据清理：`tests/unit/views/system/SystemViewsBatch.test.ts` 删除
  `/system/user-permissions` 假响应与错位注释头（原 `--- UserPermissions ---` 竟挂在 ZeroTrust 用例上）。

**⑤ fetchRoles 空函数** —— 复核为**已满足，零改动**：`grep -rn fetchRoles frontend/src` → 0；
`views/system/UserManagement.vue` 的 `roleOptions` 为静态 4 角色数组（640-645 行，注释说明
不再用 `/rbac/roles` 覆盖）；`UserManagement.test.ts:346` 已留「死函数已移除」锁定注释。

**⑥ ChartRow summary 幽灵参数清理**
- `views/dashboard/ChartRow.vue`：`/projects` 请求参数由 `{ summary: true, page_size: 5 }`
  改为 `{ page_size: 5 }`。后端 `app/api/v1/projects.py::list_projects` 的 Query 参数表
  （page/page_size/keyword/project_type/status/village_id/region/year/sort_*/include_*）无 summary，
  FastAPI 静默忽略，属行为中性的清理。
- `tests/unit/views/dashboard/ChartRowCov.test.ts` 新增精确断言
  `toHaveBeenCalledWith({ method:'GET', url:'/projects', params:{ page_size:5 } })` 锁定回归。

### 命令与结果（2026-10-18）

前端（`cd frontend`）：
- `npx vitest run tests/unit/api/policyRuralWork.test.ts tests/unit/views/dashboard/ChartRowCov.test.ts tests/unit/views/dashboard/ChartRow.test.ts tests/unit/views/dashboard/components/QuickActions.test.ts tests/unit/router/router-index.test.ts tests/unit/views/system/SystemViewsBatch.test.ts`
  → **6 files / 123 tests passed，exit 0**
- `npx vue-tsc --noEmit` → **0 错误**
- `npx eslint src/api/policy.ts src/router/index.ts src/views/dashboard/ChartRow.vue src/views/dashboard/components/QuickActions.vue --max-warnings=0` → **0**
- 覆盖率定点（改动 4 个 src 文件四指标 miss 全 0）：
  `npx vitest run <上述前 5 文件> --coverage --coverage.reporter=json --coverage.reportsDirectory=%TEMP%\w8018-cov`
  → `src/api/policy.ts / src/router/index.ts / ChartRow.vue / QuickActions.vue` missed stmts/fn/branch 全 0；
  `YearlyIndex.vue` 已不在 272 个被度量文件清单。
  说明：改动未新增未覆盖行/分支；删除视图即从 `src/views/**/*.vue` 100% 门禁集合中移除。

后端（`cd backend`）：
- `.venv\Scripts\python.exe -m flake8 app/ --max-line-length=120 --count --max-complexity=16` → **0**
- `.venv\Scripts\python.exe -m pytest tests/unit/test_r5_probe_locks.py tests/unit/test_business_health.py -q`
  → **26 passed**（含新增 deprecated 锁定 1 条；学校旧端点行为锁 2 条不变；业务体检 API 零改动）
- 静态门禁复核：`python scripts/check_menu_alignment.py` → OK（backend=70 keys / frontend=53 items / 64 paths）；
  `python scripts/check_unused_scope_params.py` → NEW=0；`python scripts/security_audit.py` → Total issues: 0

### 备注（门禁口径）
- 测试文件存在**既有** prettier 告警（`policyRuralWork.test.ts:39`、
  `ChartRowCov.test.ts:46/200/226`、`QuickActions.test.ts:14-17/151/169-199/256`、
  `SystemViewsBatch.test.ts:19/33/46/58-91`）。`git diff -U0` 显示本单在这些文件仅新增
  `ChartRowCov.test.ts +91..97`、改 `QuickActions.test.ts:85`、删 `SystemViewsBatch.test.ts:96`、
  改 `SystemViewsBatch.test.ts:366`，与上述告警行**无交集**（均为 HEAD 既有格式问题）；
  且 CI 的 `npm run lint:check` 作用域是 `src`（见 `frontend/package.json`），不含 tests。
  故未做 `--fix`，避免与在途会话产生大面积格式 diff。
- 后端未改 `business_health_service.ENTRY_VILLAGE_YEARLY = "/supported-villages/yearly"`：
  兼容重定向保证该 entry 点击仍落到村列表，业务体检 API 响应保持逐字节不变。
