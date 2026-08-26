---
labels: [done, severity-high]
blocks: []
blocked-by: ["w1-security-redline/005-unify-auth-validation.md"]
---

# W3-T3 登出服务端吊销

**来源**: 检测 P0-3（`stores/auth.ts:107-114`；全项目无 /logout 端点调用）

## 问题
登出仅清本地缓存，服务端 token 吊销不走 → 被窃 token 自然过期前有效（记住登录 refresh 达 30 天）。

## 验收标准（TDD）
- [ ] 测试：logout() 调用后端吊销接口（携带 refresh_token），成功或失败均继续本地清理（网络失败不阻塞登出）
- [ ] 后端确认 /auth/revoke 或等价端点可被普通用户调用吊销自身 token（W1-T5 已建能力）
- [ ] 记住登录场景 e2e：登出后旧 refresh_token 刷新返回 401
- [ ] vitest 全绿

## 涉及文件
- `frontend/src/stores/auth.ts`、`frontend/src/api/auth.ts`

## Resolution
完成：logout() 先经 apiRequest POST /auth/logout 携带 refresh_token 吊销（3s 超时、失败静默不阻塞），随后本地清理照常。测试 authLogout.test.ts 2 项（吊销载荷+拒绝不阻塞）
