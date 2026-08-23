---
labels: [ready-for-agent, severity-low]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 041: 空态全覆盖与斑马纹去重

**What to build:** 列表/图表空态补 el-empty+「去添加」指引（Dashboard ChartRow 文本 div 替换）；移除 68 处冗余 stripe 属性依赖全局斑马纹；分析空数据显示空态而非全 0 图。

**Acceptance criteria:**
- [ ] 主要列表空态截图级验证（人工清单记录 Resolution）
- [ ] stripe 属性残留 <10（白名单注释除外）
- [ ] analytics 空数据渲染 el-empty（vitest）
