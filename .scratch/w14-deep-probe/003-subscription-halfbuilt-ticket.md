# 003 工单：报表订阅为"半成品"——可创建订阅，但无任何生成/送达消费方

- 状态: closed（方案 A+B 混合落地，2026-09-06，见"实现记录"）
- 波次: w14-deep-probe
- 发现: 2026-09-06 R7 契约核对 + R9 复核（2026-09-06 二次确认无消费方）
- 关单: 2026-09-06（w15 会话）

## 事实（已核实）

- 后端 `ReportSubscription` 模型 + `/reports/subscriptions` CRUD 完整。
- 前端实况（比立案时认知更早期）：仅有类型定义（types/analytics.ts），
  **无视图、无 API 客户端、无入口**。
- **全仓没有任何调度器 / 任务队列 / cron 消费 `report_subscriptions` 表**——
  订阅创建后永远不会生成或送达任何报表。
- 与"奖学金导入坏死"同类（UI 可达、运行时无效果），但性质是**功能未做完**
  而非代码写坏。

## 决策项（三选一，方向确定后实施预估均 ≤1 天）

| 方案 | 内容 | 代价/风险 |
|---|---|---|
| A. 补齐（推荐） | backup_scheduler 内新增订阅调度 job：到期的订阅调用既有 `EffectivenessService`/报表生成 → 报告文件写入用户 exports 目录 → `MessageService` 站内消息附文件名通知 | 需定义"送达"语义；生成失败要留痕 |
| B. 最小可用 | 只做手动触发生成端点 `POST /subscriptions/{id}/generate-now`（页面加"立即生成"按钮），不做定时调度 | 语义最轻，无调度风险 |
| C. 暂时收起 | 前端隐藏订阅入口 + 后端端点保留，工单挂起至产品排期 | 零后端风险，但功能对用户消失 |

## 实现记录（2026-09-06，方案 A+B 混合）

- **migration** `subscription_last_sent_001`：`report_subscriptions.last_sent_at`
  （DateTime nullable，NULL=从未生成）——同周期防重复生成的判定基准。
- **纯函数** `next_run_at(frequency, send_day, send_time, base)`：
  daily/weekly/monthly/quarterly 四频次；weekly send_day=1..7 周一..周日；
  monthly/quarterly 1..31 按月钳制（31 号在 2 月 → 28/29）；send_time 非法回落
  08:00；结果严格晚于 base。31 个确定性测试（含闰年/跨年/月末钳制边界），
  墙钟纪律遵守 CI#84 教训。
- **`subscription_dispatch_service.py`**：`generate_for_subscription`（复用
  `ReportService.export_to_excel/export_to_pdf` 带 user 数据权限 → 落盘
  `output_dir` 或运行时 `uploads/subscription_reports` → `MessageService`
  站内通知 → `last_sent_at=now`）+ `dispatch_due_subscriptions`（扫启用订阅、
  逐条 try/except、失败 rollback 不影响其余）。
- **调度挂载**：`_schedule_interval(subscription_dispatch_job, 900)`（15 分钟）。
  顺带修复 `_run_async_job` 对同步函数的 TypeError 吞错——
  **recycle_retention_job（回收站保留期清理）此前实际从未执行过**。
- **端点** `POST /reports/subscriptions/{id}/generate-now`（属主或管理员；
  禁用订阅 400）。serializer 的 `next_send_at` 由纯函数动态计算。
- **前端**：`src/api/reportSubscription.ts` API 客户端 + 独立组件
  `src/views/export/SubscriptionPanel.vue`（订阅管理卡片：列表/上次下次时间/
  启停开关/立即生成/删除确认/四频次新建表单），ReportExport.vue 以
  `<SubscriptionPanel />` 挂载并桩化（coverage-merge 不变量：面板由专属
  SubscriptionPanel.test.ts 单一执行，ReportExport.test.ts 仍是主页面唯一执行者）。
  拆分原因：订阅分支并入主页面后出现分片合并幻影（freqDetail 分支出现 3 份
  重复条目 400+/1/0，WSL/Node22 全量实测；模块加载标记确认无第二执行者，
  系单 suite 内 31 次实例挂载的 fnMap 合并错位），独立组件后门禁转绿。
- 验证：后端 138 相关测试过 + flake8 0 + bandit 0；前端 33 面板/主页测试 +
  api 客户端 7 过，vue-tsc/lint 0；WSL/Node22 全量 --coverage
  301 文件 6044 测试全过、12 组 glob 阈值全 100（EXIT 0）。

## w15 探测记录（2026-09-06）

- **R1 探针固化**：tests/probe/probe_r10_subscription.py（23 项检查），
  已注册进 run_all.py。发现并修复：ReportSubscriptionResponse schema 缺
  last_sent_at/next_send_at → 详情响应被 response_model 过滤缺键。
- **R4 回归**：run_all 全量 10 轮 287 项检查 0 失败——订阅改动零回归。
- R2 边界（越权/禁用/不存在/幂等）已由 pytest(test_subscription_generate_now.py)
  与 R1 探针双重覆盖；R3 面板 E2E 待 UI 波次（组件测试 24 用例已先行锁定）。
