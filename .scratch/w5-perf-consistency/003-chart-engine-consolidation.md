---
labels: [done, severity-medium]
blocks: ["w5-perf-consistency/001-vendor-chunk-split.md"]
blocked-by: []
---

# W5-T3 图表引擎归一 echarts

**来源**: 检测 P1-4（chart.js 与 echarts 并存；`useECharts.ts:54` 死代码全量导入）

## 验收标准
- [x] WorkAnalysis.vue / ruralWorks/Analysis.vue 迁移到 utils/echarts（tree-shaken）
- [x] 删除 chart.js 依赖与死 useECharts composable
- [x] 两页面图表渲染回归（vitest + 手动冒烟）
- [x] dist 中 chartjs chunk 消失

## 涉及文件
- `frontend/src/composables/useECharts.ts`、两个视图、`package.json`

## Resolution（W19 完成）

- **依赖与死代码已清除**：`frontend/package.json` 仅剩 `echarts ^6.1.0`（无 chart.js）；
  `frontend/src/composables/useECharts.ts` 不存在；全仓 `from 'chart.js'` / `useECharts` 命中为 0。
- **两个目标视图已迁移**到 `@/utils/echarts`（tree-shaken 入口）：
  `views/analytics/reports/WorkAnalysis.vue`、`views/ruralWorks/Analysis.vue`。
- **渲染回归（vitest）**：`WorkAnalysis.test.ts` **22 passed**、`ruralWorks/Analysis.test.ts` **36 passed**
  （本轮因 W11-041 空态改动重跑，覆盖迁移后的图表构建/销毁/resize 路径）。
- **dist 产物核验**：`npm run build` 成功（exit 0）。产物内 chart 相关块仅有
  `echarts-*.js`、`BaseChart-*.js`、`chartColors-*.js`；对全部 dist JS 扫描
  `chart.js v|chartjs|new Chart(` 特征串 → **0 命中**，chart.js 懒加载块已消失。

未验证项：浏览器手动冒烟（本机无 Playwright 浏览器环境以交互审查），以 vitest + 构建产物扫描替代。
