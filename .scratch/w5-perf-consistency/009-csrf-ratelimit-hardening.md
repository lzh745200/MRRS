---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: []
---

# W5-T9 CSRF 验签 + 过期校验 + 限流器修复

**来源**: 检测 H7/H6（`csrf_middleware.py:131-164` 只比对不验签、CSRF_TOKEN_EXPIRY 无校验；`security.py:507-513` 位置参数陷阱、`_cleanup_expired_rate_keys` 固定 300s vs window=3600；`get_client_ip` 盲信 XFF）

## 验收标准（TDD）
- [ ] 测试：伪造 csrftoken cookie+header（无签名）被拒
- [ ] 测试：过期 CSRF token 被拒
- [ ] 测试：window=3600 的限流键 6 分钟后仍受限（清理窗口修复）
- [ ] check_rate_limit 签名收紧为仅关键字参数，全仓调用点排查
- [ ] get_client_ip 可配置信任代理列表（默认直连模式不读 XFF）
- [ ] 全量回归通过

## 涉及文件
- `backend/app/middleware/csrf_middleware.py`、`backend/app/core/security.py`、`machine_code.py:377` 调用点（W1-T1 已修的保持一致）
