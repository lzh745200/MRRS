---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: []
---

# T7 start.py 删库需显式环境变量

**来源**: 检测 H2（`start.py:322-333`）

## 问题
integrity_check 异常且备份恢复失败 → `os.remove(db_path)` 静默删除现库建空库。WAL 活动下可能误报，数据不可逆丢失。

## 验收标准（TDD）
- [ ] 测试：模拟 integrity_check 失败 + 无备份 → 默认**不删库**，进程退出并提示人工介入
- [ ] 测试：`ALLOW_DB_RESET=1` 时保留原删库重建路径（逃生门）
- [ ] 删库动作（无论何时发生）写审计/控制台醒目告警
- [ ] 全量回归通过

## 涉及文件
- `backend/start.py`
- `backend/tests/unit/test_start_db_guard.py`（新建）
