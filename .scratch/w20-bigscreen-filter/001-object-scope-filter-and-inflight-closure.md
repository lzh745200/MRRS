---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# 001 汇报大屏对象筛选（村/学校/单位）+ W18/W19 在途工作收口

**来源**：用户指令「实现汇报大屏不仅能看全部相关数据情况，还能针对性筛选查看某个村或者某个学校及某个单位帮扶的情况。给出务实且完整的建议方案。完成后深入检测代码，确保系统完全正常，删除无用和冗余代码。所有功能没有问题就提交GitHub并最终成功构建安装包。」

## What to build

1. **后端对象维度聚合**：`backend/app/api/v1/data/data/bigscreen.py`
   - `GET /api/v1/bigscreen/filters`：数据域内可筛选的帮扶村 / 帮扶学校 / 帮扶单位
     （单位是自由文本 facet：村 `support_unit`、校 `support_unit`、项目 `responsible_unit`、
     结对 `subject_name` 四路并集，同名合并计数）。
   - `GET /api/v1/bigscreen/overview?scope_type=all|village|school|unit&scope_id&scope_name&years`：
     KPI（固定 5 项）、经费趋势、项目状态、年度对比、经费投入排名、重点项目负责人、
     对象档案（profile）与帮扶明细（details）。
   - 数据域一律 `get_org_scope` + `filter_by_org_ids`；软删模型显式 `is_active=True`；
     村/校不存在、已软删或越权 → 404；非法维度 / 缺对象 ID / 单位名空 → 400；
     单位无匹配 → 200 空统计（不 404）。
   - 复用 `dashboard.py` 三个 `_query_*` 统计 helper，并将其年度趋势聚合抽成
     `_build_yearly_trends(db, data_scope, years)` 供 `/dashboard/yearly-trends` 与大屏共用；
     顺带修掉 `Fund.year IS NULL` 时 `int(None)` 让趋势整段降级为空的问题。
2. **前端大屏筛选**：`frontend/src/api/bigscreen.ts` + `views/bigscreen/BigScreen.vue` + `bigscreenConfig.ts`
   - 筛选条：全部 / 帮扶村 / 帮扶学校 / 帮扶单位 + 可搜索对象下拉 + 重置；
   - KPI、图表、负责人全部改由 `/bigscreen/overview` 渲染；scoped 时新增「对象档案」「帮扶明细」卡片；
   - filters 挂载仅一次、自动刷新只轮询 overview；scope 持久化到 localStorage 并在 filters 加载后校验回退；
   - 失败降级：filters/overview 失败静默降级并仅告警一次；对象已删除/越权 404 → 回退「全部」。
3. **方案文档**：`docs/design/汇报大屏对象筛选与下钻方案.md`（背景/现状/方案/口径表/API 契约/
   交互/权限/性能/验收清单/后续演进）+ 用户手册新增「汇报大屏按对象筛选」+ `docs/INDEX.md` 链接。
4. **在途工作收口（W18/W19）**：把未提交的 W18 安全/数据完整性修复与测试补齐到门禁全绿：
   数据包 PII 密文出包、跨机主键冲突业务键判定、备份/恢复健壮性、同步导入时间戳规范化、
   学校单校统计端点等；补齐 19 个测试漂移、5 个模块覆盖率缺口、
   `UserManagement.vue` 拆分组件的 vue-tsc 错误与单执行者冲突、硬编码色新增清零。

## Acceptance

- [x] 后端 `bigscreen.py` 语句/分支覆盖率 100%（44 个 API 用例）。
- [x] 200 / 400 / 404 契约与数据域隔离（admin vs 受限用户）有断言。
- [x] 前端 BigScreen 唯一执行者测试重写，目标文件四指标 100%；filters 仅一次、轮询只刷 overview。
- [x] 对象档案与帮扶明细卡片、单位覆盖名单 tags、脱敏金额、配置持久化/恢复默认/404 回退均有测试。
- [x] `vue-tsc --noEmit` 0 错误；`check_hardcoded_styles.py` 0 新增；`vue-tsc`/eslint/flake8/bandit 全绿。
- [x] 方案文档与用户手册落地并与最终代码逐条核对。
- [ ] 全量后端/前端测试与覆盖率门禁、构建 Windows 安装包（由 Lead 在提交前统一验证）。

## Resolution（待填）
