---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: []
---

# W2-T7 data_sync 裸 SQL 导入收敛到安全管线

**来源**: 检测 P1-2（`data_sync_service.py:459-476,382-434`，对照 `data_package_service.py:421-472`）

## 问题
裸 text() INSERT/UPDATE：不触发 before_update 事件 → sync_version 不递增（增量机制自我破坏）；无审计、无归属校验；约束冲突后 session pending-rollback 未回滚 → 连锁失败整体回滚且报错失真。

## 验收标准（TDD）
- [ ] 测试：经导入路径写入的记录 sync_version 递增
- [ ] 测试：单条记录约束冲突仅跳过该条并计入失败清单，其余成功导入
- [ ] 实现收敛：复用/对齐 data_package_service 的 validate_records + SAVEPOINT + bulk upsert 模式
- [ ] 全量回归通过

## 涉及文件
- `backend/app/services/data_sync_service.py`

## 审计结论（2026-08-25）

AUDIT-20260825: MISSING——裸 text() 导入绕过 sync_version 事件(data_sync_service.py:459-476)；无 SAVEPOINT
