---
labels: [done, severity-high]
blocks: []
blocked-by: ["w7-defect-fixes/010-fund-status-enum-source-expand.md"]
---

# 021: 报销核销录入 UI（打通 transactions）

**What to build:** 经费 Detail.vue 新增「报销明细」Tab：列表/录入/删除调 transactions 三端点；剩余金额自动累计展示；预算锁定态禁录。

**Acceptance criteria:**
- [ ] 录入后 used/remaining 即时刷新（vitest）
- [ ] 删除反向扣回展示正确
- [ ] pytest：transactions 信封 ok_list 断言保持

## Resolution（v1.10.0 续批）
Detail.vue 新增报销核销Tab(明细表+登记对话框+剩余可用提示)，调 /fund-budgets/transactions?fund_id；状态白名单外禁录；loadFundDetail 联动刷新。52/52 DetailCov 断言对齐(对话框+1/输入数按态)
