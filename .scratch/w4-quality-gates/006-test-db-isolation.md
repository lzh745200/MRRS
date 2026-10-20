---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# W4-T6 测试 DB 隔离统一（内存库 + worker 隔离）

**来源**: 检测（`conftest.py:14` 强制共享文件库 test.db，CI -n auto 曾损坏开发库；:670-678 autouse create_all 打共享库）

## 验收标准
- [x] conftest 默认改 `sqlite:///`（内存）+ xdist 按 worker 命名（file:memMode 或 tmp_path per worker）
- [x] 删除会话级共享 test.db 逻辑
- [x] 全量测试（含 -n auto）连续两轮全绿
- [x] 真文件库场景用显式 marker/fixture 隔离

## 涉及文件
- `backend/tests/conftest.py`

## Resolution（W19 完成）

- **测试库彻底脱离仓库相对路径**：`backend/tests/conftest.py` 统一 `TEST_DATABASE_URL` 为
  「进程临时根下的绝对路径」，并显式带 xdist worker 标识（`test_gw0.db` / 非 xdist 时 `test.db`）；
  `_APP_DATA_ROOT` 由 `tempfile.mkdtemp` 每进程一份 → 每个 worker 独立库。
  历史上 `sqlite:///./test.db` 会被同机并发 pytest 共享、并在 `CWD` 落下 `backend/test.db` 的路径，
  仓库内已 `git grep` 确认 **0 处**。
- **默认内存库**：`client` fixture 使用 `sqlite:///:memory:` + `StaticPool`，并把
  `app.core.database.engine/SessionLocal` 一并指向内存库（函数级隔离），测试结束回滚/还原。
- **真文件库场景**：备份/恢复、升级排练等需要真实文件的用例继续用显式 fixture/`tmp_path`；
  路径解析测试（`test_paths.py` / `test_utils_full_coverage.py`）显式断言「解析结果 == 运行时
  `DATABASE_URL` 指向的同一文件」，worker 后缀变化不再导致误判。
- **连续两轮全量（含 `-n 6`）全绿**：
  - 第 1 轮：================ 13929 passed, 1 skipped in 1135.15s
  - 第 2 轮：================ 13929 passed, 1 skipped in 894.17s
  两轮均为常规顺序 + `--cov=app --cov-branch`，覆盖率 **100.00%**（`fail_under=100` 达成）。
- 顺带清理：`make clean` 现在会回收 `backend/bumofu_pytest_appdata_*`（会话临时数据根）与
  `backend/data/test.db`（历史共享库残留）；这两类产物已被 `.gitignore` 覆盖。
- 说明：本机 `tempfile.gettempdir()` 解析到仓库 `backend/`（TEMP 环境变量存在但默认临时目录探测
  失败，纯 Python 亦复现），所以会话临时根落在仓库内；这是**环境特性**而非测试代码缺陷，
  隔离性与 git 洁净度由上述 gitignore + clean 兜底。
