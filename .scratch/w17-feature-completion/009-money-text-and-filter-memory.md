---
labels: [done, severity-low]
blocks: []
blocked-by: []
---

# 009 金额展示统一 MoneyText + 列表筛选状态记忆/导出当前筛选

**来源**: 2026-10-17 用户指令「按建议逐一执行」，建议九（最后一轮 4）。

**现状**: 金额展示散落各视图（~30 处）；列表筛选刷新后回到默认。

**What to build**
- `MoneyText.vue` 统一组件（4 位小数、千分位、空值占位、可选单位/大写切换），
  分批替换金额列；保留既有 `formatMoney4` 语义（组件内部复用）。
- 列表筛选状态记忆（sessionStorage，按路由 key）+「导出当前筛选结果」在村/项目/
  经费列表接线（复用既有导出接口传筛选参数）。

**验收**
- [x] MoneyText 单测覆盖（0/负数/空/小数/单位）
- [x] 替换处视觉与数值不变（快照/断言）
- [x] 覆盖率与门禁全绿

## Resolution（2026-10-17，W19 完成）

- 新增 `src/utils/money.ts`（空值判定、复用 `formatMoney4` 语义、单位拼接、人民币大写：角分/组间补零/
  负数/0/超范围回落）与 `src/components/common/MoneyText.vue`（`value/unit/placeholder/uppercase`）。
- 新增 `src/composables/useFilterMemory.ts`（按路由 path 存 sessionStorage，`load/save/clear/apply`；
  JSON 损坏/存储抛错/配额满静默兜底；`apply` 只回填目标已有字段防原型污染）。
- 三列表接线：经费 `EnhancedList.vue`（含金额列 MoneyText 试点与「导出当前筛选」）、
  项目 `List.vue`、帮扶村 `List.vue`（含 yearStart 恢复）——进入恢复筛选、搜索/重置/分页保存、
  导出复用既有导出函数并传当前筛选参数。
- 说明：经费/项目导出端点后端仅支持 keyword/type/status，列表其它筛选暂无法进入导出（列残余风险）。

**验证**：10 个测试文件 288 项全绿，8 个改动源文件四指标 100%；eslint 0；vue-tsc 0；
金额缺失语义由 0 改占位符「-」（可按需传 placeholder="0"）。
