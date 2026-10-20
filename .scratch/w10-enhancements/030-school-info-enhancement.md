---
labels: [done, severity-medium]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 030: 学校信息架构补强

**What to build:** 列表加地区列（行政区划级联文本）；详情页成效统计卡（累计资助学生数/金额，复用 statistics 接口）；附件预览复用 FilePreview 组件；删除前关联检查提示（有关联学生/项目给出警示文案二次确认）。

**Acceptance criteria:**
- [x] 地区列渲染（vitest）
- [x] 成效卡数值来自接口非本地聚合
- [x] 附件 PDF 内嵌/Office 下载提示分流
- [x] 关联存在时删除确认含警示（pytest 依赖计数端点或复用现有统计）

## Resolution（W19 完成）

- **地区列**：`views/schools/List.vue` 新增 `prop="region"` 列与 `formatRegion()`：
  优先后端 `School.to_dict` 生成的 `region`（province+city+district），缺失时回退分字段
  `province / city / district` 拼接，仍无数据返回 `-`。
- **帮扶成效统计卡**：`views/schools/Detail.vue` 通过 `schoolApi.getSchoolStatistics(id)`
  请求 `GET /schools/{id}/statistics`，展示累计资助学生数/金额、助学兴教项目数、项目预算总额；
  `statsValue()` 在加载中/字段缺失时显示 `-`，**不在本页对已加载列表做本地累加**；
  失败时展示错误文案与「重试」按钮（`loadStatistics` 可重入）。
- **附件预览**：复用 `components/FilePreview.vue`——PDF 内嵌 iframe、图片直显、Office 类提示下载。
- **删除前关联检查**：`handleDelete()` 先取关联计数，有关联资助学生/助学项目时以
  `ElMessageBox.confirm` 的警示文案二次确认（计数失败不阻断删除）。
- **测试**：`tests/unit/views/schools/SchoolsViewsBatch.test.ts`（11 passed）新增：
  - 成效卡「展示 statistics 接口返回值」——mock `GET /schools/1/statistics` 返回
    `{scholarship_count:7, scholarship_total_amount:1234, project_count:3, project_total_budget:56.5}`，
    断言四个 `.effect-value` 依次为 `7 / 1234元 / 3 / 56.5万元`，并断言该接口被精确调用；
  - `formatRegion` 三分支（region / 分字段拼接 / 空值 `-`）。
  - `tests/unit/api/schoolsFull.test.ts`（21 passed）覆盖 schools API 全量函数。
