---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 011: 数据质量自动修复诚实化

**What to build:** 后端 clean_dataset 支持 trim_whitespace/normalize_empty 两键真实处理；前端 QualitySection 报告口径与实际处理一致（fail-closed：不支持即明确报错而非假成功）。

**Acceptance criteria:**
- [ ] trim/normalize 规则产生真实数据变更（pytest）
- [ ] 未知规则键返回 400 明确报错而非静默忽略
- [ ] 前端成功文案与实际 processed 数一致（vitest）
