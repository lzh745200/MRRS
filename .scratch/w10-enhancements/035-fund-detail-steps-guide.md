---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: ["w7-defect-fixes/009-fund-reject-reason-required.md", "w7-defect-fixes/010-fund-status-enum-source-expand.md"]
---

# 035: 经费详情体验包：步骤条+操作指引

**What to build:** Detail.vue 顶部复用八阶段 el-steps（由状态推导 active）；关键按钮（申请/审批/拨付/报销/决算）旁 el-popover 问号指引：前置条件/后续影响/下一步。

**Acceptance criteria:**
- [ ] active 推导与状态机一致（vitest 参数化 7 态）
- [ ] 五个 popover 内容渲染
- [ ] 指引文案与 ADR-0009/0011 口径一致
