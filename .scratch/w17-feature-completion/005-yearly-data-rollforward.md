---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# 005 年度数据滚动填报（复制上年 + 差异对比 + 批量沿用）

**来源**: 2026-10-17 用户指令「按建议逐一执行」，建议五（优先建议 5）。

**现状**: 11 类年度板块（`YearlyDataForm` / `SectionDataForm`）每年全量重填，
无「沿用上年」能力。

**What to build**
- 后端：`GET /supported-villages/{id}/yearly/{year}/prefill?from_year=` 返回上年
  数据与差异元信息（哪些字段有值、哪些为空）；批量沿用端点（一次写多板块，
  `section_keys` 白名单，事务原子）。
- 前端：年度概览/年度表单入口「从上年复制」：逐字段差异高亮（沿用/清零/重填），
  批量选择后一次提交；写入前二次确认与影响面提示。

**验收**
- [x] 沿用只写白名单字段，不覆盖本年度已有非空值（或明确二选一语义）
- [x] 无上年数据时提示且不报错；跨村不串数据（数据域）
- [x] 覆盖率与门禁全绿

## Resolution（2026-10-17，W19 完成）

**后端**
- 新建 `app/services/yearly_rollforward_service.py`：板块/字段白名单、空值口径（None/空白串/数值 0/False
  视为未填报）、三态差异（copy=可沿用 / keep=本年度已有值保留 / blank=需重填）、批量沿用、委员会成员子表沿用。
- `app/api/v1/supported_village.py` **仅追加**：
  `GET /supported-villages/{id}/yearly/{year}/prefill?from_year=`（上年数据+逐字段差异；无上年数据 200 友好提示；
  数据域与既有年度接口同口径）；`POST .../rollforward`（`section_keys` 白名单、单事务原子、
  只写业务列白名单、`overwrite` 二选一语义写进 docstring：默认只填空不覆盖）。

**前端**
- `YearlyOverview.vue` 新增「从上年复制」入口 → `YearlyRollforwardDialog.vue`（逐字段差异高亮、板块批量勾选、
  只填空/覆盖二选一、二次确认与影响面提示）；`api/supportedVillage.ts` 追加两个函数。

**验证**：后端 46 项新测试（含跨村隔离/403/404/无上年数据/只填空/overwrite/成员子表/原子回滚），
service 175 stmts/76 branches 100%、API 新增区间 0 缺失；前端 148 项相关测试、三源文件四指标 100%。
