---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 005: 帮扶村列表年份筛选复活

**What to build:** List.vue loadData 将 yearStart 传入 API；后端 /filter-options 返回 years 集合供下拉。

**Acceptance criteria:**
- [ ] 选择年份后请求携带参数且结果过滤（vitest+pytest 各一）
- [ ] 年份下拉有真实数据源非空
