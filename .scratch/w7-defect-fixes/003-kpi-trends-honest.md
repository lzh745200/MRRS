---
labels: [done, severity-high]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 003: KPI 趋势接通与环比诚实化

**What to build:** dashboard index.vue 向 KpiCards 传 trends；卡片渲染真实环比；analytics Dashboard 环比负增长显示红色下降箭头（当前恒绿升）。

**Acceptance criteria:**
- [ ] KpiCards 接收 trends prop 并渲染涨跌方向与颜色
- [ ] 负增长用 danger 色下降箭头（vitest 断言两类分支）
- [ ] sparkline 移除模拟数据改真实 trends 或移除组件（不留假数据）

## Resolution（v1.10.0）
trends接通+方向动态化+真实sparkline序列
