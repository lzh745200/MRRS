"""深审 #58：FTS 读路径不得执行 DDL / 提交事务。

原实现 `search_policies_fts` 首行调用 `ensure_fts_table`，在 GET 搜索接口里
可能执行 CREATE VIRTUAL TABLE + INSERT ... SELECT + commit —— 并发读下写锁
竞争、且读请求隐式提交调用方事务。改为只读探测 + LIKE 降级。
"""
from unittest.mock import MagicMock

from app.services import policy_fts_service as fts


class TestSearchReadPathNoDdl:
    def test_like_fallback_without_commit_when_table_missing(self):
        """FTS 表不存在 → 走 LIKE 降级，且全程不 commit。"""
        db = MagicMock()
        missing = MagicMock()
        missing.fetchone.return_value = None
        like_rows = MagicMock()
        like_rows.fetchall.return_value = [
            (7, "乡村政策", "摘要", "关键词", "国家级", "产业", "片段", 0.0),
        ]
        db.execute.side_effect = [missing, like_rows]

        result = fts.search_policies_fts(db, "乡村")

        assert result[0]["id"] == 7
        # 只探测 + 一次 LIKE 查询，无 CREATE / INSERT DDL
        assert db.execute.call_count == 2
        db.commit.assert_not_called()

    def test_no_ddl_sql_emitted_on_read(self):
        """断言读路径发出的 SQL 中不含 CREATE / INSERT。"""
        db = MagicMock()
        missing = MagicMock()
        missing.fetchone.return_value = None
        like_rows = MagicMock()
        like_rows.fetchall.return_value = []
        db.execute.side_effect = [missing, like_rows]

        fts.search_policies_fts(db, "测试")

        emitted = [str(c.args[0]) for c in db.execute.call_args_list]
        assert not any("CREATE" in s.upper() for s in emitted)
        assert not any("INSERT" in s.upper() for s in emitted)

    def test_empty_query_short_circuits_without_db_hit(self):
        db = MagicMock()
        assert fts.search_policies_fts(db, "   ") == []
        db.execute.assert_not_called()

    def test_probe_failure_degrades_to_like(self):
        """探测本身抛异常（库损坏）也要降级而非 500。"""
        db = MagicMock()
        like_rows = MagicMock()
        like_rows.fetchall.return_value = []
        db.execute.side_effect = [RuntimeError("db locked"), like_rows]

        assert fts.search_policies_fts(db, "abc") == []


class TestEnsureFtsTableStillWrites:
    def test_ensure_creates_and_commits_when_missing(self):
        """写路径 ensure_fts_table 仍应建表 + 同步 + commit。"""
        db = MagicMock()
        missing = MagicMock()
        missing.fetchone.return_value = None
        db.execute.side_effect = [missing, MagicMock(), MagicMock()]

        fts.ensure_fts_table(db)

        assert db.execute.call_count == 3

    def test_ensure_early_returns_when_present(self):
        db = MagicMock()
        present = MagicMock()
        present.fetchone.return_value = ("policies_fts",)
        db.execute.side_effect = [present]

        fts.ensure_fts_table(db)

        assert db.execute.call_count == 1
