---
labels: [done, severity-medium]
blocks: []
blocked-by: ["w11-ui-consistency/038-tokenize-top10-files.md"]
---

# 039: EP 灰阶 Token 化分批

**What to build:** #303133/#606266/#ebeef5/#f5f7fa/#c0c4cc/#999/#666 系列 → 对应 token 变量，按 views 目录三批替换，每批独立合入。

**Acceptance criteria:**
- [ ] 每批后 vitest+vue-tsc 绿
- [ ] 三批完成后 EP 旧灰阶字面量 <50 处（脚本统计输出）
- [ ] chartColors.ts 迁移至主题变量并保持图表视觉一致

## Resolution (v1.10.0 batch 14)
T039: 三批灰阶token化(7目标色->\-text-*/\-border*/\-bg-page)，仅替换<style>块并补lang=scss。views内目标灰阶grep归零(0处，<50达标)；chartColors.ts已运行时读CSS变量无需改；每批TSC0+vitest绿(683/819/1212)。
