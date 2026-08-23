---
labels: [ready-for-agent, severity-high]
blocks: ["w13-docs-release/053-version-build-deliver.md"]
blocked-by: ["w13-docs-release/051-docs-update-adrs.md"]
---

# 052: 全量回归与 E2E 关键路径

**What to build:** 后端 pytest/vitest/flake8/eslint/vue-tsc/bandit 全绿；Playwright E2E 5 条关键路径（登录→村录入→经费申请→审批→备份恢复冒烟）通过；Docker 不可用则降级本地 playwright 直跑并记录。

**Acceptance criteria:**
- [ ] 四大门禁命令零错输出存档
- [ ] E2E 5 路径 PASS 截图/trace 存档
- [ ] backend 覆盖率 ≥98%
