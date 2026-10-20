# R34 方案 C 前端精细化 — 页头/图标/表格规范（frontend-probe）

- 时间：2026-10-20 09:23 ~ 09:36
- 基线：v1.15.13 工作区（Lead 已完成 92+ 文件批量规范；本切片在其基础上继续，未回滚任何改动）
- 范围：frontend/src/views（仅改 views + 2 个测试文件；未动 DefaultLayoutSafe.vue / styles / 版本 / CI / 根配置，未 commit）

## 1. 已完成

### 1.1 统一页头（19 页接入 components/common/PageHeader.vue）

| 页面 | title | 迁移内容 |
|---|---|---|
| views/consumption/List.vue | 消费帮扶台账 | 原 h2+desc+主操作(新建/导出×2) |
| views/households/List.vue | 一户一档 | 原 h2+desc+操作(预警/汇总/导出×2/新建) |
| views/organization/List.vue | 组织管理 | 原 el-card #header 内 title+筛选/导出/新增（整体上移到顶部），card 仅保留内容 |
| views/pairing/List.vue | 结对帮扶与走访台账 | 原 h2+刷新/新建 |
| views/todos/Index.vue | 待办事项 | 原 h2+desc（无操作） |
| views/work-calendar/Index.vue | 工作日历 | 原 h2+desc+添加安排 |
| views/donation/List.vue | 捐赠物资台账 | 原 h2+刷新/登记 |
| views/reminder/Index.vue | 提醒中心 | 原 h2+刷新/立即扫描 |
| views/reportTemplates/Index.vue | 报表模板管理 | 原 h2+desc+新建模板 |
| views/ruralWorks/List.vue | 乡村工作列表 | 原无页头 → 新增 |
| views/ruralWorks/Index.vue | 乡村振兴 | 原无页头 → 新增 |
| views/handover/Index.vue | 工作移交 | 原 h2+刷新 |
| views/funds/AnomalyList.vue | 经费异常监控 | 原 el-page-header → PageHeader show-back + back-to=/funds |
| views/funds/UserFundList.vue | 经费申请 | 原 h2+desc+提交申请/我的申请 |
| views/analytics/map/index.vue | 地图可视化 | 原无页头 → 新增（置于加载/错误/空态分支之前） |
| views/dataAnalysis/Index.vue | 数据统计分析 | 原 h2+desc+刷新数据 |
| views/dataManagement/Index.vue | 数据管理中心 | 原 el-card #header → PageHeader，card 保留统计 |
| views/dataVerify/Index.vue | 数据校验 | 原 h2+desc |
| views/batch/Index.vue | 批量操作 | 原 h2+desc |

全站共享 PageHeader 使用页由 12 → 31。原页面局部 header 样式类保留（无行为影响）。

### 1.2 搜索/重置按钮图标统一

- 24 文件 / 40 个按钮：搜索 28 个（含「查询」语义按钮）全部补 Search 图标；重置补 Refresh 图标共 27 个（筛选栏重置 100% 覆盖）。
- 变动文件：admin/MachineCodeManagement、approval/History、approval/MyApplications、bigscreen/BigScreen、consumption/List、dataPackage/List、dataPackage/ReceivePackage、donation/List、funds/EnhancedList、funds/UserFundList、households/List、media/PhotoArchive、pairing/List、policies/Search、projects/List、ruralWorks/Task、ruralWorks/List、schools/List、system/{AuditManagement,ErrorReports,Feedback,Role,TaskManager,UserManagement}。
- 按语义跳过 6 个非筛选栏「重置」（表单/弹窗重置）：batch/Index、export/ReportExport、import/DataImport、organization/PassCodeManagement×2、system/ZeroTrust。
- 已按需补 @element-plus/icons-vue 导入（Search/Refresh）。

### 1.3 表格规范补漏

- el-table 补 border：2 处（views/households/Detail.vue 成员表、走访表；即脚本因复杂标签跳过的两处）。复核全站 el-table 117/117 均带 border。
- 选择列 width=48：3 处（approval/PendingList、message/MessageCenter、policies/Search，原 width=55）。复核 10/10。
- 序号列 width=72：复核 25/25（无需改）。
- 操作列 fixed=right：复核 67/67（label="操作" 列全覆盖，无需改）。

### 1.4 测试同步修正（按新结构，未放宽断言）

- tests/unit/views/funds/AnomalyList.test.ts：vi.mock(vue-router) 补 useRouter；「页头返回」用例从 el-page-header emit(back) 改为点击 PageHeader .back-btn → 断言 pushSafe(/funds)。
- tests/unit/views/pairing/List.test.ts：vi.mock(vue-router) 补 useRouter（页面渲染 PageHeader 需要）。

## 2. 验证（最终态）

| 检查 | 结果 |
|---|---|
| cd frontend && npm run lint:check | exit 0 |
| npx vue-tsc --noEmit | exit 0 |
| 定向单测（覆盖全部改动页面的 45 个测试文件） | 45 files / 1325 tests 全部通过（exit 0） |
| 修改过的 2 个测试文件 eslint --max-warnings=0 | 0 |
| 图标化后逐文件 eslint | 0 |

## 3. 未完成 / 说明

- 5 个详情页仍用旧 el-page-header（不在本次 19 页清单）：funds/ContractManage、funds/Lifecycle、funds/Settlement、funds/TransferVoucher、projects/ProgressGallery。
- 6 个非筛选栏「重置」按钮未加图标（语义为表单/弹窗重置）。
- 未跑全量 vitest（按 Lead 约定）；未 commit、未改版本/CI/根配置。

## 4. 风险提示

- PageHeader 在 setup 中调用 useRouter()：后续新增页面单测若 mock vue-router，必须同时提供 useRouter（本轮已修 2 个既有测试）。
- PageHeader 引入后原页面局部 .page-header/.header-actions 样式保留但部分不再使用（无 lint/行为影响，可后续清理）。