---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# W11-T45 UI 精美化批量清扫（Phase 6 遗余，2026-08-30 交接）

**背景**: 2026-08-30 全面体检后的 UI 精美化阶段完成了范围重估，以下为经实测修正后的
剩余工作清单（原估值里"28 处手写空状态"经逐例核对多数是图表兜底数据/字段占位文本，
非真正空态 UI，已从清单剔除）。

## 待办清单（按优先级）

1. **PageHeader 标准件推广**：58 个视图手写 `class="page-header..."`（grep 可列出）。
   标准契约为 `src/components/common/PageHeader.vue`（title/subtitle/showBack/slots），
   标准范例见 `views/funds/EnhancedList.vue:5`、`views/projects/List.vue:5`、
   `views/system/UserManagement.vue:4`。逐视图替换并核对返回按钮/操作区迁移到
   `#extra` slot；删除 `views/dashboard/PageHeader.vue` 重名组件（dashboard/index.vue:151
   引用改用共享件）。
2. **图表引擎统一**：`views/analytics/reports/WorkAnalysis.vue:186` 与
   `views/ruralWorks/Analysis.vue:303` 仍在用 chart.js → 移植到 BaseChart/echarts
   （仓库其余图表已全部 echarts），随后 `package.json` 删除 chart.js 依赖
   （构建产物将少一个 192KB 懒加载块）。
   **侦察数据（2026-08-31 实测）**：chart.js 使用点共 10 个 Chart 实例——
   `views/analytics/reports/WorkAnalysis.vue`（798 行）：import :186；实例 :371/:408/:463（类型/状态/趋势）。
   `views/ruralWorks/Analysis.vue`（1529 行）：import :303；实例 :611/:653/:692/:739/:801/:869/:909
   （饼/柱/环/条/趋势/村排名/质量分析）。移植注意：均用 `Chart from 'chart.js/auto'`，
   数据源为组件内聚合函数，echarts 侧走 BaseChart.vue 统一主题；两视图各自在
   onUnmounted 有 destroy 逻辑需同步移除。package.json 移除 chart.js 后构建产物
   预计减少 ~192KB 懒加载块。

3. **仪表盘图表颜色令牌化**：`views/analytics/dashboard/Dashboard.vue`（32 处 hex 在
   echarts option 中，含轴色 #e2e8f0/#1e293b/#64748b——暗色主题下刺眼）、
   `views/dashboard/ChartRow.vue`(16)、`views/ruralWorks/Analysis.vue`(24)、
   `views/bigscreen/BigScreen.vue`(16)、`views/schools/List.vue`(17)。
   做法：调色板用 `@/utils/echarts-theme` 的 COLOR_PALETTE/MILITARY_BLUE 等常量；
   轴/边框色读取 CSS 变量（getComputedStyle 或 echarts 注册主题时注入当前主题值）。
4. **表格 stripe 约定统一**：90 张真实 el-table 中 40 张带 stripe，定一种约定全站落地。
5. **内联样式清理（Top）**：`views/funds/Detail.vue`(33)、`views/reportTemplates/Index.vue`(18)、
   `views/system/UserManagement.vue`(16)、`views/system/DataTier.vue`(15)。
6. **formatXxx 收敛**：71 个重复日期/格式化函数定义 → `@/utils` 统一导出
   （`views/funds/Detail.vue` 4 个最优先；纯机械但面广，建议脚本辅助+抽测）。
7. **空状态**：真正需要统一的仅约 8 处（system/ZeroTrust.vue:154,173、
   system/ErrorReports.vue:64,84、analytics/supported-villages/YearlyOverview.vue:49 等）
   → 换共享 `components/business/EmptyState/EmptyState.vue`。
8. **双通知系统**：868 处 ElMessage vs `utils/notify.ts`（仅 errorHandler 在用）——
   写一页使用规范（轻提示=ElMessage，重要事件=notify），或 notify 并入统一出口。

## 约束
- 每改一批跑 `npx vue-tsc --noEmit` + 相关 vitest；页面改动按 COORDINATION.md §3.5
  同步更新对应 .test.ts。
- auth 页面（Login/Register/ForgotPassword）归安全会话，改动前先对表
  `docs/agents/issue-tracker.md` 与 COORDINATION.md 分权表。
- 完成后用渲染截图做视觉验收（judge），逐页通过为准。

## Resolution（W19 完成）

### 1. PageHeader 标准件推广 —— 已交付

**页头迁移 37 个视图**（本轮起点 47 个手写 `class="page-header..."`；剩余 10 个见文末「判定不适用」与「未覆盖/边界说明」）。
按目录列出（`frontend/src/views/` 相对路径）：

- `ai/InteractiveResult.vue`
- `approval/Overview.vue`、`approval/MyApplications.vue`
- `analytics/Assessment.vue`、`analytics/map/MapVisualization.vue`、`analytics/reports/WorkAnalysis.vue`、
  `analytics/supported-villages/Detail.vue`、`analytics/supported-villages/YearlyOverview.vue`
- `dataEntry/ComprehensiveEntry.vue`
- `dataVerify/components/RulesPanel.vue`
- `dataSync/Export.vue`、`dataSync/Import.vue`
- `dataPackage/ReportPackage.vue`、`dataPackage/ReceivePackage.vue`
- `effectiveness/Evaluation.vue`、`effectiveness/Rankings.vue`
- `export/ReportExport.vue`
- `funds/Budget.vue`
- `households/Detail.vue`
- `import/DataImport.vue`
- `media/PhotoArchive.vue`
- `projects/Edit.vue`
- `system/AuditManagement.vue`、`system/ChunkedUploadManager.vue`、`system/ConfigPackage.vue`、
  `system/DataTier.vue`、`system/EncryptionSettings.vue`、`system/EnvCheck.vue`、`system/ErrorReports.vue`、
  `system/MapTileManager.vue`、`system/MonitoringDashboard.vue`、`system/PermissionPacks.vue`、
  `system/SecretsManagement.vue`、`system/SettingsOverview.vue`、`system/TaskManager.vue`、
  `system/UpdateLogs.vue`、`system/ZeroTrust.vue`

统一手法：

- 标题/副标题 → `title` / `subtitle`；右侧操作区 → `#extra`，**保持原按钮顺序、`@click`、`v-if`、`data-testid`**
  （如 `media/PhotoArchive.vue` 的 `photo-upload`/`upload-btn`/`refresh-btn`）。
- 详情/子页返回按钮 → `show-back` + `back-to`（`funds/Budget`→`/funds`、`households/Detail`→`/households`、
  `supported-villages/Detail`→`/supported-villages`、`YearlyOverview`→`/supported-villages/:id`）；
  原可断言的容器 class 保留在插槽内（`.header-actions`、`.header-right`、`.btn-refresh`）。
- `analytics/reports/WorkAnalysis.vue` 原 `<h1>` 页头 → `:level="1"`，保留页面唯一一级标题语义。
- `system/TaskManager.vue` 的「运行中」徽标 → `#title` 插槽，与标题同排保留。
- 重名组件 `views/dashboard/PageHeader.vue` 已删除，`views/dashboard/index.vue:151` 已改用共享件（本批复核通过）。
- 顺带收敛触碰到的内联样式：`funds/Budget.vue` 年份选择器 → `.year-select`；`ReceivePackage.vue` 页头
  内联 `display:flex` → 共享件布局。

**受影响测试同步（5 个，仅选择器/路由 mock 适配，断言意图不变）**：

| 文件 | 调整 |
|------|------|
| `tests/unit/views/analytics/supported-villages/Detail.test.ts` | `vue-router` mock 补 `useRouter`；`vm.handleBack()` → 点击共享件 `.back-btn`，断言同一 `pushSafe('/supported-villages')` |
| `tests/unit/views/analytics/supported-villages/yearly-overview-cov.test.ts` | 同上，改为点击 `.back-btn` 断言 `/supported-villages/1` |
| `tests/unit/views/funds/Budget.test.ts` | 按文案找「返回经费管理」按钮 → `.back-btn`，断言 `/funds` |
| `tests/unit/views/households/Detail.test.ts` | `.btn-back` → `.back-btn`、mock 补 `useRouter`，断言 `/households` |
| `tests/unit/views/projects/Edit.test.ts` | mock 补 `useRouter` |

覆盖率单执行者不变量：**未新增任何对目标视图的测试引用**（逐文件 `grep "@/views/<path>.vue"`
确认执行者数量不变；`smoke`/`SystemViewsBatch`/`SystemConsole`/`FundsViewsBatch`/`router-index`
等既有执行者只做复跑）。

**命令与结果**：

- `npx vue-tsc --noEmit` → 本批 38 个改动文件 **0 报错**。仓库仍有并行会话在改的
  `funds/Detail.vue`、`system/UserManagement.vue`、`dashboard/ChartRow.vue`、`schools/List.vue`、
  `system/components/UserFormDialog.vue` 共 6 条既有 TS 报错（非本批引入）。
- `npx eslint <38 个改动视图> --max-warnings=0` → **0 error / 0 warning**；改动的
  `Detail.test.ts` / `households/Detail.test.ts` / `projects/Edit.test.ts` 亦为 0 warning
  （`yearly-overview-cov.test.ts`、`Budget.test.ts` 存在**本批之前就有**的 prettier/unused 警告，
  均不在本批改动行，未顺手改动以避免无关 diff）。
- `npx vitest run <目标测试>` → 全部通过，无失败用例。分批结果：
  `reportTemplates/Index + system/DataTier` 85；approval/analytics/effectiveness 等 7 文件 143；
  ai/dataPackage/media/import/system 等 8 文件 237；WorkAnalysis/Detail/YearlyOverview/dataSync
  7 文件 118 + Detail 复跑 46；Funds/households/projects/system 7 文件 135 + 两处修复复跑 60；
  system 安全组 200；16 文件组 432；`smoke` 117；`SystemViewsBatch/SystemConsole/FundsViewsBatch/
  dataVerify Index` 62；`router-index` 20。

### 2. 内联样式清理 —— 已交付

- `frontend/src/views/reportTemplates/Index.vue`：**16 处 `style="..."` → 0**，改为 scoped class：
  `.full-width` / `.dialog-alert` / `.module-cell` / `.field-tag` / `.upload-block` / `.upload-tip` /
  `.section-gap` / `.section-gap-top` / `.block-gap-sm` / `.block-gap-top` /
  `.preview-heading`（含 `.is-danger`）/ `.text-danger`。同步删除已无模板引用的
  `.page-header` / `.page-title` / `.page-desc`。
- `frontend/src/views/system/DataTier.vue`：**10 处静态 `style="..."` → scoped class**
  （`.full-width` / `.result-alert` / `.cleanup-age-input`）；**6 处进度条宽度改为 CSS 变量**
  `:style="{ '--bar-percent': … }"` + `.bar-fill { width: var(--bar-percent, 0%) }`，保留原
  `transition: width .6s` 与 `min-width: 4px`；页头一并迁移为 `PageHeader` 并删除 `.page-header` 样式。
- 结果：两文件 `grep 'style='` 分别为 **0** / **6**；后者仅剩数据驱动的 CSS 变量绑定，无布局常量。
  原值一一对应（16px/12px/8px/4px、160px、100%、`inline-flex`+4px gap 等），未改业务逻辑。
- 验证：`npx eslint src/views/reportTemplates/Index.vue src/views/system/DataTier.vue --max-warnings=0`
  → 0 error / 0 warning；`vitest run tests/unit/views/reportTemplates/Index.test.ts
  tests/unit/views/system/DataTier.test.ts` → 85 passed；
  `backend/.venv/Scripts/python.exe scripts/check_hardcoded_styles.py --files <触碰视图>`
  → 无新增硬编码颜色（存量减少，退出码 0）。

### 已在此前完成（证据，本批未重复改动）

- **图表引擎统一**：`frontend/package.json` 已无 `chart.js`；`frontend/src` 无 `from 'chart.js'` 引用；
  `analytics/reports/WorkAnalysis.vue` 与 `ruralWorks/Analysis.vue` 均走 `BaseChart`/echarts。
- **表格 stripe 全量移除**：`grep stripe frontend/src/views` 仅命中 `policies/List.vue` 一条说明性
  CSS 注释，无任何 `stripe` 属性。
- **图表颜色令牌化**：`analytics/dashboard/Dashboard.vue`、`dashboard/ChartRow.vue`、
  `bigscreen/BigScreen.vue`、`ruralWorks/Analysis.vue`、`schools/List.vue` 均引入
  `@/utils/echarts-theme`（`COLOR_PALETTE`/`MILITARY_BLUE`/`themeColor`）或 `@/utils/chartColors`。
- **通知规范**：`docs/design/ui-notification-guideline.md` 存在。
- **空态统一**：47 个视图引用 `EmptyState`。

### 判定不适用（逐文件 + 原因）

- `views/system/Menu.vue`：页头位于 `el-card` 的 `#header` 槽内（`<span class="page-title">` + 菜单数
  `el-tag`），属**卡片标题**而非页面标题区；套用共享件会引入 h2 与卡片标题的嵌套层级与多余 margin。
- `views/auth/Profile.vue`、`views/auth/ChangePassword.vue`、`views/auth/TwoFactorSettings.vue`：
  位于 `views/auth/**`，按工单「auth 页面归安全会话」的分权约束不在本批处理；且三者均为
  `el-card` 包裹的账号表单页，不是标准 T1/T2 页头形态。
- `views/analytics/map/MapVisualization.vue`：已迁移，但该文件当前无路由引用
  （`/data-analysis/map` 指向 `analytics/map/index.vue`）、也无测试执行者，属历史死代码；
  迁移只为消除手写页头，不影响运行产物。

### 未覆盖/边界说明

- 受并行会话保护、本批**未改动**：`views/analytics/dashboard/Dashboard.vue`、`views/funds/Detail.vue`、
  `views/ruralWorks/Analysis.vue`、`views/schools/{Detail,Scholarship,Projects}.vue`、
  `views/system/UserManagement.vue`。
- 无同名测试、按约定跳过：`views/system/SettingsOverview.vue`（仅被 `SystemConsole.test.ts` 以
  mock 形式引用，从不执行真实组件）、`views/analytics/map/MapVisualization.vue`（无测试）。
- 为控制 diff，各视图 scoped 样式中已无模板引用的 `.page-header`/`.page-title`/`.page-desc`
  死规则**未逐条删除**（不影响渲染，后续样式重构可统一清理）；本轮已在触碰样式的
  `reportTemplates/Index.vue`、`system/DataTier.vue`、`funds/Budget.vue`、`WorkAnalysis.vue` 内删除。
- 迁移计数：**页头迁移 37 个视图**；另有 `reportTemplates/Index.vue`（此前已用共享件）本批仅做
  内联样式清理，合计改动 38 个视图文件 + 5 个测试文件。

