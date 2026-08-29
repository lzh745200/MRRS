"""
资源限制器服务

提供限流和资源配额管理功能
"""

from dataclasses import dataclass, field
from typing import Dict
from datetime import datetime, timezone
import threading
import time


@dataclass
class RateLimit:
    """速率限制配置"""

    requests: int
    window: int  # seconds


@dataclass
class ResourceQuota:
    """资源配额配置"""

    max_requests: int
    period: int  # seconds
    current_usage: int = 0


@dataclass
class UsageStats:
    """使用统计"""

    total_requests: int = 0
    allowed_requests: int = 0
    denied_requests: int = 0
    last_reset: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ResourceLimiter:
    """
    资源限制器

    管理请求速率限制和资源配额
    """

    def __init__(self):
        self._rate_limits: Dict[str, RateLimit] = {}
        self._quotas: Dict[str, ResourceQuota] = {}
        self._usage: Dict[str, UsageStats] = {}
        self._request_counts: Dict[str, list] = {}
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_thread = None

    def start_monitoring(self):
        """启动资源监控（兼容接口）"""
        self._monitoring = True

    def stop_monitoring(self):
        """停止资源监控（兼容接口）"""
        self._monitoring = False

    def is_allowed(self, key: str) -> bool:
        """
        检查是否允许请求

        Args:
            key: 限制键

        Returns:
            bool: 是否允许
        """
        with self._lock:
            now = time.time()

            # 初始化请求计数
            if key not in self._request_counts:
                self._request_counts[key] = []

            # 清理过期的请求记录
            if key in self._rate_limits:
                limit = self._rate_limits[key]
                cutoff = now - limit.window
                self._request_counts[key] = [t for t in self._request_counts[key] if t > cutoff]

                # 检查是否超过限制
                if len(self._request_counts[key]) >= limit.requests:
                    self._update_usage(key, allowed=False)
                    return False

            # 记录请求
            self._request_counts[key].append(now)
            self._update_usage(key, allowed=True)
            return True

    def get_usage_stats(self, key: str) -> UsageStats:
        """
        获取使用统计

        Args:
            key: 限制键

        Returns:
            UsageStats: 使用统计
        """
        with self._lock:
            return self._usage.get(key, UsageStats())

    def set_quota(self, key: str, max_requests: int, period: int):
        """
        设置配额

        Args:
            key: 限制键
            max_requests: 最大请求数
            period: 时间周期（秒）
        """
        with self._lock:
            self._quotas[key] = ResourceQuota(max_requests=max_requests, period=period)
            self._rate_limits[key] = RateLimit(requests=max_requests, window=period)

    def clear_quota(self, key: str):
        """
        清除配额

        Args:
            key: 限制键
        """
        with self._lock:
            self._quotas.pop(key, None)
            self._rate_limits.pop(key, None)
            self._request_counts.pop(key, None)
            self._usage.pop(key, None)

    def _update_usage(self, key: str, allowed: bool):
        """更新使用统计"""
        if key not in self._usage:
            self._usage[key] = UsageStats()

        stats = self._usage[key]
        stats.total_requests += 1
        if allowed:
            stats.allowed_requests += 1
        else:
            stats.denied_requests += 1


# 全局限制器实例
_rate_limiter = ResourceLimiter()


def check_rate_limit(key: str, limit: int, window: int) -> bool:
    """
    检查速率限制

    Args:
        key: 限制键
        limit: 限制数量
        window: 时间窗口（秒）

    Returns:
        bool: 是否允许
    """
    _rate_limiter.set_quota(key, limit, window)
    return _rate_limiter.is_allowed(key)


# 全局导出实例
resource_limiter = _rate_limiter
