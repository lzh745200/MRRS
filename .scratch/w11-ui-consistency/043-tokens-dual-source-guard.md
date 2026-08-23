---
labels: [ready-for-agent, severity-low]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 043: tokens 双维护一致性守卫

**What to build:** scripts 增加 tokens.scss 尾部 $ 映射与 tokens-vars.scss 一致性校验脚本并入 pre-commit（drift 即 fail）。

**Acceptance criteria:**
- [ ] 人为制造漂移脚本 FAIL（自测）
- [ ] pre-commit 本地运行通过
