---
labels: [done, severity-medium]
blocks: []
blocked-by: ["w7-defect-fixes/010-fund-status-enum-source-expand.md"]
---

# 029: 映射源收敛 migrate 批（project/approval/entityType）

**What to build:** project 8 态、approval 4 态、entity_type 全量入 enums.ts；projects/approval 相关视图私有映射替换为共享导入；formatEntityType 补 rural_work/assessment。

**Acceptance criteria:**
- [x] 任务状态/优先级列中文渲染（vitest）
- [x] 审批类型标签含 rural_work/assessment 中文
- [x] 被替换视图快照更新且测试绿

## Resolution（W19 完成）

- **共享枚举已补全**：`frontend/src/config/enums.ts` 含 `PROJECT_STATUS`（8 态）、`PROJECT_TYPES`、
  `APPROVAL_STATUS` / `APPROVAL_ACTIONS`、`ENTITY_TYPES`（含 `rural_work: '乡村工作'`、
  `assessment: '考核复核'`）、`TASK_PRIORITY`，本轮补入 **`TASK_STATUS`**（待分配/进行中/已完成/
  已延期/已取消）与 `getTaskStatusLabel`。
- **视图私有映射替换为共享导入**：`views/ruralWorks/Task.vue` 删除本地 `getPriorityLabel` /
  `getStatusLabel` 两个 switch 及导出用的 `statusMap` / `priorityMap`，改由
  `@/config/enums` 的 `getTaskPriorityLabel` / `getTaskStatusLabel` 统一渲染列、进度弹窗与 CSV 导出。
  审批侧 `History/PendingList/Overview` 与 `projects/Detail` 已直接使用 `ENTITY_TYPES` /
  `PROJECT_STATUS`（`@/config/enums` 被 10 个文件引用）。
- **测试**：
  - `tests/unit/config/enums.test.ts` 新增 `TASK_STATUS` 常量/标签/未知回落三组断言（29 passed）；
  - `tests/unit/api/approval.test.ts` 覆盖 `formatEntityType('rural_work')='乡村工作'`、
    `('assessment')='考核复核'` 与未知原样返回（47 passed）；
  - `tests/unit/views/ruralWorks/Task.test.ts` 新增「状态/优先级列渲染中文标签」用例，
    断言三行样本渲染为 高/中/低 与 待分配/进行中/已取消（该文件 63 passed）。
  - 三文件合计 **105 passed**。
