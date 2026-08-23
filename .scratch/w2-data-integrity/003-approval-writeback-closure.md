---
labels: [ready-for-agent, severity-critical]
blocks: []
blocked-by: []
---

# W2-T3 审批回写闭环 + resubmit 角色解析

**来源**: 检测 P0-4（`approval_workflow_service.py:46-59,556-560`）

## 问题
apply_entity_change 失败仅 warning：任务 APPROVED 但业务状态未变，永久不一致。resubmit 不走 _resolve_role_approver_id → role 节点指向非法 user id。

## 验收标准（TDD）
- [ ] 测试：模拟 apply 失败 → 任务标记 `approved_apply_failed`（不 commit 成功态），可查询重试
- [ ] 测试：role 型节点 resubmit 后 approver 正确解析为具体用户
- [ ] 全量回归通过

## 涉及文件
- `backend/app/services/approval_workflow_service.py`
