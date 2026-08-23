---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: ["w12-system-compliance/044-backup-unify-truth-source.md"]
---

# 045: 磁盘空间感知

**What to build:** drive_detect 扩展剩余容量探测；手动备份前目标盘 <500MB 拒绝并提示；upload-restore 前本盘预检；备份列表展示各盘剩余空间。

**Acceptance criteria:**
- [ ] 容量阈值拒绝路径 pytest（mock psutil/detect）
- [ ] 前端低空间警告 UI（vitest）
- [ ] Linux ARM64 分支 statvfs 兜底不炸
