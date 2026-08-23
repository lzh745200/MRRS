---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 024: 勾选导出接线 + 政策文号列与文案修正

**What to build:** 村 List 多选→导出携带 village_ids（后端参数已在）；政策列表补「文号」列；删除确认文案改为软删除语义（可在回收站恢复口径与实现一致）。

**Acceptance criteria:**
- [ ] 勾选导出请求体含 village_ids（vitest）
- [ ] 政策列表文号列渲染（vitest）
- [ ] 删除文案不再声称不可恢复
