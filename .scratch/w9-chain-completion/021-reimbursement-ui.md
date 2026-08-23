---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: ["w7-defect-fixes/010-fund-status-enum-source-expand.md"]
---

# 021: 报销核销录入 UI（打通 transactions）

**What to build:** 经费 Detail.vue 新增「报销明细」Tab：列表/录入/删除调 transactions 三端点；剩余金额自动累计展示；预算锁定态禁录。

**Acceptance criteria:**
- [ ] 录入后 used/remaining 即时刷新（vitest）
- [ ] 删除反向扣回展示正确
- [ ] pytest：transactions 信封 ok_list 断言保持
