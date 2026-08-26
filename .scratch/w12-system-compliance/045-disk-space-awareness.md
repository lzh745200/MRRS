---
labels: [done, severity-medium]
blocks: []
blocked-by: ["w12-system-compliance/044-backup-unify-truth-source.md"]
---

# 045: 磁盘空间感知

**What to build:** drive_detect 扩展剩余容量探测；手动备份前目标盘 <500MB 拒绝并提示；upload-restore 前本盘预检；备份列表展示各盘剩余空间。

**Acceptance criteria:**
- [ ] 容量阈值拒绝路径 pytest（mock psutil/detect）
- [ ] 前端低空间警告 UI（vitest）
- [ ] Linux ARM64 分支 statvfs 兜底不炸

## Resolution
- backend/app/utils/disk_space.py: 新增 get_disk_free_bytes（psutil→statvfs→shutil 三路探测，
  Linux ARM64 兜底不炸）+ has_enough_free_space 阈值判定
- app/core/database.check_disk_space: 增加可选 path 参数（默认数据库目录，向后兼容）
- backup_service: BACKUP_MIN_FREE_MB=500 阈值；_ensure_disk_space 手动备份/恢复前预检；
  get_disk_space_info 聚合备份目录/数据库目录剩余空间并纳入 get_backup_statistics
- system/backup.py upload-restore: 本盘 <500MB 预检（409 拒绝，避免写出损坏文件）
- BackupManagement.vue: 低空间 el-alert 警告（diskSpaceWarning computed）
- 测试: 10 后端用例（探测三路/阈值/create拒绝/信息聚合/upload 409）+ 2 前端用例（警告显隐）
- 注: 044（备份真相源/调度器）为独立工单，本工单仅实现磁盘空间感知部分
