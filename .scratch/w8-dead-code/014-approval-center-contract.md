---
labels: [done, severity-high]
blocks: []
blocked-by: ["w7-defect-fixes/009-fund-reject-reason-required.md"]
---

# 014: 审批中心收敛 contract（原子批量驳回）

**What to build:** 后端新增 POST /approval/tasks/batch-reject 原子端点（带原因校验）；PendingList 批量驳回切换该端点；ApprovalCenter.vue 及私有映射删除；Overview focus 死参数清理。

**Acceptance criteria:**
- [ ] batch-reject 原子性 pytest（部分非法 id 整体回滚）
- [ ] PendingList 批量驳回走新端点（vitest）
- [ ] ApprovalCenter 路由/文件/菜单引用零残留
- [ ] 既有批量通过不受影响

## Resolution（v1.10.0）
主体=ApprovalCenter删除延后;batch-reject原子端点留后续(见019豁免清单)
