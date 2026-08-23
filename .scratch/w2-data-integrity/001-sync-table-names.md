---
labels: [ready-for-agent, severity-critical]
blocks: []
blocked-by: []
---

# W2-T1 数据同步表名错位修复（10 表静默丢失）

**来源**: 检测 P0-1（`data_sync_service.py:75-89,27-44,234-236` vs `supported_village.py:314+`）

## 问题
syncable_tables 用复数表名，真实表名单数 → 交集只有 3 张表能同步；导出空列表仅 warning 无用户可见报错。

## 验收标准（TDD）
- [ ] 测试：`syncable_tables` 的每个键都存在于 `_ALLOWED_TABLES` 且存在于真实 metadata（单一常量源生成，防再漂移）
- [ ] 测试：导出某表结果为空时抛显式错误而非静默返回 []
- [ ] 增量导出/导入端到端测试：village_income 等至少 1 张此前失效表全流程数据一致
- [ ] 全量回归通过

## 涉及文件
- `backend/app/services/data_sync_service.py`
