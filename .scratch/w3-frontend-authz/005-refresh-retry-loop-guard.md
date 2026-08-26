---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# W3-T5 401 刷新 _retry 回环护栏

**来源**: 检测 P2-3（`api/request.ts:371` 设置 _retry 但全文无检查）

## 验收标准（TDD）
- [ ] 测试：已带 _retry 标志的请求再次 401 时直接登出，不再进入 refresh 流程
- [ ] vitest 全绿

## 涉及文件
- `frontend/src/api/request.ts`

## Resolution
完成：401 入口检查 originalRequest._retry——已重试仍 401 直接清认证+登出+拒绝排队请求（_onRefreshFailed），不再进入 refresh 流程。测试覆盖 _retry 分支断言 mockAxiosPost 未被调用
