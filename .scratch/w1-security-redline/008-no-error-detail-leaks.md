---
labels: [done, severity-critical]
blocks: []
blocked-by: []
---

# T8 消除 500 错误细节直出

**来源**: 检测 H-5 及全局模式（`todos.py:150-155,196,255,297,344`；`system/init.py:84-91`）

## 问题
`except Exception as e: raise HTTPException(500, detail=f"...: {str(e)}")` — 内部异常字符串（可能含 SQL 片段/表结构）直达客户端。

## 验收标准（TDD）
- [ ] 测试：构造触发异常的请求，断言 detail 不含 SQLAlchemy 异常特征字符串
- [ ] todos.py 5 处 + system/init.py 1 处改泛化消息，str(e) 仅入 logger.error
- [ ] grep `detail=f".*\{str(e)\}\|detail=f".*\{e\}"` 清点其余端点并修复同类（重点 api/v1 下）
- [ ] 全量回归通过

## 涉及文件
- `backend/app/api/v1/todos.py`
- `backend/app/api/v1/system/init.py`
- 其余 grep 命中文件
- `backend/tests/unit/api/test_no_error_detail_leak.py`（新建，参数化覆盖命中点）
