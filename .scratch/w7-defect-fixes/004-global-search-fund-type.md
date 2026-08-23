---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 004: 全局搜索找回资金结果

**What to build:** search.ts 类型联合、SEARCH_TYPE_LABELS、GlobalSearch iconMap/typeOrder 补 fund；placeholder 文案补资金与用户说明。

**Acceptance criteria:**
- [ ] fund 结果在搜索下拉按分组渲染（vitest）
- [ ] typeOrder 包含 fund
- [ ] placeholder 与实际支持实体一致
