---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: ["w11-ui-consistency/038-tokenize-top10-files.md"]
---

# 039: EP 灰阶 Token 化分批

**What to build:** #303133/#606266/#ebeef5/#f5f7fa/#c0c4cc/#999/#666 系列 → 对应 token 变量，按 views 目录三批替换，每批独立合入。

**Acceptance criteria:**
- [ ] 每批后 vitest+vue-tsc 绿
- [ ] 三批完成后 EP 旧灰阶字面量 <50 处（脚本统计输出）
- [ ] chartColors.ts 迁移至主题变量并保持图表视觉一致
