---
labels: [ready-for-agent, severity-medium]
blocks: ["w5-perf-consistency/001-vendor-chunk-split.md"]
blocked-by: []
---

# W5-T3 图表引擎归一 echarts

**来源**: 检测 P1-4（chart.js 与 echarts 并存；`useECharts.ts:54` 死代码全量导入）

## 验收标准
- [ ] WorkAnalysis.vue / ruralWorks/Analysis.vue 迁移到 utils/echarts（tree-shaken）
- [ ] 删除 chart.js 依赖与死 useECharts composable
- [ ] 两页面图表渲染回归（vitest + 手动冒烟）
- [ ] dist 中 chartjs chunk 消失

## 涉及文件
- `frontend/src/composables/useECharts.ts`、两个视图、`package.json`
