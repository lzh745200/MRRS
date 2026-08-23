---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: ["w2-data-integrity/004-fund-state-machine.md"]
---

# W2-T8 备份快照 WAL 一致性 + 加密流式化（低风险顺手项）

**来源**: 检测 P2-1/P2-2（`backup_service.py:385-395,157-162`、`encryption_service.py:54-66`）

## 问题
恢复前安全快照用裸 shutil.copy 不合并 WAL → 可能是不一致副本；encrypt_file/decrypt_file 整文件读入内存，多 GB 包 OOM 风险。

## 验收标准（TDD）
- [ ] 测试：_create_snapshots 使用与 _create_consistency_snapshot 相同的 Backup API 路径
- [ ] 测试：大文件加密采用分块流式（8MB chunk，与 upload-restore 对齐），内存峰值受控
- [ ] 全量回归通过

## 涉及文件
- `backend/app/services/backup_service.py`、`backend/app/services/encryption_service.py`
