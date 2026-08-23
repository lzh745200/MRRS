---
labels: [ready-for-agent, severity-low]
blocks: []
blocked-by: ["w8-dead-code/014-approval-center-contract.md"]
---

# 034: 转交人员远程搜索

**What to build:** PendingList 转交对话框 el-select remote 模式按关键词查用户（防抖），解除 200 人截断。

**Acceptance criteria:**
- [ ] remote-method 触发请求且 loading 态正确（vitest）
- [ ] 排除当前审批人逻辑保留
