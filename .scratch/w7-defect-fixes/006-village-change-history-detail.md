---
labels: [done, severity-high]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 006: 变更历史字段级明细展示

**What to build:** ChangeHistoryDialog 渲染 changes[{field,old_value,new_value}] 时间线：谁在何时把什么从 A 改为 B。

**Acceptance criteria:**
- [ ] 字段级 old/new 以时间线节点展示（vitest）
- [ ] 无 changes 时回退摘要文案不报错

## Resolution（v1.10.0）
ChangeHistoryDialog字段级渲染重写
