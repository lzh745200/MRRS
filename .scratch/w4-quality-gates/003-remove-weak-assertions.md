---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: []
---

# W4-T3 清理弱断言与恒真断言

**来源**: 检测（`backend/tests/utils.py:7` HTTP_SUCCESS_OR_ERROR 含 500 共 30 处；root `tests/e2e/test_e2e.py:546` 恒真；`:237-245` 零断言；smoke.test.ts ~90 个 import-only）

## 验收标准
- [ ] tests/utils.py 移除 500/403 等宽松值，30 个调用点逐一改精确状态码断言
- [ ] 删除 test_e2e.py:546 恒真断言改为真实 URL 断言；快捷入口测试补真实交互断言或删除
- [ ] smoke.test.ts 合并降权为少量模块存在性测试，名额转行为测试
- [ ] 相关测试全绿

## 涉及文件
- `backend/tests/utils.py` + 30 个引用文件、根 `tests/e2e/test_e2e.py`、`frontend/tests/unit/views/smoke.test.ts`
