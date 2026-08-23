---
labels: [done, severity-high]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 023: 政策 FTS5 全文搜索接线

**What to build:** Search.vue 定位全文检索专页：q= 调 GET /policies/search，BM25 排序+高亮摘要渲染；保留 List 结构化筛选差异化共存。

**Acceptance criteria:**
- [ ] 搜索命中返回高亮片段渲染（vitest）
- [ ] 空结果 el-empty
- [ ] FTS 索引同步既有 pytest 保持绿

## Resolution（v1.10.0 续批）
Search.vue接FTS5端点+snippet高亮列(mark样式)
