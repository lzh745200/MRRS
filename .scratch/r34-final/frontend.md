# R34 最终复检 — 前端切片（task: 前端最终复检 + 冗余清理）

- **负责人**：frontend-probe
- **时间**：2026-10-19 18:53 ~ 19:05（Asia/Shanghai）
- **基线**：v1.15.12 / HEAD 2ad1f47（origin 同步）
- **范围**：frontend/src、frontend/tests（未动 backend/electron/scripts/版本/CI/根配置；未 commit）
- **可复现脚本**：.scratch/r34-final/_tools/deadcode.mjs、reachability.mjs；复用 .scratch/w24-enterprise-probe/_tools/{dump_routes.py,contract_compare.mjs,dump_menus.py}

---

## 0. 结论摘要

| 项 | 结论 |
|---|---|
| R33 单位授权前端测试 | ✅ **测试文件已存在且已跟踪**（Lead 消息中"无测试文件"判断有误，已澄清）；3 文件 36 tests 全绿，OrgGrant.vue / GrantImport.vue / orgGrants.ts **四列 100%** |
| R33 真实 CI 风险 | ✅ 已修：router-index.test.ts 二次真实 import 两页 → 违反"单执行者"不变量；已加 vi.mock 桩，router/index.ts 仍 100% |
| API 契约 | ✅ 830 条后端路由 vs 528 个前端调用点，**匹配 528 / 不匹配 0** |
| 菜单/权限单一源 | ✅ check_menu_alignment.py A~E 通过（6 板块 / 102 key / 83 带 path / 160 路由路径 / 69 menuKey） |
| 路由可达性 | ⚠️ **发现 6 个页面无导航入口**（含 R33 两页，见 §2）——建议 Lead 决策补入口或下线 |
| 内存泄漏 | ✅ 0 处定时器泄漏（setInterval 均有 clearInterval+卸载钩子）；全局 listener 仅 errorHandler 单例（设计如此） |
| 控制台 | ✅ src 内无 console.log 泛滥：22 处 console.*，均为 logger 内部/错误诊断；生产 terser drop_console+pure_funcs 移除 |
| 注释代码/TODO | ✅ 连续注释代码块 0 处；TODO/FIXME/HACK 0 处 |
| 冗余清理 | ✅ 删除 2 处死导出（fundsRecycle/schoolsRecycle 的 `export { request }`）；其余候选按"无引用且无测试依赖"口径**均不满足**，只列清单不删（§3） |
| 静态门禁 | ✅ `npm run lint:check` exit 0；`npx vue-tsc --noEmit` exit 0（全部改动后复跑） |

**本轮修改文件（5 个，+18/−15）**：
1. frontend/src/api/fundsRecycle.ts（删死导出+未用默认导入）
2. frontend/src/api/schoolsRecycle.ts（同上）
3. frontend/tests/unit/router/router-index.test.ts（+ R33 两页 vi.mock 桩）
4. frontend/tests/unit/api/orgGrants.test.ts（prettier --fix，纯格式）
5. frontend/tests/unit/views/system/OrgGrant.test.ts（prettier --fix，纯格式）
（frontend/src/views/system/OrgGrant.vue 的 M 状态是 Lead 的 prettier 修复，非本轮改动）

---

## 1. R33 单位授权前端复检

### 1.1 澄清：测试文件存在（Lead 消息"grep 无匹配"为误判）
`git ls-files frontend/tests | Select-String 'Grant'` 输出：
- `frontend/tests/unit/views/system/OrgGrant.test.ts`
- `frontend/tests/unit/views/system/GrantImport.test.ts`
- `frontend/tests/unit/api/orgGrants.test.ts`
均为 R33 功能提交（554c810 / b800c49）随功能一并加入，GrantImport 测试还经 b9a676c 专门改过 mock 方式；磁盘存在，Test-Path=True。

### 1.2 覆盖率证据（当前工作区，单文件限定）
命令：
```
cd frontend && npx vitest run tests/unit/views/system/OrgGrant.test.ts tests/unit/views/system/GrantImport.test.ts tests/unit/api/orgGrants.test.ts --coverage --coverage.include='src/views/system/OrgGrant.vue' --coverage.include='src/views/system/GrantImport.vue' --coverage.include='src/api/orgGrants.ts' --coverage.reporter=text
```
结果：**3 files / 36 tests 全过**；`OrgGrant.vue / GrantImport.vue / orgGrants.ts` **Stmts 100 / Branch 100 / Funcs 100 / Lines 100**。

### 1.3 发现的真实 CI 风险（已修）
- **问题**：`frontend/tests/unit/router/router-index.test.ts` 会遍历执行**全部懒加载路由组件**（真实 import）。R33 两页未列入其 vi.mock 清单 → 同一 .vue 出现第二个执行者，违反 `frontend/vitest.config.ts` 注释 (A) 的"每个受覆盖率门禁的 .vue 全仓只允许一个测试文件执行"不变量；满量 v8 fnMap 按 id 合并可能错位 → functions 跌破 100%（与历史上 LoginEnhanced 88.23% 同一机制），这正是会让 PR Checks 变红的同类问题。
- **修复**：router-index.test.ts:135-145 给 `@/views/system/OrgGrant.vue`、`@/views/system/GrantImport.vue` 加 vi.mock 桩（懒加载函数本体仍执行）。
- **验证**：`npx vitest run tests/unit/router/router-index.test.ts --coverage --coverage.include='src/router/index.ts'` → **20 tests 通过，router/index.ts 四列 100%**。

### 1.4 R33 其它前端文件核对（`git diff --name-status b3d404a^..2ad1f47 -- frontend`）
| 文件 | 状态 | 测试覆盖 |
|---|---|---|
| src/api/orgGrants.ts | A | ✓ orgGrants.test.ts（100%） |
| src/views/system/GrantImport.vue | A | ✓ GrantImport.test.ts（100%） |
| src/views/system/OrgGrant.vue | A | ✓ OrgGrant.test.ts（100%） |
| src/router/index.ts | M（+2 路由） | ✓ router-index.test.ts（100%） |
| src/config/constants.ts | M（版本串 1.15.12） | ✓ 现有测试覆盖常量 |
**未发现其它缺测试的 R33 前端文件。**

### 1.5 交互 / 权限 / 错误态复检（代码走查）
- 路由：两页 `roles: ['admin','super_admin']` + `menuKey: 'system-permission-packs'`，与后端模块门禁 `write_route_map.py`（/api/v1/org-grants → system-permission-packs）一致；后端端点仅管理员。
- OrgGrant.vue：单位 ID 校验（`parseOrgId` 只接受正整数）、加载/保存 loading 态、保存只提交非 none 级、错误统一 `errText`（detail→message→兜底）、失败清空矩阵与行、按钮 `!meta` 禁用、导出文件名回落。
- GrantImport.vue：limit=1 只保留最后文件、未选文件提示、导入成功/失败分支、错误 detail 逐级回退、清空逻辑；导入后本机不提供编辑入口（只读语义）。
- 两页均无内存泄漏（无定时器/监听器）、无未捕获 Promise（全部 try/catch/finally）。

---

## 2. 路由 / 页面可达性复检（⚠️ 需 Lead 决策）

方法：后端菜单源（menus.py 的 83 个 path + tabs.path）∪ 前端源码内所有导航字符串 → 与前端 160 条路由路径/页面路径比对；再人工核对动态跳转（router.push({path})/query）。

**确认无任何导航入口（路由存在、页面有专属测试、后端 API 存在，但 UI 无法到达）**：
| 路由 | 页面 | 归属 | 说明/建议 |
|---|---|---|---|
| /system/org-grant | OrgGrant.vue | **R33 新增** | 单位授权配置（上级）；后端菜单源无条目、src 内除路由外 0 引用（grep 证实） → **R33 功能在 UI 完全不可用**。建议在 backend menus.py（唯一菜单源）补入口（如 system-permission-packs 关联 tab/按钮），或从权限包页面加入口 |
| /system/grant-import | GrantImport.vue | **R33 新增** | 单位授权包导入（下级唯一写入口）→ 同上，功能不可用 |
| /admin/subordinates | SubordinateManagement.vue | 历史 | 下级单位管理；无菜单/无链接（后端 /subordinates 端点存在）→ 建议补入口或下线页面+路由+测试（需决策） |
| /admin/module-policy | OrgModulePolicy.vue | 历史 | 模块策略配置；无菜单/无链接 → 同上 |
| /ai/interactive | InteractiveResult.vue | 历史 | AI 分析结果页；无入口（AI 功能入口缺失）→ 同上 |
| /data-sync/conflicts | ConflictResolution.vue | 历史 | 冲突解决页；仅路由定义（offlineMock 除外）→ DataSync 页面未提供跳转，建议补链接或下线 |

> 说明：`/profile`、`/organizations*`、`/data-analysis*`、`/import/data` 等经人工核对有真实入口（用户下拉/聚合页 Tab/QuickActions），不计入缺口。
> **未擅自删除**：这些页面均有后端能力与专属测试，删除属产品决策；补菜单入口需改 backend/app/api/v1/menus.py（Lead/后端范围）。

---

## 3. 冗余 / 死代码清理

### 3.1 已删除（确定安全，含验证）
| 文件 | 改动 | 依据 |
|---|---|---|
| frontend/src/api/fundsRecycle.ts | 删 `export { request }` + 未使用的默认导入 | 全仓无任何 `import { request } from '@/api/fundsRecycle'`（src+tests grep 0）；view 只用 restore/previewPurge/purge |
| frontend/src/api/schoolsRecycle.ts | 同上（含"保留 request 引用避免 tree-shaking"注释一并删） | 同上；SchoolsViewsBatch.test.ts 的 mock 额外键无影响 |
验证：`npx eslint` exit 0；`rececyleAndOfflineMap.test.ts` 9 tests 全过；两文件覆盖率 **四列 100%**。

### 3.2 生产不可达文件（可达性分析，306 个 src 文件：297 可达 / 9 不可达）
| 文件 | 是否删除 | 理由 |
|---|---|---|
| src/api/i18n.ts | ❌ 不删 | 生产 0 引用，但有专属测试（tests/unit/api/i18n.test.ts + api-modules.test.ts）→ 按"无引用且**无测试依赖**"口径不满足；且属后端 i18n 能力的客户端封装，删除需产品决策 |
| src/components/common/{AppEmpty,AppError,AppLoading,AppPageHeader,AppStatCard,AppTableToolbar}.vue + index.ts | ❌ 不删 | UI v2.0 设计系统组件（CLAUDE.md 有登记），各有专属测试；建议后续接入页面而非删除 |
| src/router/guards.ts | ❌ 误报 | main.ts 以裸 `import './router/guards'` 引入，静态脚本未识别裸导入 → 实际可达 |

### 3.3 其它死代码盘点（只列不删）
- **死导出**：281 个"src+tests 均无 import"的导出中，绝大多数为 `api/*.ts`/`types/*.ts` 的 interface/type（纯类型、编译期擦除，删除无收益且有契约价值）；另 287 个"仅测试引用"多是通过 `xxxApi` 命名空间对象调用的函数（静态分析假阳性）。
- **barrel 冗余**：`src/utils/index.ts` 中 `toDate/formatLocalDate/...` 等 datetime re-export 无人使用（实际调用方 52 处只用 `format/formatDateTime`）；删除收益低、风险>收益，建议保留。
- **注释代码/TODO**：0 处（已全仓扫描）。**控制台**：22 处 console.* 均为 logger/错误诊断（生产被 terser 移除），无 console.log 调试残留。

---

## 4. 可靠性与状态复检
- **内存泄漏**：`setInterval` 文件 100% 配套 `clearInterval` + `onUnmounted/onBeforeUnmount`（0 可疑）；`addEventListener` 仅 errorHandler.ts 全局 unhandledrejection 单例（main.ts 安装一次，无需移除）。
- **空态**：`App.vue` 用 `<el-config-provider :locale="zhCn">` 包裹全站 → el-table 默认空态为中文「暂无数据」；抽查 projects/supported-villages/consumption 列表无英文空态问题。个别页面显式 `empty-text`（approval/Overview、DataTier、SecretsManagement）。
- **控制台错误兜底**：utils/errorHandler.ts 全局 onerror + unhandledrejection（取消/401/silent 过滤、2s 去重）；生产 console 输出被移除。
- **无 TODO/FIXME/大段注释代码**。

## 5. API 契约 / 菜单门禁复检（回归证据）
- `backend/.venv/Scripts/python.exe .scratch/w24-enterprise-probe/_tools/dump_routes.py` → **ROUTES: 830**
- `node .scratch/w24-enterprise-probe/_tools/contract_compare.mjs` → **匹配 528 / 不匹配 0（exit 0）**
- `python scripts/check_menu_alignment.py` → **[OK] 规则 A~E 全部满足**（160 路由路径 / 69 menuKey）

## 6. 验证汇总（本轮全部改动后实测）
| 检查 | 命令 | 结果 |
|---|---|---|
| R33 三文件覆盖率 | `npx vitest run OrgGrant.test.ts GrantImport.test.ts orgGrants.test.ts --coverage --include=...` | **36 tests 过；三文件四列 100%** |
| router 覆盖率 | `npx vitest run router-index.test.ts --coverage --include='src/router/index.ts'` | **20 tests 过；四列 100%** |
| 回收站 API 清理后 | `npx vitest run recycleAndOfflineMap.test.ts --coverage --include=...` | **9 tests 过；两文件四列 100%** |
| 全量 lint | `cd frontend && npm run lint:check` | **exit 0** |
| 全量类型检查 | `npx vue-tsc --noEmit` | **exit 0** |
| 契约 / 菜单门禁 | 见 §5 | **528/528；A~E OK** |

## 7. 遗留风险 / 需 Lead 决策
1. **R33 功能 UI 不可达**（§2）：单位授权配置/导入页面无任何入口 → 发布后用户无法使用该功能。修复需改 backend/app/api/v1/menus.py（唯一菜单源）或在权限包页面加入口（frontend；我可按指示实施，需补 PermissionPacks 页测试以维持 100%）。
2. 历史 4 个不可达页面（下级单位管理/模块策略/AI 结果/冲突解决）：补入口 or 下线，需产品决策；未擅自删除。
3. 未跑全量 vitest / 覆盖率门禁（按约定 Lead 统一跑）；本切片已确认 R33 三文件 + router 单文件 100%，但全量合并口径最终以 Lead 的 CI 为准。
4. R33 两页加 vi.mock 桩属测试基础设施改动，若 Lead 后续在别处再引入对这两页的真实 import，需同步维护。
5. 未做 git 操作；未改版本/CI/根配置。
