---
labels: [ready-for-agent, severity-low]
blocks: []
blocked-by: ["w9-chain-completion/027-audit-export-userfilter.md"]
---

# 048: 操作日志写入点补全

**What to build:** 状态流转/字段修改类事件在 FundOperationLog 补写（或详情页签改名「附件日志」二选一，倾向补写关键流转）；保证详情页操作日志 tab 非稀疏。

**Acceptance criteria:**
- [ ] approve/reject/allocate 操作产生日志（pytest）
- [ ] tab 数据非空场景 vitest

## 审计结论（2026-08-25）

AUDIT-20260825: 部分完成——rural_tasks 六端点已接入(07b5b017)；work_logs/user_permissions/files 仍缺
