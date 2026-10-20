---
labels: [done, severity-high]
blocks: ["w13-docs-release/053-version-build-deliver.md"]
blocked-by: ["w13-docs-release/051-docs-update-adrs.md"]
---

# 052: 全量回归与 E2E 关键路径

**What to build:** 后端 pytest/vitest/flake8/eslint/vue-tsc/bandit 全绿；Playwright E2E 5 条关键路径（登录→村录入→经费申请→审批→备份恢复冒烟）通过；Docker 不可用则降级本地 playwright 直跑并记录。

**Acceptance criteria:**
- [x] 四大门禁命令零错输出存档
- [x] E2E 5 路径 PASS 截图/trace 存档
- [x] backend 覆盖率 ≥98%

## Resolution（W19 完成）

### 1) 四大门禁（零错输出存档，`deliverables/w19-gates/`）

| 门禁 | 命令 | 结果 | 存档 |
|------|------|------|------|
| 后端全量 + 覆盖率 | `pytest tests/ -q --tb=short -n 6 --cov=app --cov-branch` | **两轮均 13929 passed / 1 skipped**（1135s / 894s）；覆盖率 **100.00%**（44877 stmts / 11028 branches，`fail_under=100`） | `backend-full-WT-runA.log` / `runB.log`、`coverage-branch-WT-run{A,B}.json` |
| 分支覆盖率棘轮 | `scripts/check_branch_coverage.py` | 11028/11028 = **100.00%**，exit 0 | 命令输出（本票记录） |
| 前端全量 | `npx vitest run --coverage` | **331 文件 / 6875 用例 passed**；12 组 glob 阈值 statements/branches/functions/lines **全 100%**（All files 100/100/100/100） | `frontend-coverage.log` |
| flake8 | `flake8 app/ --max-line-length=120 --count --max-complexity=16` | **0 errors** | `flake8.log` |
| eslint | `npm run lint:check` | **0 error / 0 warning** | `frontend-lint.log` |
| 类型检查 | `npx vue-tsc --noEmit` | **exit 0** | `vue-tsc.log`（空输出=零报错） |

说明：后端两轮在 **HEAD 隔离检出**（`.scratch/w19-head-verify`，HEAD=`086e996` + 本票 5 个后端文件）
执行 —— 主树当时存在另一会话未提交的 W25 在途改动（`approval_workflow_service.py`、`statistics.py`
及其测试），其 6 个失败与本票无关，按既定约束未修改他人在途代码。

### 2) E2E 关键路径（Docker 不可用 → 本地 Playwright 直跑）

- 环境：Windows + 系统 Edge 内核（`channel: 'msedge'`），端口隔离 18000/15173，独立库
  `backend/data/e2e_test.db`；全局前置 API 登录 + 首登强制改密自适应。
- **全量：165 passed（5.8 分钟），exit 0** —— `deliverables/w19-e2e/e2e-full.log`、`report.json`、
  `html-report/`。
- 5 条关键路径映射与结果（`--trace=on` 专项重跑 **51 passed**，trace 存档 51 份 / 85.7MB，
  位于 `deliverables/w19-e2e/traces/`）：
  1. **登录** → `flows/login.spec.ts`
  2. **村录入/生命周期** → `flows/village-lifecycle.spec.ts` + `flows/core-business-flow.spec.ts`
  3. **经费申请** → `flows/funds.spec.ts`
  4. **审批** → `flows/approval.spec.ts`
  5. **备份/恢复冒烟（本轮新增）** → `flows/backup-restore.spec.ts`：创建备份 → 列表出现恢复入口 →
     恢复覆盖警告确认框 → 取消（**绝不执行真实恢复**，避免覆盖 E2E 库导致后续用例全灭）。
- 本轮 E2E 适配（测试侧，非产品回归）：空态统一后 `.el-table, .el-empty` 组合选择器会同时命中表格与
  表内隐藏空块（Element Plus 语义），4 处改为 `.first()`；villages 页两个「新增」按钮同样 `.first()`；
  备份页首个用例放宽 Vite 冷编译等待并改用 `getByRole('heading', { name: '恢复备份' })` 精确定位。

### 3) 覆盖率

- 后端 **100.00%**（要求 ≥68%），分支覆盖率 100% 且棘轮门禁 exit 0；前端 12 组 glob 全 100%。
