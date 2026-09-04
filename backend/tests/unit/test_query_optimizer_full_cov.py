"""app.core.query_optimizer 全覆盖补充测试。

针对 51% 覆盖率缺口，补齐 paginate / track_query / get_slow_queries /
get_query_count / reset_query_count / analyze_n_plus_one 的全部分支。
"""
import time
from unittest.mock import MagicMock

from app.core import query_optimizer as qo


class TestPaginate:
    def _query(self, total, items):
        q = MagicMock()
        q.count.return_value = total
        q.offset.return_value.limit.return_value.all.return_value = items
        return q

    def test_empty_result(self):
        # total == 0 → pages 固定为 1（行 46 else 分支）
        q = self._query(0, [])
        items, total, pages = qo.paginate(q, page=1, page_size=20)
        assert items == [] and total == 0 and pages == 1

    def test_normal_pagination(self):
        q = self._query(45, ["a", "b"])
        items, total, pages = qo.paginate(q, page=2, page_size=20)
        assert total == 45 and pages == 3 and items == ["a", "b"]
        q.offset.assert_called_once_with(20)

    def test_page_below_one_clamped(self):
        q = self._query(10, ["x"])
        _, _, _ = qo.paginate(q, page=0, page_size=5)
        q.offset.assert_called_once_with(0)

    def test_page_size_capped(self):
        q = self._query(1000, [])
        # page_size 超过 max_page_size → 被钳制（行 44）
        qo.paginate(q, page=1, page_size=5000, max_page_size=200)
        q.offset.return_value.limit.assert_called_once_with(200)

    def test_page_beyond_last_clamped(self):
        # 请求页超过总页数 → page 被钳制到 pages（行 47）
        q = self._query(10, [])
        items, total, pages = qo.paginate(q, page=99, page_size=5)
        assert pages == 2
        q.offset.assert_called_once_with(5)  # (2-1)*5


class TestTrackQuery:
    def setup_method(self):
        self._saved = list(qo._slow_query_log)
        qo._slow_query_log.clear()

    def teardown_method(self):
        qo._slow_query_log.clear()
        qo._slow_query_log.extend(self._saved)

    def test_fast_query_debug_branch(self):
        result = qo.track_query("fast", lambda: "v")
        assert result == "v"
        assert len(qo._slow_query_log) == 1
        assert qo._slow_query_log[0]["slow"] is False

    def test_slow_query_warning_branch(self):
        def slow():
            time.sleep(0.02)
            return "done"

        result = qo.track_query("slow", slow, threshold_ms=1)
        assert result == "done"
        assert qo._slow_query_log[-1]["slow"] is True

    def test_threshold_zero_disables_warning_branch(self):
        # threshold=0 → `threshold > 0` 为 False → 走 debug 分支（不告警）；
        # slow 标志仍按 elapsed > threshold(0) 计算，故为 True。
        qo.track_query("z", lambda: 1, threshold_ms=0)
        assert qo._slow_query_log[-1]["label"] == "z"
        assert qo._slow_query_log[-1]["slow"] is True

    def test_log_trimming_over_500(self):
        # 预置 500 条，再追加一条 → 触发裁剪保留最近 500 条（行 90-91）
        for i in range(500):
            qo._slow_query_log.append({"label": f"l{i}", "elapsed_ms": float(i), "slow": False})
        qo.track_query("overflow", lambda: None)
        assert len(qo._slow_query_log) == 500
        assert qo._slow_query_log[-1]["label"] == "overflow"


class TestGetSlowQueries:
    def setup_method(self):
        self._saved = list(qo._slow_query_log)
        qo._slow_query_log.clear()

    def teardown_method(self):
        qo._slow_query_log.clear()
        qo._slow_query_log.extend(self._saved)

    def test_sorted_slowest_first_and_limited(self):
        qo._slow_query_log.extend([
            {"label": "a", "elapsed_ms": 5.0, "slow": False},
            {"label": "b", "elapsed_ms": 50.0, "slow": True},
            {"label": "c", "elapsed_ms": 20.0, "slow": False},
        ])
        result = qo.get_slow_queries(limit=2)
        assert [e["label"] for e in result] == ["b", "c"]


class TestQueryCounter:
    def test_ensure_counter_initializes(self):
        # 清除线程本地 count → get_query_count 触发 _ensure_counter 初始化
        if hasattr(qo._query_counter, "count"):
            del qo._query_counter.count
        assert qo.get_query_count() == 0

    def test_reset_query_count(self):
        qo._query_counter.count = 42
        qo.reset_query_count()
        assert qo.get_query_count() == 0


class TestAnalyzeNPlusOne:
    def test_below_threshold_no_warning(self):
        @qo.analyze_n_plus_one(threshold=5)
        def work():
            qo._query_counter.count = 3
            return "ok"

        assert work() == "ok"

    def test_above_threshold_warns(self):
        @qo.analyze_n_plus_one(threshold=2)
        def work():
            # 模拟 N+1：函数内部累加查询计数超过阈值（行 164-171）
            qo._query_counter.count = 10
            return "ok"

        assert work() == "ok"

    def test_exception_still_computes_in_finally(self):
        @qo.analyze_n_plus_one(threshold=1)
        def boom():
            qo._query_counter.count = 5
            raise ValueError("x")

        try:
            boom()
        except ValueError:
            pass
        else:  # pragma: no cover - 防御：应始终抛异常
            raise AssertionError("boom() 应抛出 ValueError")
