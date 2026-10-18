---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# W5-T8 审计/日志大表保留期调度

**来源**: 检测 P1-3（backup_scheduler 8 个 job 无任何清理；audit_logs/api_access_logs/login_attempts/security_events/data_export_logs/token_blacklist 只增不减；每请求双写）

## 验收标准（TDD）
- [x] 测试：cleanup job 删除超过保留期的行（audit_logs 180d / login_attempts 90d / api_access_logs 180d / token_blacklist 过期即删），保留期常量可配
- [x] 接入 backup_scheduler 注册
- [x] api_access_logs 写入改批量缓冲或降频采样（SQLite 单写者热点缓解）——已由 H9 落地（提交 `62d6943`，`core/audit_middleware.py`），本工单仅复核，不再改动
- [x] 定向回归通过（399 用例）；全量回归由 CI `pr-checks` 承担（本会话按协调要求未起全量，另一会话在途改动不可打断）

## 涉及文件
- `backend/app/services/backup_scheduler.py`、`core/audit_middleware.py`

## Resolution（W19 完成）

### 根因

六张审计/日志表（`audit_logs`、`api_access_logs`、`login_attempts`、`security_events`、
`data_export_logs`、`token_blacklist`）此前**没有任何保留期清理**：`backup_scheduler`
只注册了备份/消息/会话/导出文件等清理，审计类大表只增不减。`api_access_logs` 在
H9（提交 `62d6943`）前还是「每请求一写」，单机长期运行下库体积、WAL 与索引维护
成本持续上升（备份/体检/迁移变慢）。`docs/R28补充验证与补漏报告-2026-10-16.md`
§12.2 曾刻意不做自动清理（保留期属合规决策）——本工单即该决策的落地，保留期
默认值由工单给定且全部可由 SystemConfig 覆盖。

### 改动

1. **新增 `backend/app/services/audit_retention_service.py`**（23 stmts / 4 branch）
   - `DEFAULT_RETENTION_DAYS`：audit_logs 180d / api_access_logs 180d /
     login_attempts 90d / security_events 365d / data_export_logs 365d
     （键同时是 SystemConfig 配置键，单一事实源）。
   - `purge_expired_audit_rows(db, retention_days, *, now=None)`：按「时间列 <
     now - days」严格早于截止点删除（恰好落在 cutoff 上的行保留），返回
     `{表名: 删除行数}`；未传键回退默认值（防漏传静默停清理）；显式 0/负数 =
     禁用该表（与 `BackupService.cleanup_by_retention_days` 同语义）；
     `token_blacklist` 只删已过期条目，`expires_at IS NULL`（永久吊销，W1 安全
     不变量）**绝不删除**；删除后显式 `safe_commit`（`get_db()` 成功路径不提交，
     漏提交会让删除静默回滚）；时间基准用 `time_utils.utcnow()`（UTC 口径）。
2. **`backend/app/services/backup_scheduler.py`**
   - 新增 `audit_log_cleanup_job()`：逐键 `get_int_config(..., getter=get_config)`
     读取保留期 → 调用清理 → 返回计数并 INFO 日志（删除总数+明细+保留期；
     无超期数据单独文案）；异常记 ERROR 且不外抛（下个周期重试）。
   - `start_backup_scheduler()` 注册 `_schedule_daily(audit_log_cleanup_job, 4, 20,
     "audit_log_cleanup")`（04:20，与 04:00/04:10/04:30 各清理任务错峰）；
     模块 docstring 与启动日志同步补充。
3. **`backend/app/services/system_config_service.py`**：`DEFAULT_CONFIGS` 新增
   上述 5 个保留期键（值/说明），管理端配置页可见、可改。
4. **`core/audit_middleware.py` 未改动**：批量缓冲 + 定量/定时/退出三重刷写已由
   H9（`62d6943`）落地并有 `test_audit_middleware_batching.py`（14 条）锁定。
5. **新增 `backend/tests/unit/test_audit_retention_w5t8.py`（11 条）**：超期删除/
   期内保留、cutoff 边界保留、配置覆盖+未传键回退、0/负数禁用、永久吊销保留、
   显式提交、默认值与配置层一致性、作业读取配置+计数日志、无超期数据分支、
   异常吞掉返回空计数、源码接线断言 + FakeTimer 启动注册断言。

### 命令与结果

```
cd backend
& ".venv\Scripts\python.exe" -m pytest tests/unit/test_audit_retention_w5t8.py -q -p no:cacheprovider
  → 11 passed
& ".venv\Scripts\python.exe" -m pytest tests/unit/test_audit_retention_w5t8.py tests/unit/test_backup_scheduler_jobs.py \
  tests/unit/test_scheduler_hardening_20260912.py tests/unit/test_coverage_gap_batch8.py \
  tests/unit/test_data_package_retention_w18.py tests/unit/test_session_lifecycle_r26.py \
  tests/unit/test_system_config_service.py tests/unit/test_system_config_api_cov.py \
  tests/unit/test_backup_single_source_of_truth.py tests/unit/test_backup_schedule_unify.py -q -p no:cacheprovider
  → 232 passed
& ".venv\Scripts\python.exe" -m pytest tests/unit/test_w18_ci_gap_fill.py tests/unit/test_export_purge_r5.py \
  tests/unit/test_audit_middleware_batching.py tests/unit/test_cov_final_audit_middleware.py \
  tests/unit/test_ratchet_gates_p1_20260913.py tests/unit/test_audit_api_cov.py \
  tests/unit/test_system_audit_api.py tests/unit/test_v1129_gap_system_audit.py -q -p no:cacheprovider
  → 167 passed
& ".venv\Scripts\python.exe" -m pytest tests/unit/test_audit_retention_w5t8.py -q -p no:cacheprovider \
  --cov=app.services.audit_retention_service --cov-report=term-missing
  → audit_retention_service.py 23 stmts / 4 branch / 100.00%（新作业体 352-391 行经
     coverage JSON 复核：missing_lines 与 missing_branches 均为空）
& ".venv\Scripts\python.exe" scripts/check_scheduler_registration.py    → total=0 NEW=0，exit 0
& ".venv\Scripts\python.exe" -m flake8 app/ --max-line-length=120 --count --max-complexity=16 → 0
& ".venv\Scripts\python.exe" scripts/security_audit.py --verbose        → Total issues: 0
& ".venv\Scripts\python.exe" scripts/check_soft_delete_usage.py         → NEW=0，exit 0
（mypy 单文件无本文件报错；bandit 单文件 exit 0）
```

### 遗留与说明

- **全量回归未在本会话执行**（协调要求：另一会话在途改动，禁止起全量后端套件）；
  定向 399 用例 + 全部相关门禁已绿，全量由 CI `backend-test` 承担。
- 首次运行可能一次性删除长期积累的存量行（单条 DELETE，非分批）；作业排在
  04:20 离线时段，单机桌面场景可接受，后续如需分批可再收敛。
- 保留期默认值（180/180/90/365/365 天）为工单给定的产品/合规决策；配置为 0
  或负数可禁用某表清理，永久吊销令牌记录不受任何配置影响（始终保留）。
- `login_attempts` 与 `security_events` 的清理不影响登录锁定判定（锁定只看近期
  失败窗口），亦不影响 `/health`、诊断摘要的逐表行数统计。
