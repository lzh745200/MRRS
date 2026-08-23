---
labels: [ready-for-agent, severity-high]
blocks: ["w13-docs-release/053-version-build-deliver.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 046: WAL 安全恢复与回退分支修复

**What to build:** _restore_database_from_backup 覆盖前 checkpoint/删除 -wal/-shm；create_backup 的 shutil.copy 回退分支标记危险并优先 sqlite backup API 重试；upload-restore 校验兼容 WAL 库。

**Acceptance criteria:**
- [ ] 恢复后打开库 PRAGMA integrity_check 通过（pytest 临时库实测）
- [ ] 残留 wal 场景模拟恢复不损坏
- [ ] 备份创建回退分支日志告警断言
