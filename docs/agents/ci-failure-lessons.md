# CI 红灯教训与防复发规则（2026-10-25）

> 本文记录 2026-10-25 一天内 **多轮 PR Checks 红 / Nightly 红 / 两次 tag 构建失败**的
> 根因与已经落地的自动化防线。新增发布相关流程前必读。

## 一、真实故障时间线（摘录）

| 时间 | 现象 | 根因 |
|---|---|---|
| 05:12 | v1.18.4 tag 构建失败 | main 的 PR Checks 未绿就打了 tag；更早还有并发推送导致 PR Checks 被 `cancelled` |
| 05:13 | v1.18.5 tag 构建失败 | 同上；且该 tag commit 的 PR Checks 被后续 push 取消 |
| 07:06 | Nightly Full Test 失败 | 后端全量覆盖率 `99.82 < 100`、前端 `src/utils` / `src/api` 覆盖率缺口（99.9/99.53） |
| 12:55 | PR Checks 失败 | 前端覆盖率缺口（`src/utils` 99.91 / `src/api` 99.9）；后端 `MAX_PAGE_SIZE` 断言过期 |
| 13:10 | PR Checks 失败 | `tests/unit/test_svc_batch.py::test_h10` 仍断言常量等于旧值 100（`constants.py` 已改为 200） |
| 16:40 | PR Checks 失败 | E2E `village-lifecycle` 选择器 `.el-dialog,.el-drawer,form` 的 `.first()` 命中顶栏新增的**隐藏**同步抽屉 |
| 16:45 | Nightly 失败 | Nightly 6 段分组漏 `backend/tests/*.py` 根目录 → `permission_packs.py` 夜间覆盖率 38%、总覆盖 99.82% |
| 17:10 | PR Checks 失败 | `scripts/release_tag.py` 裸 `# pragma: no cover`（无理由）→ F2 棘轮 NEW=1 |

## 二、根因分类（按代价排序）

1. **发布动作早于验证结论**（最贵）：`git push` 成功后立刻 `git tag`，而 PR Checks 尚在
   `in_progress` / 被取消 / 已失败。tag 构建内的 `check_release_gate.py` 只能拒绝，无法阻止动作本身。
2. **常量与断言漂移**：常量是单一事实源，但测试里写死历史值；本地按"相关套件"验证时
   **碰不到**那条断言，CI 分段才跑到。
3. **覆盖率只差 0.1%**：`src/utils`/`src/api` 的少数分支未覆盖；后端聚合覆盖率 99.82。
   本地 `vitest --coverage` 与 CI 的分片聚合口径不同，容易"本地绿、CI 红"。
4. **并发推送取消验证**：`concurrency.cancel-in-progress` 对 main 生效时，
   连续推送会让前一次 PR Checks 变成 `cancelled`，于是"推动成功但没有任何一次完整验证"。

## 三、已落地的防线（不要绕过）

| 防线 | 位置 | 作用 |
|---|---|---|
| `check_main_ci.py` | `scripts/` | 查/等某个 commit 的 PR Checks 结论（`--wait-minutes`） |
| `check_release_gate.py` | `scripts/`（构建工作流内） | tag 构建前置门禁：结论必须 success（或被取消时回退 main 最近 success），等待上限 90 分钟 |
| **`release_tag.py`（唯一发布入口）** | `scripts/` | 一次跑完：分支必须是 main、工作区干净、tag 与 `package.json` 版本一致、CHANGELOG 已记录、HEAD 的 PR Checks 必须绿 → 才 `git tag && git push`；默认 dry-run |
| `check_constants_sync.py` | `scripts/` + `.pre-commit-config.yaml`（pre-push） | 扫描 `backend/tests`、`docs` 里的 `CONST == 字面量`，与 `backend/app/core/constants.py` 不一致即拦 |
| `pr-checks.yml` concurrency | `.github/workflows/` | `cancel-in-progress` **只对 PR** 生效；main 排队，避免"推送即取消" |
| `electron/tests/ci-wiring.test.js` | `electron/tests/` | 守卫上述接线：release gate 等待预算 ≥60 分钟、main 不得恢复取消、缺少 `check_main_ci.py` 接线即测试红 |

## 四、发布纪律（硬规则）

1. **禁止**手工 `git tag && git push origin vX`：一律
   `python scripts/release_tag.py --apply --tag vX.Y.Z`（它会等 PR Checks 绿）。
2. tag 之前：本地门禁全绿（至少 `check_changelog.py`、`check_doc_numbers.py`、
   `check_constants_sync.py`、改动文件的 flake8 / vitest），且 `git status` 干净。
3. 改了 `backend/app/core/constants.py` 的常量 → **同提交** 搜索并更新测试/文档中的字面量
   （`git grep <常量名>`），pre-push 的 `check-constants-sync` 会拦。
4. 覆盖率不是"大概齐"：前端 `src/**` 阈值 100%、后端 `--cov=app` 100%；
   新增分支必须带用例。本地至少要跑**改动文件所在目录的完整覆盖**（不要只跑"相关文件"）。
5. **E2E 选择器必须可辨识"可见"**：`.el-dialog, .el-drawer, form` 这类多类型 `.first()` 会被
   顶栏/全局的隐藏抽屉污染；断言一律用 `:visible` 过滤或 `data-testid`，不要依赖 DOM 顺序。
6. **Nightly 与 PR Checks 必须同一测试覆盖面**：两套分组曾漏掉 `backend/tests/*.py` 根目录，
   造成"PR 绿、Nightly 恒红"；`check_nightly_test_parity.py` 已把这条变成机械检查。
7. 被并发推送取消的运行**不算验证**：用 `gh run list --branch main` 确认目标 commit
   确实有一次 `completed/success`，而不是 `cancelled`。

## 五、复盘检查清单（CI 红时按顺序看）

```bash
# 1. 哪个 commit、哪个 job、哪一步红
gh run list --limit 10
gh run view <run-id> --log-failed | grep -E "::error::|does not meet|FAILED|Test Files"
# 2. 目标 commit 的 PR Checks 结论
python scripts/check_main_ci.py --sha <sha>
# 3. 常量漂移
python scripts/check_constants_sync.py
# 4. 覆盖率缺口（前端看 ERROR: Coverage 行；后端看 --cov 的 missing 列）
```

修复后：提交 → 推送 main → `python scripts/release_tag.py --apply`（等绿后自动打 tag）。
