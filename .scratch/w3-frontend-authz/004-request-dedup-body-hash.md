---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# W3-T4 请求去重键含请求体（防并发 POST 静默取消）

**来源**: 检测 P0-4（`api/request.ts:140-143,164-170`）

## 问题
_makeRequestKey 只含 method+url+params，不含 config.data → 同端点两个并发 POST（body 不同）key 相同，第二个发出时第一个被静默 cancel 且无提示 → 批量操作丢写入。

## 验收标准（TDD）
- [ ] 测试：仅 GET 参与去重；POST/PUT/DELETE 不再互相取消
- [ ] 测试（若保留非 GET 去重）：不同 body 的同端点请求 key 不同，均正常完成
- [ ] ERR_CANCELED 对用户可见提示或仅对 GET 生效使该路径不再触发
- [ ] vitest 全绿

## 涉及文件
- `frontend/src/api/request.ts`

## Resolution
完成（方案A）：仅幂等 GET 参与去重取消池；POST/PUT/DELETE 不注册 CancelToken、绝不互相取消，杜绝并发写被静默吞掉。requestErrorHandling/request.test 同步新契约，api+stores 79文件1284用例全绿
