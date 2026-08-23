---
labels: [ready-for-agent, severity-high]
blocks: ["w12-system-compliance/049-audit-capacity-governance.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 027: 审计日志导出接线与用户筛选落地

**What to build:** AuditManagement/OperationLogs 增导出按钮（json/excel/csv 三选）调 /audit/logs/export；用户筛选实现（核对后端 user_id 过滤支持，缺则补）。

**Acceptance criteria:**
- [ ] 三种格式下载成功（vitest blob 断言）
- [ ] 按用户名筛选生效（pytest user_id 链路）
- [ ] 5000 条上限提示文案
