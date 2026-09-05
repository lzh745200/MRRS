---
labels: [ready-for-agent, severity-medium]
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
