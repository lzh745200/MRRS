---
labels: [done, severity-medium]
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

## Resolution（W19 完成）

阈值口径已收敛为两处**单一事实源**，且文档/CI 无历史漂移残留：

- 后端：`backend/.coveragerc` `fail_under=100` + `branch=True`；Makefile L85、`pr-checks.yml`、
  `nightly-full.yml` 均**不内联** `--cov-fail-under`（内联参数会屏蔽配置文件口径，该规则已写入
  AGENTS.md「Backend Coverage」段）。
- 前端：`frontend/vitest.config.ts` 12 组 glob 阈值，`statements/branches/functions/lines` 全 100。
- 文档：`CONTRIBUTING.md` L46-49 与 AGENTS.md 均明示「100%（可覆盖集口径）」及各自事实源，无不一致。
- Codecov 定性为**纯展示**：CI 上传步骤带 `continue-on-error: true`；本轮新增仓库根 `codecov.yml`，
  显式关闭 Codecov 自身的 project/patch 状态检查（保留 PR 评论），避免出现与本地门禁并行的第二套判定。
