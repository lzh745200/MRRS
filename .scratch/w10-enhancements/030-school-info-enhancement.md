---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 030: 学校信息架构补强

**What to build:** 列表加地区列（行政区划级联文本）；详情页成效统计卡（累计资助学生数/金额，复用 statistics 接口）；附件预览复用 FilePreview 组件；删除前关联检查提示（有关联学生/项目给出警示文案二次确认）。

**Acceptance criteria:**
- [ ] 地区列渲染（vitest）
- [ ] 成效卡数值来自接口非本地聚合
- [ ] 附件 PDF 内嵌/Office 下载提示分流
- [ ] 关联存在时删除确认含警示（pytest 依赖计数端点或复用现有统计）
