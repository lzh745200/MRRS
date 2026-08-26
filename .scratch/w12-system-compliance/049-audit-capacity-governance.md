---
labels: [done, severity-low]
blocks: []
blocked-by: ["w9-chain-completion/027-audit-export-userfilter.md"]
---

# 049: 审计日志容量治理

**What to build:** 不做自动清理（军规保留）；系统信息/健康页增加 audit_logs 表体积展示；提供管理员手动导出归档指引文案（复用 027 导出）。

**Acceptance criteria:**
- [ ] 体积统计端点或复用 stats（pytest）
- [ ] UI 展示条数与体积（vitest）

## 审计结论（2026-08-25）

AUDIT-20260825: 并行会话已加 recycle_retention_job(04:30)；audit_logs/api_access_logs/login_attempts 保留期仍缺

## Resolution（v1.10.0 续批7）
审计总条数卡(tooltip 含保留政策与导出归档指引)接入既有 /stats total_operations；22绿 TSC0
