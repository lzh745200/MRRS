"""W2-T6 回归：计数器读-改-写竞态原子化。

历史缺陷：view/download_count、failed_login_count 用 Python 读加一写回，
WAL 并发下丢更新（锁定计数少计=安全弱化）。
"""


class TestPolicyCountersAtomic:
    def test_download_count_uses_sql_increment(self):
        """下载计数必须走 UPDATE x=x+1 原子形式。"""
        from app.api.v1 import policy as policy_api
        import inspect

        src = inspect.getsource(policy_api.download_policy_file)
        assert "download_count + 1" not in src and "download_count +1" not in src, (
            "仍存在读-改-写模式"
        )
        assert "download_count = download_count" in src or "update(" in src.lower(), (
            "未找到 SQL 原子递增"
        )

    def test_view_count_uses_sql_increment(self):
        from app.api.v1 import policy as policy_api
        import inspect

        for fn_name in ("view_policy", "increment_view_count"):
            fn = getattr(policy_api, fn_name, None)
            if fn is None:
                continue
            src = inspect.getsource(fn)
            assert "view_count + 1" not in src, f"{fn_name} 仍为读-改-写"


class TestAuthCounterAtomic:
    def test_failed_login_count_increment_atomic(self):
        """auth.py:82 的 failed_login_count 必须原子化或经 lockout_service。"""
        import inspect
        from app.api.v1.auth import auth as auth_api

        src = inspect.getsource(auth_api)
        # 禁止直接 Python 递增赋值（允许 lockout_service 内部实现迁移后删除此断言）
        bad = "failed_login_count = (user.failed_login_count or 0) + 1"
        assert bad not in src, "auth.py 仍在用读-改-写更新 failed_login_count"


class TestLockoutServiceAtomic:
    def test_record_failed_uses_sql_increment(self):
        """record_failed 应使用 UPDATE 原子递增（禁止读-改-写）。"""
        import inspect
        from app.services import lockout_service

        src = inspect.getsource(lockout_service.LockoutService.record_failed)
        assert "failed_login_count=failed_count" not in src, "仍为读-改-写"
        ok = (
            "failed_login_count + :inc" in src
            or "failed_login_count + 1" in src
            or "coalesce(User.failed_login_count, 0) + 1" in src
        )
        assert ok, "未找到 SQL 原子递增"
