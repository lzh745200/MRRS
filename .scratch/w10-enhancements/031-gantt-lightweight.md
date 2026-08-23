---
labels: [ready-for-agent, severity-medium]
blocks: ["w7-defect-fixes/012-village-kpi-real-aggregate.md"]
blocked-by: ["w9-chain-completion/020-milestone-wiring.md"]
---

# 031: 轻量甘特图视图

**What to build:** 项目列表新增视图切换（表格/甘特）：ECharts 自定义 series 按开始-结束日期横向条+今日线+进度着色，零新依赖。

**Acceptance criteria:**
- [ ] 甘特 series 数据映射 vitest
- [ ] 无日期项目回退占位不崩溃
- [ ] ADR-0012 落稿
