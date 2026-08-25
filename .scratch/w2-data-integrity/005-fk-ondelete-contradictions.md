---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: []
---

# W2-T5 FK ondelete 与 nullable=False 矛盾修复

**来源**: 检测 P1-5（`policy.py:82-87`、`import_history.py:44-49`、`user_cascade_delete_service.py:120-127`）

## 问题
PolicyFavorite.policy_id / ImportHistory.user_id 为 SET NULL + nullable=False → 被引用记录删除必然 IntegrityError。删用户时物理 DELETE 审批记录/导入历史，销毁合规痕迹。

## 验收标准（TDD）
- [ ] 测试：删除被收藏的政策成功（收藏行级联删除或列改 nullable）
- [ ] 测试：删除用户后其导入历史保留（user_id 置空或改 RESTRICT 策略）
- [ ] 测试：删用户不再物理删除 approval_records
- [ ] 对应 alembic 迁移
- [ ] 全量回归通过

## 涉及文件
- `backend/app/models/policy.py`、`backend/app/models/import_history.py`
- `backend/app/services/user_cascade_delete_service.py`

## 审计结论（2026-08-25）

AUDIT-20260825: MISSING——PolicyFavorite/ImportHistory(+ApprovalRecord/Task) 四处 SET NULL×NOT NULL 矛盾；cascade 服务物理删除审计记录(user_cascade_delete_service.py:120-127)
