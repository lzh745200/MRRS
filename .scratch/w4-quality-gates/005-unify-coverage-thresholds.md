---
labels: [ready-for-agent, severity-medium]
blocks: ["w4-quality-gates/001-pr-checks-coverage-gate.md"]
blocked-by: []
---

# W4-T5 覆盖率阈值与文档对齐

**来源**: 检测（build-windows 50% / pr-checks 98%(不阻断) / nightly 98%；AGENTS.md 宣称 98% CI gate；pytest.ini 无覆盖率配置）

## 验收标准
- [ ] 三处工作流统一 98%（或明确分级并在 AGENTS.md 如实记录）
- [ ] AGENTS.md / CONTRIBUTING.md 漂移修正
- [ ] pytest.ini 补充本地覆盖率开关说明（不强制默认开）
- [ ] codecov.yml 增加或删除纯展示上传，二选一

## 涉及文件
- `.github/workflows/*`、`AGENTS.md`、`CONTRIBUTING.md`、`codecov.yml`
