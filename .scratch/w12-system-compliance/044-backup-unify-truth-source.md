---
labels: [done, severity-high]
blocks: ["w12-system-compliance/045-disk-space-awareness.md", "w12-system-compliance/046-wal-safe-restore.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 044: 自动备份机制统一（唯一真相源）

**What to build:** 后端 scheduler 定为唯一真相源：auto_backup 默认 true、每日 02:00、保留天数可配置默认 7；REST /system/backup/schedule 改读写 SystemConfig 真实生效；Electron 仅触发不改策略；BackupManagement 双设置卡合一如实显示下次备份时间与保留策略；docstring 谎言修正。ADR-0010。

**Acceptance criteria:**
- [x] schedule PUT 后 scheduler 热生效（pytest monkeypatch 定时器）→ tests/unit/test_backup_schedule_unify.py
- [x] 保留 7 天清理任务单测（fake clock）→ TestRetentionCleanup
- [x] 前端设置保存后回读一致（vitest）→ frontend/tests/unit/composables/useBackupSchedule.test.ts
- [x] Electron main.js 删除自有清理逻辑仅保留触发（cleanupOldBackups 移除）
- [x] ADR-0010 落稿 → docs/adr/0010-backup-single-source-of-truth.md

## Resolution (v1.10.0 batch 17)

T044: 后端 scheduler 定为唯一真相源。DEFAULT_CONFIGS.auto_backup 改 true、新增 backup_retention_days=7；/schedule GET 读 SystemConfig 返回 enabled/keepCount/nextRun，PUT 经 set_config 热生效；auto_backup_job 默认开启并按保留天数 cleanup_by_retention_days 清理；Electron 仅触发（移除 cleanupOldBackups）；前端抽出 useBackupSchedule，保存后回读一致。3 pytest + 2 vitest 全绿；vue-tsc 0。
