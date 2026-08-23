---
labels: [ready-for-agent, severity-critical]
blocks: []
blocked-by: ["w1-security-redline/001-fix-public-reset-endpoint.md"]
---

# T5 认证收口：吊销体系闭环（ADR-0001）

**来源**: 检测 C1（`security.py:288-365`、`token_manager.py:149-160`、`admin.py:449`、`auth.py:536-538`）

## 问题
1. 主认证链 `get_current_user` → `decode_token()` **不查黑名单** → 登出/吊销形同虚设（access 8h 有效）
2. `create_access_token` 不含 `jti` → 无法进黑名单
3. logout 不递增 token_version（仅改密触发）
4. `admin.py:449` 把 session_id 当 JWT 传 revoke_token → 强制下线恒 400

## 决策（ADR-0001）
`token_manager.validate_token` 成为唯一校验出口（黑名单+类型+jti）；所有签发路径统一带 jti；登出 = 吊销当前 jti + 递增用户 token_version。

## 验收标准（TDD）
- [ ] 测试：logout 后原 access token 请求受保护端点返回 401
- [ ] 测试：管理员强制下线接口对活跃会话返回 200，目标用户后续请求 401
- [ ] 测试：refresh token 不能当 access 用（类型校验）
- [ ] 测试：改密后旧 token 失效（token_version 现状回归保护）
- [ ] 性能护栏：validate_token 的 LRU 缓存行为不回退（现有测试保持绿）
- [ ] 全量回归通过

## 涉及文件
- `backend/app/core/security.py`、`backend/app/core/token_manager.py`
- `backend/app/api/v1/auth/auth.py`、`backend/app/api/v1/system/admin.py`
- `docs/adr/0001-unified-auth-validation.md`（新建）
