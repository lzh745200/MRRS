"""ResourceLimiter.ensure_quota / check_rate_limit 限流生效性回归测试。

背景（系统全面排查报告 2026-10-14 M22）：
`check_rate_limit` 旧实现每次都先 `set_quota`，而 `set_quota` 内部会清空
`_request_counts[key]` —— 紧接着的 `is_allowed` 永远看到空历史，
**限流因此从不生效**（第 N 次调用也永远放行）。

本文件用真实实例（不 mock）证明：
1. 同一 key 连续调用超过限额后必须被拒绝；
2. `ensure_quota` 幂等（参数未变不重置窗口）；
3. 参数变化时才重置窗口（保留 set_quota 原本"调低配额不被旧记录误拒"的语义）。
"""

import pytest

from app.services.resource_limiter import ResourceLimiter, check_rate_limit


@pytest.fixture
def limiter():
    return ResourceLimiter()


class TestCheckRateLimitActuallyLimits:
    def test_enforces_after_limit_exceeded(self):
        """同一 key 超过限额后必须被拒（旧实现第 N 次仍返回 True）。"""
        key = "rl-m22-enforce"
        assert check_rate_limit(key, limit=2, window=60) is True
        assert check_rate_limit(key, limit=2, window=60) is True
        assert check_rate_limit(key, limit=2, window=60) is False
        assert check_rate_limit(key, limit=2, window=60) is False

    def test_different_keys_are_independent(self):
        assert check_rate_limit("rl-m22-a", limit=1, window=60) is True
        assert check_rate_limit("rl-m22-a", limit=1, window=60) is False
        assert check_rate_limit("rl-m22-b", limit=1, window=60) is True

    def test_usage_stats_counts_denials(self, limiter):
        key = "rl-m22-stats"
        limiter.ensure_quota(key, 1, 60)
        assert limiter.is_allowed(key) is True
        assert limiter.is_allowed(key) is False
        stats = limiter.get_usage_stats(key)
        assert stats.total_requests == 2
        assert stats.allowed_requests == 1
        assert stats.denied_requests == 1


class TestEnsureQuota:
    def test_idempotent_when_params_unchanged(self, limiter):
        """参数未变 → 返回 False，且**不重置**请求窗口（这是修 bug 的关键语义）。"""
        key = "rl-m22-idem"
        assert limiter.ensure_quota(key, 2, 60) is True
        assert limiter.is_allowed(key) is True          # 窗口内第 1 次
        assert limiter.ensure_quota(key, 2, 60) is False  # 幂等：不清空计数
        assert limiter.is_allowed(key) is True          # 第 2 次
        assert limiter.is_allowed(key) is False         # 第 3 次超限
        # 若 ensure_quota 误清空窗口，这里会重新变 True
        assert limiter.is_allowed(key) is False

    def test_resets_window_when_params_change(self, limiter):
        """参数变化 → 返回 True 并重置窗口（保留 set_quota 原语义）。"""
        key = "rl-m22-change"
        limiter.ensure_quota(key, 2, 60)
        limiter.is_allowed(key)
        limiter.is_allowed(key)
        assert limiter.is_allowed(key) is False         # 已满
        # 调低配额：窗口被重置，且新配额立即生效
        assert limiter.ensure_quota(key, 1, 60) is True
        assert limiter.is_allowed(key) is True          # 重置后放行 1 次
        assert limiter.is_allowed(key) is False         # 新配额=1，立即超限

    def test_first_registration_returns_true(self, limiter):
        assert limiter.ensure_quota("rl-m22-first", 5, 60) is True
        assert limiter.ensure_quota("rl-m22-first", 5, 60) is False

    def test_set_quota_still_resets_window(self, limiter):
        """`set_quota` 的既有语义（无条件重置）不得被改变。"""
        key = "rl-m22-setquota"
        limiter.ensure_quota(key, 2, 60)
        limiter.is_allowed(key)
        limiter.is_allowed(key)
        assert limiter.is_allowed(key) is False
        limiter.set_quota(key, 2, 60)                   # 无条件重置
        assert limiter.is_allowed(key) is True
