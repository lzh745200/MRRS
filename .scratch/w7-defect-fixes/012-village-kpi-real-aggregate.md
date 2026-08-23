---
labels: [done, severity-medium]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 012: 村列表 KPI 卡片真实聚合

**What to build:** 总投入/覆盖县市/参与部门三卡改为基于全量筛选结果聚合（新增或复用统计端点），不再按当前页计算。

**Acceptance criteria:**
- [ ] 翻页不改变 KPI 数值（vitest）
- [ ] 后端聚合端点带数据权限过滤（pytest）

## Resolution（v1.10.0）
with_summary聚合端点+前端消费
