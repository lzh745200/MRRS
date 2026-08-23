---
labels: [ready-for-agent, severity-low]
blocks: []
blocked-by: ["w9-chain-completion/027-audit-export-userfilter.md"]
---

# 049: 审计日志容量治理

**What to build:** 不做自动清理（军规保留）；系统信息/健康页增加 audit_logs 表体积展示；提供管理员手动导出归档指引文案（复用 027 导出）。

**Acceptance criteria:**
- [ ] 体积统计端点或复用 stats（pytest）
- [ ] UI 展示条数与体积（vitest）
