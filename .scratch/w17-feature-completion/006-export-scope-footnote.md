---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# 006 导出物口径脚注（数据截止/范围/是否含软删/生成人）

**来源**: 2026-10-17 用户指令「按建议逐一执行」，建议六（最后一公里 1）。

**现状**: 各类导出（Excel/PDF/Word/综合报告）无统一口径说明，汇报口径靠口头解释。

**What to build**
- 统一生成「口径脚注」块（数据截止时间 UTC→本地、过滤条件、是否含软删、
  范围层级/组织、生成人、生成时间），挂到既有导出的页眉/页脚或表尾。
- 落点：`report_export_service` / `export_service` / `supported_village_export_service`
  的公共出口（先做公共注入函数，再逐出口接线）。

**验收**
- [x] 至少覆盖村/学校/项目/经费/综合报告五类导出
- [x] 脚注含软删排除说明；无过滤条件时不输出空字段（保持整洁）
- [x] 现有导出测试更新后全绿；覆盖率门禁全绿

## Resolution（2026-10-17，W19 完成）

- `export_service.py` 新增唯一实现：`build_scope_footnote`（数据截止 UTC→本地 / 过滤条件 / 软删 /
  数据范围 / 生成人 / 生成时间，空字段自动省略）、`format_scope_footnote`（单行「口径说明：…」）、
  `apply_scope_footnote`（Excel 表尾灰字合并行）、`describe_data_scope`、`exporter_from_watermark`。
- 接线五类导出：村 / 学校 / 项目 / 经费列表 + 综合报表（每个 sheet）；`report_export_service` 的 Word/PDF
  文末脚注；`supported_village_export_service` 的 xlsx 各 sheet 与 CSV 尾部「# 口径说明」。
- 生成人从既有审计水印「导出人：X」解析；范围走 `data_permission` 口径。

**验证**：`test_export_footnote.py` 42 项；五类导出既有测试适配后全绿；新增行覆盖 100%。
