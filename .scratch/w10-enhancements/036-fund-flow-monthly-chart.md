---
labels: [done, severity-medium]
blocks: []
blocked-by: ["w7-defect-fixes/010-fund-status-enum-source-expand.md"]
---

# 036: 资金流入流出月度趋势图

**What to build:** Analysis.vue（或 Lifecycle 概览）新增月度流入(allocated)/流出(used)双序列面积图，数据取 multi-dimension year_month 分组既有端点，零迁移。

**Acceptance criteria:**
- [ ] 双序列渲染与图例（vitest）
- [ ] 空月份数据 data||[] 防御
- [ ] 配色走 chartColors 主题变量

## Resolution (v1.10.0 batch 10)
T036: Analysis.vue new bar chart for monthly fund flow (allocated vs used), reusing statisticsMultiDimension endpoint. 3-state loading + filter sync. TSC0 377 green.
