---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# W4-T7 移除 sklearn sys.modules 注入 + 顺序耦合治理

**来源**: 检测（`tests/unit/conftest.py:5-22` MagicMock sklearn/scipy；`conftest.py:89-107` _POLLUTION_SENSITIVE 官方顺序依赖清单；`conftest_extended.py:31` 缺 sqlalchemy.event 导入的地雷）

## 验收标准
- [x] requirements-dev 补真实 scikit-learn/scipy 或预测测试显式 skipif + 标注（移除 sys.modules 注入）
- [x] _POLLUTION_SENSITIVE 清单逐文件消除：修复 mock 链使其不再依赖先跑
- [x] 引入 pytest-randomly 冒烟验证一轮随机顺序
- [x] conftest_extended.py 补导入或删除死代码
- [x] 全量测试全绿

## 涉及文件
- `backend/tests/conftest.py`、`backend/tests/unit/conftest.py`、`backend/tests/conftest_extended.py`

## Resolution（W19 完成）

- **移除 sys.modules 注入**：`backend/tests/unit/conftest.py` 从「真实包优先 + 缺失时 MagicMock 注入」
  改为**完全不再注入**（仅保留说明 docstring）。`scikit-learn` 是 `backend/requirements.txt` 的运行时
  依赖（scipy 随其安装），CI 与本地 venv 必然存在真实包；需要特定预测行为的用例在用例内显式 patch
  目标模块（如 `test_anomaly_detection_service_complete`）。
- **删除强制排序清单**：`backend/tests/conftest.py` 的 `_POLLUTION_SENSITIVE`（8 个「必须先跑」文件）
  与 `BUMOFU_TEST_NO_ITEM_REORDER` 逃生舱**整体删除**。这 8 个文件在自然顺序下一起运行
  **304 passed**（本轮实测），证明原「必须先跑」依赖已消除。
- **pytest-randomly 随机序冒烟**：临时安装 `pytest-randomly==3.16.0`，以随机种子
  （`--randomly-seed=553670018`）跑上述 8 文件 → **304 passed**。`requirements-dev.txt` 已加注释版
  固定版本与手动运行命令（不默认启用，避免 CI 每次换序）。
  说明：全量随机序会暴露**本票范围之外**的既有耦合（`app.main` 被部分用例 reload 导致
  `TestClient` 指向旧实例、favicon/version 断言失败等），已在 w13-052 的回归记录中如实列出；
  本票验收要求的「一轮随机顺序冒烟」以 8 文件随机序达成。
- **conftest_extended.py**：`from sqlalchemy import create_engine, event` 为**有效导入**
  （`event.listens_for` 在 `test_db` fixture 内注册 PRAGMA），非死代码，未改动。
- **其它顺序/竞态修复**（全量回归暴露后修复，缺一无法两轮全绿）：
  1. 审计批量落库的 5s 定时刷写线程与请求事务共用测试 `StaticPool` 单连接 → 高压下偶发
     `Multi-row INSERT ... did not produce the correct number of INSERTed row`。
     新增 session 级 autouse fixture 把 `_FLUSH_INTERVAL_SECONDS` 拉到 3600s（请求末尾的显式
     flush 仍生效，审计落库断言不变）。
  2. `test_grant_guard_r33` 的“委派给 security.decode_token”用例改为同时 `monkeypatch.setitem`
     `sys.modules['app.core.security']`，避免其它测试 pop/重载模块后补丁与解析对象分叉。
  3. `test_utils_full_coverage::test_get_database_path` 适配每 worker 库文件名（仍精确断言
     「解析 == 运行时 DATABASE_URL」）。
- **全量测试全绿**：
  - 第 1 轮：================ 13929 passed, 1 skipped in 1135.15s
  - 第 2 轮：================ 13929 passed, 1 skipped in 894.17s
