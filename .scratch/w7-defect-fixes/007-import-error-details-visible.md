---
labels: [done, severity-high]
blocks: ["w8-dead-code/018-micro-redundancy-sweep.md"]
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 007: 导入错误明细回显（村+学校）

**What to build:** 村 List.vue 导入后展示 errors[] 明细表格（行号+原因），不再只提示条数 console.log；学校 List 从信封 data.errors 正确读取并同款展示。

**Acceptance criteria:**
- [ ] 两处导入失败时弹窗/面板列出前 N 条明细（vitest）
- [ ] 学校侧从 res.data.errors 取数（修正信封层级）
- [ ] 复用统一错误明细展示片段避免双实现

## Resolution（v1.10.0）
两处导入明细弹窗+信封层级修正
