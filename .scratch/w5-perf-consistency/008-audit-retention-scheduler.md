---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: []
---

# W5-T8 审计/日志大表保留期调度

**来源**: 检测 P1-3（backup_scheduler 8 个 job 无任何清理；audit_logs/api_access_logs/login_attempts/security_events/data_export_logs/token_blacklist 只增不减；每请求双写）

## 验收标准（TDD）
- [ ] 测试：cleanup job 删除超过保留期的行（audit_logs 180d / login_attempts 90d / api_access_logs 180d / token_blacklist 过期即删），保留期常量可配
- [ ] 接入 backup_scheduler 注册
- [ ] api_access_logs 写入改批量缓冲或降频采样（SQLite 单写者热点缓解）
- [ ] 全量回归通过

## 涉及文件
- `backend/app/services/backup_scheduler.py`、`core/audit_middleware.py`
