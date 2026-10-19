# W24 企业级深度探测 — 前端切片报告（task-2）

- **负责人**：frontend-probe（task-2）
- **探测时间**：2026-10-19 12:07 ~ 12:35（Asia/Shanghai）
- **基线**：v1.15.4 / git HEAD 5a182cd；后端 flake8、7 个棘轮门禁、根 scripts 8 门禁、bandit、前端 eslint / vue-tsc、版本单源均绿（Lead 已验证，本切片只做增量复核）
- **写入范围**：frontend/src、frontend/tests、frontend/public（本报告另存 .scratch/w24-enterprise-probe/）
- **可复现脚本目录**：.scratch/w24-enterprise-probe/_tools/

---

## 0. 结论摘要

| 级别 | 数量 | 已修 | 待修/待复核 | 说明 |
|---|---|---|---|---|
| P0 | 1 | 0 | 1（环境限制） | 本机 `npm run build` 失败（esbuild 临时文件删除被系统拒绝）；判定为**本机环境限制**，需干净 runner 复核，不改生产构建配置 |
| P1 | 3 | 3 | 0 | 帮扶村列表布尔筛选丢 false/0；登录页 label 未关联输入框；密码可见性切换不可键盘操作 |
| P2 | 8 | 2 | 6 | 机器码 menuKey 错挂（已修）、3 条路由懒加载未走 retryImport（已修）；其余为设计/一致性/性能建议 |

**验证通过、无需修复的关键项**：前后端 API 契约 524 个前端调用点 vs 826 条后端路由 **100% 匹配**（方法 + 路径），菜单单一源对齐门禁 A~E 通过，XSS 渲染点全部净化，`router.push` 裸调用 0 处，生产 sourcemap 关闭，404/403 兜底存在。

**修改文件（5 个，+108/−15）**：
1. frontend/src/views/analytics/supported-villages/List.vue
2. frontend/src/router/index.ts
3. frontend/src/views/auth/LoginEnhanced.vue
4. frontend/tests/unit/views/analytics/supported-villages/ListCov.test.ts
5. frontend/tests/unit/views/auth/LoginEnhanced.test.ts

---

## 1. P0 — 本机 vite build 失败（环境限制，非仓库缺陷；需干净 runner 复核）

### 现象
`cd frontend && npm run build`（vite 7.3.6）在本机 **2/2 次稳定失败**，均在 renderChunk 阶段：

```
vite v7.3.6 building client environment for production...
transforming...
✓ 3054 modules transformed.
✗ Build failed in 51.67s        ← 第一次
error during build:
[vite:esbuild-transpile] remove C:\Users\Administrator\AppData\Local\Temp\esbuild-62a8a10a9ef0c136e3a6e3aaed14e35fed9c1ebb28201b4a0c58e50616235620: Access is denied.
    at ...\frontend\node_modules\esbuild\lib\main.js:999:38
    at responseCallbacks.<computed> (main.js:884:9)
    at handleIncomingPacket (main.js:938:31)
    at Socket.readFromStdout (main.js:862:9)
```
第二次（45.78s）报错形态完全相同，仅临时文件名/hash 不同（esbuild-e525a0ac...）。

- 失败命令：`cd frontend && $env:CI="1"; npm run build`（等价 `npx vite build`）
- 产物状态：frontend/dist 为失败构建留下的部分产物（该目录已 gitignore，不构成仓库变更）；**需在依赖修复后重新构建**。
- 由于失败发生在 chunk 输出前，本次**无法采集** chunk 体积 / sass 弃用 / dynamic import 告警（见 §5 未完成项）。

### 最小复现（与项目代码无关）
前端依赖 esbuild **0.28.1**。esbuild JS API 对 >1MB 的 transform 输入会写系统临时文件、由 Go 侧读取后删除；本机该「新建后立即删除」被系统拒绝。

```js
// .scratch/w24-enterprise-probe/_tools/esbuild_probe.cjs
const esbuild = require('C:/military-Rural Revitalization-system/frontend/node_modules/esbuild')
const big = 'var a = 1;\n'.repeat(200000) // ≈2.2MB > 1MB 阈值（esbuild main.js:1055）
esbuild.transform(big, { loader: 'js', target: 'es2020', sourcefile: 'chunk-x.js' })
  .then(r => console.log('OK', r.code.length))
  .catch(e => { console.error('ERR', e.message); process.exit(3) })
```

结果（`node .scratch/w24-enterprise-probe/_tools/esbuild_probe.cjs`）：
- 默认（worker threads）：`ERR remove C:\Users\...\Temp\esbuild-<hex>: Access is denied.`
- `ESBUILD_WORKER_THREADS=0`：同样报错。
- 失败后遗留的 esbuild-* 临时文件随后可被正常删除（手工 `Remove-Item` 成功）。

### 排除项（为什么不是目录权限/代码问题）
- TEMP 目录可写：Node 自写自删 OK；子进程 `cmd /c del` 删除 OK；PowerShell `Remove-Item` OK（`.scratch/w24-enterprise-probe/_tools/rm_probe.cjs`）。
- 失败后遗留临时文件可删除 → 是**瞬时占用**（MsMpEng 实时扫描/安全软件句柄），不是 ACL/只读属性（Attributes=Archive，TEMP ACL 含 Administrator F）。
- 仅 esbuild 的「>1MB 输入 → 临时文件 → Go 删除」路径复现，与 Vue/项目源码无关。

### CI 影响面（Lead 决策依据）
- `.github/workflows/build-arm64.yml`（第 17-78 行）：build-frontend **runs-on: ubuntu-latest** → Linux 上 unlink 无需独占句柄，该链路**不受此 Windows 问题影响**（前提是 Lead 修复的 `@vitejs/plugin-vue` peer / `npm ci` 问题）。
- `.github/workflows/build-windows.yml`（第 105-156 行）：build-windows **runs-on: windows-2022**，第 149-156 行在 Windows runner 上 `npm ci … && npm run build` → **若该问题并非本机特有，Windows 安装包链路会同样失败，需在干净 windows-2022/本地干净 Windows 复核**。
- pr-checks / nightly-full 只跑 lint/type-check/test，不跑 vite build → 不受影响。

### 建议（不修改生产构建配置）
1. 干净 Windows runner 复核：`cd frontend && npm ci && npm run build`；若同样复现 → 视为依赖/平台缺陷（可用 `build.target='esnext'` 跳过 vite:esbuild-transpile 验证，或锁 esbuild 版本）。
2. 本机规避（仅本地）：将 `%TEMP%` 加入 Windows Defender 实时扫描排除，或换 TEMP 目录。
3. **不要**为通过构建而改 vite.config.ts 生产配置（本次未改）。

---

## 2. P1 — 已修复缺陷

### P1-1 帮扶村列表：布尔筛选为「否」（false / 0）时被静默丢弃
- **现象**：列表页「振兴梯队」开关关闭 +「三区三州/民族地区/重点帮扶县」选「否」后点搜索，后端返回**全部**数据（筛选不生效）。
- **证据（修复前）**：frontend/src/views/analytics/supported-villages/List.vue:450-453
  ```ts
  is_revitalization_tier: filters.isRevitalizationTier || undefined,  // false → undefined
  is_three_regions: filters.isThreeRegions || undefined,              // 0 → undefined
  ```
  模板取值：`:value="1"` / `:value="0"`（List.vue:35-53）、`<el-switch v-model="filters.isRevitalizationTier" />`（List.vue:31）。
  后端判定：backend/app/api/v1/supported_village.py:609-616 对每个参数 `if x is not None` → false 是有效过滤条件。
  同文件正确写法（导出链路）：List.vue:778-779 `filters.isRevitalizationTier == null ? undefined : filters.isRevitalizationTier`。
- **根因**：布尔/数值 0 过滤条件用 `|| undefined` 归一化，false/0 被吞成「未设置」。
- **修复**：List.vue:449-458，4 个字段统一改为 `== null ? undefined : value`（与导出链路口径一致）。
- **测试**：frontend/tests/unit/views/analytics/supported-villages/ListCov.test.ts:470 新增回归用例（false/0 原样透传；undefined 不传）。
- **验证**：ListCov + RecycleBin + LoginEnhanced + router-index + guards 共 5 文件 164 用例全绿（见 §4）。

### P1-2 登录页：`<label>` 与输入框无关联（可访问性）
- **现象**：账号/密码/2FA 验证码/机器码 4 个 `<label>` 是输入的兄弟节点，没有 `for`，输入框没有 `id`；读屏软件不播报字段名，点击 label 也不会聚焦输入框。
- **证据（修复前）**：frontend/src/views/auth/LoginEnhanced.vue:30/60/74/97 为 `<label>账号</label>` 形式。
- **修复**：label 增加 `for`，input 增加 `id`：LoginEnhanced.vue:30/34（login-totp-code）、61/65（login-username）、76/80（login-password）、104/108（login-machine-code）。
- **测试**：frontend/tests/unit/views/auth/LoginEnhanced.test.ts:351 断言 4 组 `label[for=...]` 与输入框存在。
- **验证**：LoginEnhanced.test.ts 58 用例全绿。

### P1-3 登录页：密码可见性切换不可键盘操作（可访问性）
- **现象**：`<span class="toggle-password" @click="...">` 仅响应鼠标点击，无法 Tab 聚焦 / 回车空格触发（纯键盘与读屏用户不可用）。
- **证据（修复前）**：LoginEnhanced.vue:84-91（span + aria-label）。
- **修复**：改为原生 `<button type="button">`（LoginEnhanced.vue:87-98），保留 `aria-label` 并动态化（显示密码/隐藏密码）+ `aria-pressed`；样式补 `border/background/padding/color: inherit` 抵消 button 默认外观（LoginEnhanced.vue:709-722）。`type="button"` 防止误触发表单提交。
- **测试**：LoginEnhanced.test.ts:351 断言 tagName=BUTTON、type=button、aria-label/aria-pressed 随点击切换。
- **验证**：同上；eslint 0 告警；硬编码色值门禁仍 305/305。

---

## 3. P2 — 已修 / 待办建议

### P2-1（已修）机器码菜单页 menuKey 错挂，菜单可见性校验旁路
- 后端单一菜单源 `system-console-security` 的 tab `machine-code` 落点是 `/admin/machine-code/management`（backend/app/api/v1/menus.py tabs 定义，dump 见 .scratch/backend_menus.json），但修复前只有 `/admin/machine-code` 带 `meta.menuKey: 'machine-code'`，真正的菜单落点路由无 menuKey → 守卫不做菜单可见性判断（roles 仍校验 admin，故非越权，属一致性缺口）。
- 修复：frontend/src/router/index.ts:711-717 给 `/admin/machine-code/management` 补 `meta.menuKey: 'machine-code'`。
- 验证：`check_menu_alignment.py` 通过（menuKey 68→69，规则 A~E 全满足）。

### P2-2（已修）3 条懒加载路由未走 retryImport（chunk 加载失败无重试）
- 全仓 122 处路由用 `retryImport(() => import(...))`，仅帮扶村 3 条用裸 `import()`：修复前 router/index.ts:178/184/190。
- 修复：统一为 retryImport（router/index.ts:178、184-185、190-192）。
- 验证：router-index.test.ts「懒加载组件均可加载（9 批）」全绿。

### P2-3（待办建议）UI v2 通用组件 6 个零引用
- `frontend/src/components/common/` 下 AppEmpty/AppError/AppLoading/AppPageHeader/AppStatCard/AppTableToolbar 6 个组件在 src 内**没有任何模板引用**（仅出现在自动生成的 components.d.ts 与自身/索引文件）；页面实际使用 el-empty / el-skeleton / 自定义 div，空态/错误态/加载态样式不统一。
- 建议：下一迭代把 6 个组件接入 1-2 个代表页面（试点）后再推广；本次不做（大范围 UI 改动，超出最小修复原则）。

### P2-4（记录，接受现状）菜单可见性守卫 fail-open
- guards.ts:89-98：菜单接口失败（`menuStore.loaded === false`）时**不阻断导航**，仅在 loaded 且 key 不在集合时 403。设计意图已注明「菜单只是可见性层，真实权限由后端接口兜底」。
- 风险：后端冷启动窗口菜单接口异常时，用户可进入本应隐藏的页面（页面内后端接口仍 403）。属已接受设计，建议保留注释与后端兜底回归测试。

### P2-5（待办建议）审计管理筛选 label 未关联
- frontend/src/views/system/AuditManagement.vue:72/81：`<label class="filter-label">用户</label>` 与相邻 el-input/el-date-picker 无 for/id 关联（同类：SupportedVillageForm.vue 162/187/203/216 为分组小标题，非输入标签，可接受）。
- 修复成本低（el-input 需 :id 绑定），但涉及该页测试；本次未改，建议后续接入 AppPageHeader/统一表单规范时一并处理。

### P2-6（待办建议）可编辑动态行使用 index 作为 v-for key
- 例：dataEntry/ComprehensiveEntry.vue:631（荣誉动态行）、dataVerify/Index.vue:56（条件行）、dataManagement/components/QualitySection.vue:111（规则行）、projects/Edit.vue:498、projects/Detail.vue:235。
- 删除中间行后可能造成输入框状态错位（Vue 复用 DOM）。只读列表用 index key 可接受；**可编辑行建议改为稳定 id**。

### P2-7（待办建议）登录背景图体积
- frontend/public/images/login-bg/ 12 张 jpg 合计 ≈3.68MB（单张 75KB~758KB），public 总体积 ≈3.86MB。离线单机可接受；建议后续转 webp/降采样（首屏只加载 1 张，非阻塞项）。

### P2-8（待办建议，轻微）项目列表恢复/彻底删除后未回第 1 页
- frontend/src/views/projects/List.vue:503/522/577/599 的 handleRestore/handlePurge/batchRestore/batchPurge 直接刷新当前页（CLAUDE.md 的分页重置规则主要针对 create/edit/delete/import；这些操作多为当前页内移除，影响小）。
- 同类：handover/Index.vue、organization/Detail.vue、UserTableCard.vue、ZeroTrust.vue 无筛选重置页码（其分页由父组件/局部数据驱动），未构成用户可见缺陷。

### 另记（文档漂移）
- CLAUDE.md 中提到的前端「`_unwrapList()` 兼容」在实际代码中不存在该符号；现为 **utils/unwrapList.ts 的 `unwrapList()`**（请求层 envelope 展开见 frontend/src/api/request.ts:285-331）。行为正确，仅文档名称漂移，建议文档后续校正（不在本次写入范围）。

---

## 4. 验证通过项（无需修复，附证据）

### 4.1 前后端 API 契约一致性：524/524 匹配（方法 + 路径）
- 方法：运行时导入后端路由表（`app.api.v1.api_v1_router`，826 条，含子包/子路由），前端静态解析 57 个 frontend/src/api/*.ts 中的全部 get/post/put/del/patch/apiRequest 调用（含模板字符串、const 拼接、查询串），路径参数统一归一化为 `{}` 后按方法比对。
- 可复现命令：
  ```
  backend/.venv/Scripts/python.exe .scratch/w24-enterprise-probe/_tools/dump_routes.py
  node .scratch/w24-enterprise-probe/_tools/contract_compare.mjs
  ```
- 输出：
  ```
  后端路由(含路径参数归一化): 826
  前端 API 调用点: 524
  匹配: 524  不匹配: 0
  ```
- 限定说明：仅校验「路径 + HTTP 方法」（不存在 404/405 类契约错误）；字段级契约另做了关键抽样（见 4.2）。
- 人工复核的 4 类动态表达式（脚本内 `applyKnownFixes` 已注释）：milestones 的 `base(projectId)`、chunkedUpload 的变量 url、secrets 的 `${qs}` 查询串、request.ts 的通用函数（已排除）。

### 4.2 响应解包假设一致
- 后端 `ok_list` / `success_response` 信封 `{code, message, success, data}`（backend/app/core/response.py:173-197、103-138）；前端响应拦截器原地展开 `data` 内层键且保留 data/success（frontend/src/api/request.ts:285-331）。
- 抽查三处曾疑似「双重解包」的页面（ZeroTrust.vue:564、UpdateLogs.vue:137、ErrorReports.vue:342 的 `res.success && res.data`）均与后端真实返回形态一致，**无缺陷**。
- `unwrapList`（utils/unwrapList.ts:22-34）兼容裸数组/items/envelope 四形态，列表页（帮扶村/经费/一户一档）抽样一致。

### 4.3 路由/菜单/权限
- `python scripts/check_menu_alignment.py` → `[OK] 前后端菜单对齐检查通过（规则 A~E 全部满足）`；6 板块 / 102 key / 83 带 path 入口 / 158 路由路径（含 alias）/ 69 menuKey。
- 守卫链完整：未登录→/login?redirect=；锁屏 fail-closed（guards.ts:19-25、61-64）；must_change_password 收口（66-71）；roles 校验（73-82）；menuKey 校验（84-99）；/undefined 参数防护（router/index.ts:912-929）。
- 116 条受保护路由中：71 条有 menuKey、30 条有 roles、82 条至少有其一；其余 34 条为详情/新建/编辑/profile 等**依赖后端数据权限**的页面（后端 detail/list 均有 get_current_user + apply_scope_filter，非管理员拿不到越权数据，见 backend/app/api/v1/supported_village.py:590 等）。本项无缺陷，作为权限面盘点记录。
- 404/403/500 兜底存在（router/index.ts:884-903、views/NotFound.vue、views/errorPage/403.vue），404 为 catch-all。

### 4.4 可靠性与安全渲染
- 未处理 Promise 拒绝兜底：utils/errorHandler.ts:436-472（取消请求/401 不弹错误、`silent` 尊重、2s 同文案去重）；`unhandledrejection` 有全局处理（main.ts:76）。
- 请求取消/去重：request.ts:191-208 仅 GET 去重、调用方 cancelToken 不被覆盖；`cancelAllRequests` 在布局/改密页使用（DefaultLayoutSafe.vue:793、ChangePassword.vue:317）。
- XSS：全仓 3 处真实 v-html（HelpCenter.vue:40/167、policies/Detail.vue:60）全部经 DOMPurify 封装（utils/sanitize.ts:86-99，含 mXSS hook），另有 1 处模板注释说明不用 v-html（TwoFactorSettings.vue:55）。
- 裸 `router.push`：0 处（3 处均已 `.catch` 或 pushSafe）；安全导航 composable 正常（useRouterSafe.ts:98/116）。
- console 泛滥：src 内 `console.log/warn/info/debug` 0 处；`console.error` 仅 3 处（App.vue:44 全局错误边界、ErrorBoundary.vue:113、schools/Analysis.vue:138 加载失败日志），合理。
- 生产构建安全项：sourcemap 生产关闭（vite.config.ts `sourcemap: !isProduction`）；terser 移除 console/debugger；public 内无 sourcemap/密钥文件（15 个文件清单见目录）；index.html `lang="zh-CN"`。

### 4.5 可访问性基础设施（已具备）
- skip-link：DefaultLayoutSafe.vue:4 + 样式 accessibility.css。
- 全局焦点环/reduced-motion/high-contrast：styles/accessibility.css。
- 对话框：全仓 `<el-dialog>` 均带 title（0 处缺失），Element Plus 默认 focus trap。
- 图片 alt：真实 `<img>` 均带 alt（多行属性扫描的 2 处误报已人工确认）。
- 空/错误/加载态角色：AppLoading role=status aria-live、AppError role=alert、AppEmpty role=status（组件存在但未接入页面，见 P2-3）。

---

## 5. 未完成 / 受限项（交接 Lead）

1. **构建告警采集未完成**：因本机 `vite build` 失败（P0），chunk 体积告警、sass 弃用警告、动态导入告警、sourcemap 泄漏均无法实测。待 Lead 修复 `@vitejs/plugin-vue` peer / node_modules 后，在干净环境执行 `cd frontend && npm run build` 采集；同时需重建 frontend/dist（当前为失败构建的部分产物，已 gitignore）。
2. **前端全量 vitest + 100% 覆盖率门禁**未由本切片执行（Lead 负责）；本切片只跑了受影响的 5 个测试文件（164 用例全绿）。新增代码分支均已由新/旧用例覆盖（新 ternary 的 null 分支由页面初始 loadData 覆盖，非 null 分支由真值用例 + 新增 false/0 用例覆盖；Login 动态 aria 两分支由点击前后断言覆盖）。
3. **eslint / vue-tsc 全量**：本切片只对 5 个改动文件跑 eslint（0 告警）并跑全量 `npx vue-tsc --noEmit`（TSC_EXIT=0，全绿）。
4. 构建/依赖修复由 Lead 并行进行（frontend/package.json、package-lock.json 为 Lead 负责，本切片未改、未跑 npm install/ci）。

---

## 6. 复现命令速查

```powershell
# 契约比对（826 路由 vs 524 调用点）
backend/.venv/Scripts/python.exe .scratch/w24-enterprise-probe/_tools/dump_routes.py
node .scratch/w24-enterprise-probe/_tools/contract_compare.mjs

# 构建失败复现（本机环境限制）
cd frontend; $env:CI="1"; npm run build
node ../.scratch/w24-enterprise-probe/_tools/esbuild_probe.cjs          # 默认 worker threads
$env:ESBUILD_WORKER_THREADS="0"; node ../.scratch/w24-enterprise-probe/_tools/esbuild_probe.cjs

# 改动验证（164 用例）
cd frontend; npx vitest run tests/unit/views/analytics/supported-villages/ListCov.test.ts `
  tests/unit/views/analytics/supported-villages/RecycleBin.test.ts `
  tests/unit/views/auth/LoginEnhanced.test.ts `
  tests/unit/router/router-index.test.ts tests/unit/router/guards.test.ts

# 静态门禁
cd frontend; npx eslint src/views/analytics/supported-villages/List.vue src/views/auth/LoginEnhanced.vue src/router/index.ts --ext .vue,.ts --max-warnings=0
cd frontend; npx vue-tsc --noEmit
python scripts/check_menu_alignment.py
python scripts/check_hardcoded_styles.py

# 菜单源快照（规则 A~E 复核用）
backend/.venv/Scripts/python.exe .scratch/w24-enterprise-probe/_tools/dump_menus.py
```

## 7. 本次自验结果汇总

| 检查 | 命令 | 结果 |
|---|---|---|
| 受影响单测 | `npx vitest run <5 files>` | **5 files / 164 tests 全绿** |
| 改动文件 eslint | `npx eslint <3 src files> --max-warnings=0` | **exit 0（0 warning）** |
| 全量类型检查 | `npx vue-tsc --noEmit` | **TSC_EXIT=0** |
| 菜单对齐门禁 | `python scripts/check_menu_alignment.py` | **OK（A~E 全满足）** |
| 硬编码色值棘轮 | `python scripts/check_hardcoded_styles.py` | **305/305（零新增）** |
| API 契约 | `node contract_compare.mjs` | **匹配 524 / 不匹配 0** |
| 生产构建 | `npm run build` ×2 | **失败（环境限制，见 P0）** |


---

## 8. 回补（2026-10-19 12:43，Lead 全量覆盖率门禁暴露的缺口）

**缺口**：全量测试 328 files / 6828 tests 全绿，但覆盖率门禁失败 `src/views/**/*.vue` lines/statements 99.99%、functions 99.89%，精确到 frontend/src/views/auth/LoginEnhanced.vue：lines/statements 99.24%、functions 86.95%（20/23），Missing lines **66, 81, 109**。

**定位**：66/81/109 = 账号/密码/机器码三个原生 input 的 `v-model` 行。原生 input 的 v-model 编译为内联 `onInput` 处理器函数；既有用例只直接给 vm 赋值（2FA 验证码用 `input.custom-input` 触发过输入），三个处理器从未被真实输入事件调用 → 3 个 functions 未计数。属本轮 LoginEnhanced.vue 安全/可访问性改造后行号映射暴露的**测试缺口**，非运行期缺陷。

**补测**：frontend/tests/unit/views/auth/LoginEnhanced.test.ts:384 新增「输入框 v-model 双向绑定：账号 / 密码 / 机器码输入都写回表单状态」，用 `setValue` 依次输入 `input#login-username` / `input#login-password` / `input#login-machine-code`（先置 showMachineCodeInput=true）并断言 vm.username/password/verificationCode 回写；保留此前 +5 条用例逻辑。

**自验**（单文件限定覆盖率，避免全量 15 分钟）：
```
cd frontend && npx vitest run tests/unit/views/auth/LoginEnhanced.test.ts --coverage --coverage.include='src/views/auth/LoginEnhanced.vue' --coverage.reporter=text
```
输出：59 tests passed；LoginEnhanced.vue **% Stmts 100 / % Branch 100 / % Funcs 100 / % Lines 100**（Uncovered Line #s 空）；`npx eslint tests/unit/views/auth/LoginEnhanced.test.ts --max-warnings=0` exit 0。

**本次改动**：仅 frontend/tests/unit/views/auth/LoginEnhanced.test.ts（+53 行）；未改 src、未改 vitest.config.ts、未加任何 ignore 注释。需 Lead 重跑全量覆盖率确认门禁转绿。
