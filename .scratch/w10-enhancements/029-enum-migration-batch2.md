---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: ["w7-defect-fixes/010-fund-status-enum-source-expand.md"]
---

# 029: 映射源收敛 migrate 批（project/approval/entityType）

**What to build:** project 8 态、approval 4 态、entity_type 全量入 enums.ts；projects/approval 相关视图私有映射替换为共享导入；formatEntityType 补 rural_work/assessment。

**Acceptance criteria:**
- [ ] 任务状态/优先级列中文渲染（vitest）
- [ ] 审批类型标签含 rural_work/assessment 中文
- [ ] 被替换视图快照更新且测试绿
