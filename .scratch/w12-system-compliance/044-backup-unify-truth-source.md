---
labels: [ready-for-agent, severity-high]
blocks: ["w12-system-compliance/045-disk-space-awareness.md", "w12-system-compliance/046-wal-safe-restore.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 044: 自动备份机制统一（唯一真相源）

**What to build:** 后端 scheduler 定为唯一真相源：auto_backup 默认 true、每日 02:00、保留天数可配置默认 7；REST /system/backup/schedule 改读写 SystemConfig 真实生效；Electron 仅触发不改策略；BackupManagement 双设置卡合一如实显示下次备份时间与保留策略；docstring 谎言修正。ADR-0010。

**Acceptance criteria:**
- [ ] schedule PUT 后 scheduler 热生效（pytest monkeypatch 定时器）
- [ ] 保留 7 天清理任务单测（fake clock）
- [ ] 前端设置保存后回读一致（vitest）
- [ ] Electron main.js 删除自有清理逻辑仅保留触发
- [ ] ADR-0010 落稿
