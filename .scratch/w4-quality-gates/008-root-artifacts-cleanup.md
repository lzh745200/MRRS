---
labels: [done, severity-low]
blocks: []
blocked-by: []
---

# W4-T8 仓库卫生：根目录遗留物清理 + make clean 扩展

**来源**: 检测（根目录 17 个 vitest 日志/json、test.db、.coverage；`Makefile:66-71` clean 不扫根目录）

## 验收标准
- [x] 删除根目录 vitest-*.{log,json}、test.db、.coverage 及 frontend 下同类
- [x] make clean 增加根目录清理段
- [x] .gitignore 补 `data_sync/`、根目录 `vitest-*`
- [x] git status 干净（不误删被跟踪文件）

## 涉及文件
- 根目录、`Makefile`、`.gitignore`

## Resolution（2026-09-13 全面清理批次）

**1. 根目录遗留物**
- `vitest-*.{log,json,mjs}` / `test.db`：检测当日已为 0 个（此前批次已回收），本轮复核确认为空。
- 删除根 `.coverage`（1654h 未更新）、`.pytest_cache`、`.ruff_cache`，以及 24 个 `_*.log`/`_*.txt` 会话临时输出
  （`_d1.log`、`_d2.txt`、`_git.log`、`_verify_build_win*.log`、`_vit_u8.txt` 等，均为 27~30h 前的历史批次产物）。
- 同批删除 `backend/coverage.json`、`backend/coverage.xml`、`backend/.covperm_v5`、`backend/*.log`、
  `frontend/_verify_*.log`、`frontend/coverage/`（20.6MB）。

**2. make clean 扩展**（`Makefile` clean 段新增 6 行，纯追加）
```make
-rm -f .coverage _*.log _*.txt backend/coverage.json backend/.covperm_v5 2>/dev/null || true
-rm -f backend/*.log frontend/_verify_*.log 2>/dev/null || true
-rm -rf .pytest_cache .ruff_cache 2>/dev/null || true
-find . \( -name node_modules -o -name .venv -o -name .git -o -name dist \) -prune -o -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
```
原 clean 只覆盖 `backend/` 下的 `__pycache__`（`find backend`）与 frontend 覆盖率，
现补齐「后端以外 `__pycache__`」（根 `tests/`、`scripts/`、`electron/`）与上述遗留物。

**3. .gitignore**：复核后**未改动**——`data_sync/`（第 307 行）、`vitest-*.log|json|mjs`（303-305 行）、
`/_*.txt`（193 行）已全部存在。按「不写重复规则」原则不追加冗余条目。

**证据**
- `git status --porcelain`：本次改动对**被跟踪文件零删除**（`-D` 计数 0），工作树仅含本轮显式修改项。
- 清理后 `from app.main import app` 通过：**786 条路由 / 46 个业务模块**全部静态注册成功。
- `flake8 app/ --max-line-length=120 --max-complexity=16`：**0 违例**；pyflakes 子集
  （F401/F811/F841/F821/F823/F522/F632）**0 违例**。
- 清理后全量单元测试：`pytest tests/unit` → **10842 passed, 0 failed**（12:39；
  `--deselect test_org_tree_metadata_r14.py` 排除并发会话在途的 TDD 红测试）。
- `cd frontend && npm run type-check`（vue-tsc --noEmit）：**通过**。
