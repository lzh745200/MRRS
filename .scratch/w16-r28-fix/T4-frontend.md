# T4 前端缺陷（写入范围：frontend/src/**、frontend/tests/**）
不得触碰：backend/**、electron/**、frontend/dist、resources/**。
门禁：受影响测试全绿；覆盖率 100%（含 branches）；npx vue-tsc --noEmit EXIT=0；npx eslint src --max-warnings=0 EXIT=0。

## 待修条目
- M42 views/admin/AdminDashboard.vue:286-328 —— 管理面板 5 个区域恒为空（读 /dashboard/stats 的 system_status/recent_logins/audit_logs/pending_items/storage，后端不返回）；adminStats[1]「今日活跃」实际展示 total_population → 改接真实端点（/system/monitor/snapshot、/system-health/*、/system/audit/*、/approval/tasks/pending），逐块给真实数据或明确空态。
- M43 SubordinateManagement.vue:173,204,230,253、OrgModulePolicy.vue:129,149、projects/Detail.vue:459,583,610,621 等 20+ 处 —— 错误提示走 axios 英文文案，绕过 utils/getErrorMessage.ts → 统一 getErrorMessage(e,'…失败')。
- M44 analytics/supported-villages/Detail.vue:301-325、YearlyOverview.vue:380-412 —— 趋势图串行 N 次请求 → Promise.all 或后端聚合端点。
- M45 SubordinateManagement.vue:210-223 —— 「授权/撤销」失败被 catch {} 吞掉（confirm 与请求同一 try）→ 拆两段 try/catch + 提示。
- M46 message/MessageCenter.vue:380-388 —— 标记已读失败静默且本地已改 is_read/unreadCount → 失败回滚 + 提示。
- M47 dashboard/index.vue:159、effectiveness/Rankings.vue:130、admin/MachineCode.vue:201、admin/AdminDashboard.vue:221、directives/permission.ts:37,92 —— 管理员判定硬编码原始 role → 统一 roleAccess.isAdminUser()。
- M48 api/analytics.ts:73-81 + 后端 schemas/supported_village.py:147-153 —— 钻取下发 target_dimension 后端无此字段且 extra='ignore' → 静默忽略。只改前端（后端 schema 归他人）；若必须后端改，报告给 lead 协调。
- 复核 H10（利用率趋势恒 0）已由 0d8b7b2 修，确认剩余类型谎报（api/fundStatistics.ts:39-95）是否清干净。

## 低危前端（§3）
- api/map.ts:102 getDistances 传参后端不认（死代码）
- api/analytics.ts:88 compareVillages 把 metrics join 成单串而后端要重复键
- api/analytics.ts:145-204 10 个函数无消费方（与 /dashboard/* 双源）
- api/systemMonitor.ts:51-77、api/supportedVillage.ts:180-182 死代码
- api/dataTier.ts:105 恢复时 file.name.split('_')[0] 反推模型名（含下划线模型被截断）
- funds/Detail.vue:1422 注释称并行实为串行
- sentiment/Index.vue:300 采集关键字数组含重复项

## 已知坑
- del() 只接受 1 个参数（request.ts:609），要请求头必须用 apiRequest。
- mock 作用域要匹配实现：用 mockResolvedValueOnce，不要覆盖 beforeEach 的默认实现。
- 新增 <el-dialog> 会让按序号断言的用例红（ElDialog 计数）。
- tsc 会因删掉最后一次使用报 TS6133，改调用方式后同步清理 import。

## 验收
每条：改前行为 + 改后断言；受影响测试文件全绿；新增/修改分支覆盖率 100%；vue-tsc 与 eslint 均 EXIT=0。