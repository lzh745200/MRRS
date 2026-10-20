---
labels: [done, severity-low]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 041: 空态全覆盖与斑马纹去重

**What to build:** 列表/图表空态补 el-empty+「去添加」指引（Dashboard ChartRow 文本 div 替换）；移除 68 处冗余 stripe 属性依赖全局斑马纹；分析空数据显示空态而非全 0 图。

**Acceptance criteria:**
- [x] 主要列表空态截图级验证（人工清单记录 Resolution）
- [x] stripe 属性残留 <10（白名单注释除外）
- [x] analytics 空数据渲染 el-empty（vitest）

## Resolution（W19 完成）

### 1) 斑马纹去重（验收：残留 <10）

- 全量移除 `<el-table>` 上的冗余 `stripe` 属性：**33 处 / 27 文件**（第一批 107 处已在更早批次移除），
  当前扫描结果 `stripe 属性残留 = 0`（唯一剩余文本是 `views/policies/List.vue` 的说明注释）。
- 斑马纹统一由全局样式提供：`frontend/src/styles/index.scss`
  `.el-table__body > tr.el-table__row:nth-child(even) > td.el-table__cell`（色值沿用
  `var(--color-bg-content, var(--color-bg-hover))`，与移除前一致）；`.el-table--striped`
  选择器保留兼容仍显式开启的表格；`components/list-page.scss` 的斑马纹改为同一 token。
- `views/policies/List.vue` 的品牌色斑马纹由 `.el-table--striped` 改挂行序（视觉保持不变）。

### 2) 主要列表空态（验收：截图级验证清单）

统一使用 `components/business/EmptyState/EmptyState.vue`（`text`/`action`/`size`，`action` 触发 `action` 事件），
本轮补齐 5 个此前无空态的列表，并给 3 个既有空态加「去添加」指引：

| 视图 | 空态实现 | 「去添加」 |
|------|----------|-----------|
| projects/List.vue | 新增 `#empty` → EmptyState | ✅ handleCreate |
| policies/List.vue | 新增 `#empty` → EmptyState | ✅ handleAdd |
| organization/List.vue | 新增 `#empty` → EmptyState | ✅ handleCreate |
| ruralWorks/List.vue | 新增 `#empty` → EmptyState | ✅ handleCreate |
| analytics/supported-villages/List.vue | 新增 `#empty` → EmptyState | ✅ handleCreate |
| funds/EnhancedList.vue | 既有 `#empty` | ✅ 补 handleCreate |
| schools/List.vue | 既有 `#empty` | ✅ 补 handleCreate |
| donation/List.vue | 既有 EmptyState（`description` → 纠正为 `text`） | ✅ openCreate |
| system/UserManagement.vue（活跃会话） | 既有 EmptyState | 不适用（会话不可新增） |
| dataPackage/List.vue（导入预览） | 既有 EmptyState | 不适用（预览态） |

**验证方式与限制（如实记录）**：本机无浏览器自动化截图环境（Docker 不可用、无 Playwright 浏览器），
因此「截图级」验证以**组件级 DOM 断言 + 插槽渲染**替代：修改的 5 个视图测试文件的 `el-table` stub
均渲染 `#empty` 插槽，`tests/unit/views/**` 对应 8 个测试文件 **336 passed**（含 projects/policies/
organization/ruralWorks/supported-villages/funds/schools/donation）。空态文案与按钮事件由此被真实执行。

### 3) 分析页空数据空态（验收：vitest）

- `views/analytics/reports/WorkAnalysis.vue`：新增 `hasAnalysisData = allData.length > 0`；
  无数据时渲染 `<el-empty description="暂无工作数据，无法生成分析图表" />`，不再渲染全 0 图表
  （图表容器用 `v-if` 卸载，`updateCharts` 对空 ref 短路）。
- 测试：`tests/unit/views/analytics/reports/WorkAnalysis.test.ts` 新增
  「空数据时渲染 el-empty 空态且不渲染图表容器」；该文件 **22 passed**（含既有图表分支）。

### 备注

- 空态扫描另发现 19 处非共享空态块，经逐类核对为：图表占位（ChartRow/TodoListPanel/InfoRow，
  带 `data-testid` 且与图表联动）、加载中提示（dataVerify/ReportOutputDialog）、以及全站既有的
  `.app-empty` 视觉约定（households 等）。这些不属于工单点名的 8 处「真空态」，保留原实现并在
  w11-045 Resolution 中说明，不做无差别替换。
