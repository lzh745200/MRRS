---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# 001 发布提交门禁复算与修复（w17 批次收口，v1.12.22）

**来源**：用户指令「按建议逐一执行…确保不新增任何新问题」「继续，确保所有工单全部完成」。
w17 十项工单全部改判 `done` 后，对发布提交 `29248ff`（v1.12.22）做发布前门禁复算，
把「工单文档声称完成」与「CI 门禁实际可过」之间的差额补平。

**为什么必须做**：`29248ff` 尚未推送（`origin/main` 停在 `fd03743`），因此该提交
从未跑过任何 CI 作业 —— 本地复算等价于它的第一次门禁运行。复算发现 4 处必然红
+ 1 处覆盖率缺口（全部会阻断推送后的 PR Checks）。

## 复算发现与修复

| # | 门禁 | 症状 | 修复 |
|---|------|------|------|
| 1 | `lint`（flake8 C901） | `app/core/config.py` `Settings.model_post_init` 复杂度 17 > 16（release 提交新增 `LOG_FILE` 守卫时超标）| 拆出 `_apply_production_security_baseline()` / `_resolve_runtime_paths()`（纯提取，行为不变，与 `_absolutize_sqlite_url` 同一处置先例）|
| 2 | `lint`（flake8 E301） | `app/services/backup_service.py` 少一个空行（W18-D7 恢复前置校验插入时造成）| 补空行 |
| 3 | `lint`（bandit `-ll`） | `app/services/data_package_service.py` B608 Medium：`"SELECT %s FROM %s" % (col_list, table)` | 同行 `# nosec B608` + 理由（表名/列名取自 `model.__table__` 元数据，过滤值走 `text()` 绑定参数），与全库既有豁免口径一致 |
| 4 | `backend-test`（覆盖率口径） | 工作区里 `backend/.coveragerc` 被删（与 `pyproject.toml` 指针注释矛盾），会静默摘掉 `fail_under=100` 门禁 | `git checkout` 恢复（HEAD 内该文件本就存在，删除只是工作区残留）|
| 5 | `backend-test`（覆盖率 100%） | `config.py` 打包态 `LOG_FILE` 改写行（`if self.LOG_FILE.startswith("./")` 真分支）无测试覆盖 —— conftest 把 `LOG_FILE` 覆盖成绝对路径，天然绕过该行 | `tests/unit/test_config_core.py` 新增 `test_frozen_relative_log_file_is_rewritten`（显式传相对 `LOG_DIR`/`LOG_FILE`）|
| 6 | `frontend-check`（coverage-merge 不变量） | `donation/List.vue`、`analytics/supported-villages/Detail.vue` 新增专属深挂载测试后，仍在 `router-index.test.ts` 被真实执行（懒加载遍历）→ 两个执行者，v8 fnMap 分片按 id 合并在 Linux 有错位先例 | `router-index.test.ts` 增补两处 `vi.mock` 桩（与既有 pairing/handover/LoginEnhanced 桩同款）|

## 复算证据

- flake8（`app/`，`--max-complexity=16`）= 0；bandit `-r app/ -ll` = 0；vue-tsc = 0；
  eslint `--max-warnings=0` = 0。
- 17 个静态门禁脚本全过：soft-delete 扫描、os_exit、subprocess 编码、dir_replace、
  unbounded_read、upload_endpoints、scheduler_registration、unused_scope_params、
  userdata_path、raw_sql_fstrings、menu_alignment、security_audit、check_migrations
  （单 head）、hardcoded_styles、tokens_sync、pragma_reasons、version_sync。
- 升级排练 `backend/scripts/upgrade_rehearsal.py` = 0（旧库→`upgrade head` 无表丢失、
  行数不变、`integrity_check=ok`）。
- `npm audit --omit=dev --audit-level=high` = 0 vulnerabilities（生产依赖树，阻断口径）。
- 后端定点回归：提醒处置 / 结对 / 捐赠 / 移交 / 滚动填报 / 导出脚注 / 一村一档 /
  AI 可解释 / 业务体检 / config = **553 passed**。
- 前端定点回归：17 个 w17 相关测试文件 + 菜单/路由对齐 = **295 passed / 19 文件**。

## 结论

- w17 十项工单（001~010）全部落地并收口，工单 001 验收项补勾。
- 本批修复后，`29248ff` 的门禁缺口已补平（详见复算证据）。
- 并行会话在 `29248ff` 之上的**未提交** w18 在途工作（`data_package_service.py`
  65.32%、`backup_service.py` 98.82%、`pii_crypto.py` 分支缺失，以及 R28 upsert /
  data-package 18 条测试失败）不属于本工单范围，已在会话内单独报告。

## W19 收尾验证记录（2026-10-20 晚）

- 主树后端全量 #1（-n 6 + 覆盖率）：**13926 passed / 3 failed**，覆盖率 **100.00%**（44877 stmts / 11028 branches）。
  3 个失败均已修复：	est_grant_guard_r33（security 模块对象分叉）、	est_utils_full_coverage::test_get_database_path
  （worker 库名）、	est_fund_approval_integration（审计定时刷写与 StaticPool 单连接竞态 → session 级 fixture 拉长间隔）。
- 主树后端全量 #2（pytest-randomly 随机序）：8 failed / 12 errors，均为**既有**随机序耦合
  （pp.main 被部分用例 reload、favicon/version/SPA、data_quality 鉴权、branch_gaps 组），
  超出本票 8 文件范围；8 个原「必须先跑」文件随机序 **304 passed** 作为验收冒烟。
- 主树后端全量 #3（常规顺序）：6 failed，**全部落在另一会话未提交的 W25 在途改动**上：
  pp/services/approval_workflow_service.py、pp/api/v1/data/data/statistics.py，
  以及其修改中的 	est_approval_workflow_service.py / 	est_coverage_tail_gaps.py。
  按既定约束不修改他人在途代码。
- 为获得不受在途改动影响的证据，在**工作区内**创建 HEAD 隔离检出
  .scratch/w19-head-verify（HEAD=086e996），仅叠加本票的 5 个后端文件，
  运行两轮全量（常规顺序 + -n 6 + 覆盖率）。日志：deliverables/w19-gates/。
  注：系统临时目录在本环境不可写（纯 Python 亦 PermissionError），pytest 回落到 cwd 临时根；
  工作区外的 worktree 会因沙箱权限导致 FileNotFoundError: No usable temporary directory，
  故隔离检出放在工作区内。
