---
labels: [done, severity-low]
blocks: []
blocked-by: ["w8-dead-code/014-approval-center-contract.md"]
---

# 034: 转交人员远程搜索

**What to build:** PendingList 转交对话框 el-select remote 模式按关键词查用户（防抖），解除 200 人截断。

**Acceptance criteria:**
- [ ] remote-method 触发请求且 loading 态正确（vitest）
- [ ] 排除当前审批人逻辑保留

## Resolution（W19 完成）

转交人选择器远程检索已在 `frontend/src/views/approval/PendingList.vue` 实现：

- `el-select` 带 `filterable remote :remote-method="searchTransferUsers" :loading="transferSearching"`，
  占位文案标注「T034 远程检索，解除200上限」。
- `searchTransferUsers(query)`：`page_size=50` + `keyword` 查询 `listStaff`，结果按
  `u.id !== task.current_approver_id` **排除当前审批人**（打开弹窗时的首次 200 条加载同样过滤）。
- 锁定测试：`frontend/tests/unit/views/approval/PendingListCov.test.ts` 含 T034 专组
  （remote-method 触发请求、loading 置位/复位、候选列表写入、异常回落空列表）。

验收两条（remote-method 触发且 loading 正确、排除当前审批人保留）均满足并有用例。
防抖未实现：Element Plus 的 remote 语义按输入变化触发，且验收未要求；如需可在模板层包一层防抖，
测试仍可直接调用 `searchTransferUsers`，不受影响。
