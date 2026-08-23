---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: ["w8-dead-code/014-approval-center-contract.md"]
---

# 033: 审批详情左 diff 右时间线

**What to build:** History/PendingList 详情升级为左右布局：左侧申请内容+变更 diff，右侧审批轨迹 el-timeline（事件源=审批历史+状态日志聚合）。

**Acceptance criteria:**
- [ ] timeline 节点含操作人/动作/时间（vitest）
- [ ] diff 表格复用既有 computed 不重复实现
- [ ] 移动窄屏纵向堆叠不破版
