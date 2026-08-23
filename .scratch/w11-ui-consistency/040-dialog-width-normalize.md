---
labels: [ready-for-agent, severity-low]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 040: 弹窗宽度收敛两档

**What to build:** 编辑类弹窗统一 600px、复杂表单 800px（用户规范），76 处 13 种取值分批调整；超大表格弹窗允许 960px 白名单注释豁免。

**Acceptance criteria:**
- [ ] 宽度分布脚本输出仅 {600,800,960*}
- [ ] 抽查 8 个弹窗视觉无溢出
- [ ] vitest 全量绿
