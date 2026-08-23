---
labels: [done, severity-high]
blocks: ["w8-dead-code/014-approval-center-contract.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 009: 经费驳回原因必填（前+后端）

**What to build:** Detail.vue 工作流弹窗驳回时意见必填校验；后端 reject 端点接收 opinion 并写入审批留痕。

**Acceptance criteria:**
- [ ] 前端空意见提交被拦截并提示（vitest）
- [ ] 后端 reject 带 opinion 落库可查询（pytest）
- [ ] 通过/拨付等其他操作不受影响

## Resolution（v1.10.0）
前端守卫+后端400+opinion落状态史与审批任务
