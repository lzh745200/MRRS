# ADR-0012: 轻量甘特图视图（项目列表）

- 日期: 2026-08-24
- 状态: 已采纳
- 决策人: 前端架构

## 背景

项目列表仅有表格视图，无法直观查看各项目工期重叠与进度。需新增甘特图视图，
但引入重型甘特库（如 dhtmlx-gantt）会增加包体与离线打包复杂度。

## 决策

不引入新依赖，复用 ECharts 时间轴 + 堆叠条模拟横向甘特条：

- 每个项目为 y 轴类目，x 轴为 time 类型。
- 两条 series 堆叠：透明 offset 条（定位起点）+ 可见 duration 条（按进度着色：
  100% 军绿、≥60% 中绿、否则金）。
- 今日线用 `markLine` 虚线红标「今日」。
- 无开始/结束日期或日期非法的项目回退为占位灰条（value=1），不崩溃。
- 纯函数 `buildGanttData` / `buildGanttOption`（`src/utils/gantt.ts`）承载数据映射，
  由 `GanttView.vue` 包裹 `BaseChart` 渲染，视图切换在 `projects/List.vue` 用
  `el-radio-group` 切换 table/gantt。

## 影响

- 零新依赖，包体不增。
- 视觉一致：着色复用 tokens（`$military-*` / `$badge-gold` / `$alert-red`）。
- 无日期项目安全降级，不抛错。

## 替代方案

- dhtmlx-gantt：功能全但体积大、离线许可与主题定制成本高，否决。
- 第三方 Vue 甘特组件：维护性与离线打包不确定性高，否决。
