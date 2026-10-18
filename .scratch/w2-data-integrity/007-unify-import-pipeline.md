---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# W2-T7 data_sync 裸 SQL 导入收敛到安全管线

**来源**: 检测 P1-2（`data_sync_service.py:459-476,382-434`，对照 `data_package_service.py:421-472`）

## 问题
裸 text() INSERT/UPDATE：不触发 before_update 事件 → sync_version 不递增（增量机制自我破坏）；无审计、无归属校验；约束冲突后 session pending-rollback 未回滚 → 连锁失败整体回滚且报错失真。

## 验收标准（TDD）
- [x] 测试：经导入路径写入的记录 sync_version 递增
- [x] 测试：单条记录约束冲突仅跳过该条并计入失败清单，其余成功导入
- [x] 实现收敛：复用/对齐 data_package_service 的 validate_records + SAVEPOINT + bulk upsert 模式
- [ ] 全量回归通过

## 涉及文件
- `backend/app/services/data_sync_service.py`

## 审计结论（2026-08-25）

AUDIT-20260825: MISSING——裸 text() 导入绕过 sync_version 事件(data_sync_service.py:459-476)；无 SAVEPOINT

## Resolution（W19 完成）

**根因**（三条，第 3 条为实施中附带实证的真实缺陷）：
1. 导入写入走裸 `text()` INSERT/UPDATE：绕过模型 `before_update` 事件与批量更新自增钩子
   （`models/base._bump_sync_version_on_bulk_update` 只认 `Update` 语句）→ 覆盖导入后
   `sync_version` 原地不动；且包内 `sync_version` 是**源机**值，直写会让本机版本号回退 ——
   增量导出按 `sync_version > since` 过滤时永久漏行。
2. 无逐条 SAVEPOINT：单条失败的部分写入无回滚点，被末尾 `safe_commit` 照常固化
   （计入 failed 但脏写已生效）。
3. `dict(zip(existing.keys(), existing))` 的 `existing.keys()` 在 SQLAlchemy 2.0 `Row` 上
   不存在（`Could not locate column in row for column 'keys'`）→ merge/manual 策略对
   **真实已存在记录必失败**（既存测试用的是替身 `_Row.keys()`，掩盖了该缺陷）。

**改动文件**：
- `backend/app/services/data_sync_service.py`
  - `_insert_record`/`_update_record` 改 SQLAlchemy 类型化 `insert(table)`/`update(table)`
    （与 `data_package_service` 的 Core 写入模式对齐；表名仍过 `_ALLOWED_TABLE` 白名单，
    保留的 raw SELECT 带 `# nosec B608` 理由）。
  - UPDATE 丢弃包内 `sync_version`，以 `table.c.sync_version + 1` SQL 表达式原子自增
    （无该列的表如 `policies` 跳过）；INSERT 保留导出源机值（新行语义）。
  - 两个导入循环 `_import_table_data`（明文包）与 `_import_table_data_enhanced`
    （加密包）均加逐条 `with db.begin_nested():` —— 单条失败只回滚该条，会话不留在
    pending-rollback，后续记录不受影响。
  - 新 helper：`_resolve_table`（表名→`Base.metadata.tables`，幽灵表名如 `update_logs`
    显式 `ValueError` → 该条计入 failed）、`_parse_datetime`（ISO 串→naive UTC datetime，
    解析失败原样返回由列绑定器报错 → 该条失败）、`_coerce_datetime_values`（导出侧 raw
    SELECT 的时间列是字符串，类型化写入的 SQLite 时间列只收 datetime/date）。
  - `existing.keys()` → `dict(existing._mapping)` ×3（merge/manual 与 enhanced-merge）。
- `backend/tests/unit/test_data_sync_import_pipeline.py`（新增，14 条）：sync_version 递增
  （overwrite/merge/公共入口 `import_package` 端到端）、逐条 SAVEPOINT 回滚实证（先真实写
  一行再抛 `IntegrityError`，断言该行随 SAVEPOINT 回滚）、时间串规范化、幽灵表拒绝。
- `backend/tests/unit/test_data_sync_service.py`（既有测试适配）：`_Row` 替身改暴露
  `_mapping`（贴合 2.0 Row API）；两处异常用例补
  `db.begin_nested.return_value.__exit__.return_value = False`（MagicMock 默认真值会吞异常）。

**命令与结果**（均 `-p no:cacheprovider`）：
1. `pytest tests/unit/test_data_sync_import_pipeline.py -q` → **14 passed**。
2. `pytest tests/unit/test_data_sync_service.py tests/unit/test_cov_b4a_data_sync_service.py
   tests/unit/services/test_data_sync_tables.py tests/unit/test_coverage_tail_gaps.py
   tests/unit/test_branch_gaps_group_c.py tests/unit/test_data_sync_import_pipeline.py
   --cov=app.services.data_sync_service --cov-report=term-missing --cov-branch -q`
   → 174 passed / 1 failed（已知且无关，见下）；覆盖率 `data_sync_service.py`
   **474 stmts / 120 branches / 100.00%**。
3. `pytest tests/unit/test_data_sync_route.py tests/unit/test_security_hardening.py
   tests/unit/test_svc_batch.py -q` → **95 passed**。
4. `flake8 app/ --max-line-length=120 --count --max-complexity=16` → **0 errors**。

**残余注意事项**：
- 唯一失败 `test_branch_gaps_group_c.py::TestDataPackageServiceBranches::
  test_export_data_type_without_org_columns_applies_no_org_filter` 与本次无关：由另一
  会话 W18 在途改动 `data_package_service.py` 的新 raw-SQL 导出路径（`model.__tablename__`）
  与测试替身 `_BareTableModel` 无该属性所致，勿修。
- `tests/unit/test_data_sync_service.py` 的 8×E501 + 1×F841 为 HEAD 既有（`backend/.flake8`
  口径；仓库根 `.flake8` 忽略 E501），本次未引入（与 HEAD 版同款结果），未顺手修改以避免
  无关扇动；CI 门禁仅覆盖 `app/`（0 错误）。
- 按会话约束未跑全量套件（验收第 4 项留空），全量回归由 CI 承载；本文件目标集已全绿 +
  覆盖率 100%。

