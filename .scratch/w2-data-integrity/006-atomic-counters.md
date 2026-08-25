---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# W2-T6 计数器读改写竞态原子化

**来源**: 检测 P1-6（`policy.py:994-995,1235-1236`、`policy_service.py:249-250`、`auth.py:82`）

## 问题
view_count/download_count/failed_login_count 用 Python 读加一再写回，WAL 下并发丢更新。

## 验收标准（TDD）
- [ ] 测试：并发 20 次 view 递增后计数=20（UPDATE x=x+1 原子化）
- [ ] failed_login_count 同样修复
- [ ] 全量回归通过

## 涉及文件
- `backend/app/api/v1/policy.py`、`backend/app/services/policy_service.py`、`backend/app/api/v1/auth/auth.py`

## Resolution（2026-08-25）

6148cbf0：policy 计数与登录锁定改 COALESCE/CASE/RETURNING 原子 UPDATE
