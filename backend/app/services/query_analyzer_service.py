"""
查询性能分析服务
提供慢查询日志、查询计划分析、N+1查询检测
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """查询性能分析器"""

    def __init__(self):
        self._slow_queries: List[Dict[str, Any]] = []
        self._max_slow_queries = 1000  # 最多保存1000条慢查询
        self._n_plus_one_cache: Dict[str, int] = {}  # N+1查询检测缓存

    def log_slow_query(
        self,
        query: str,
        duration_ms: float,
        params: Optional[Dict] = None,
        explain_plan: Optional[str] = None,
    ):
        """记录慢查询"""
        slow_query = {
            "timestamp": datetime.now().isoformat(),
            "query": query[:500],  # 限制长度
            "duration_ms": round(duration_ms, 2),
            "params": params,
            "explain_plan": explain_plan,
        }

        self._slow_queries.append(slow_query)

        # 限制列表大小
        if len(self._slow_queries) > self._max_slow_queries:
            self._slow_queries = self._slow_queries[-self._max_slow_queries:]

        logger.warning(f"慢查询检测: {duration_ms:.2f}ms - {query[:100]}")

    def get_slow_queries(self, limit: int = 100, min_duration_ms: Optional[float] = None) -> List[Dict[str, Any]]:
        """获取慢查询列表"""
        queries = self._slow_queries

        # 按持续时间过滤
        if min_duration_ms:
            queries = [q for q in queries if q["duration_ms"] >= min_duration_ms]

        # 按时间倒序排序
        queries = sorted(queries, key=lambda x: x["timestamp"], reverse=True)

        return queries[:limit]

    def get_query_stats(self) -> Dict[str, Any]:
        """获取查询统计信息"""
        if not self._slow_queries:
            return {
                "total_slow_queries": 0,
                "avg_duration_ms": 0,
                "max_duration_ms": 0,
                "min_duration_ms": 0,
            }

        durations = [q["duration_ms"] for q in self._slow_queries]

        return {
            "total_slow_queries": len(self._slow_queries),
            "avg_duration_ms": round(sum(durations) / len(durations), 2),
            "max_duration_ms": round(max(durations), 2),
            "min_duration_ms": round(min(durations), 2),
            "p50_duration_ms": self._calculate_percentile(durations, 50),
            "p95_duration_ms": self._calculate_percentile(durations, 95),
            "p99_duration_ms": self._calculate_percentile(durations, 99),
        }

    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """计算百分位数"""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)

        return round(sorted_values[index], 2)

    def detect_n_plus_one(self, query: str, context: str = ""):
        """检测N+1查询问题"""
        # 简化的N+1检测:检测短时间内相似查询的重复执行
        query_signature = self._get_query_signature(query)

        current_time = time.time()
        cache_key = f"{context}:{query_signature}"

        # 清理过期缓存(超过1秒) — 跳过 _count 键
        expired_keys = [k for k, v in self._n_plus_one_cache.items()
                        if not k.endswith("_count") and current_time - v > 1.0]
        for k in expired_keys:
            del self._n_plus_one_cache[k]

        # 检测重复查询
        if cache_key in self._n_plus_one_cache:
            count = self._n_plus_one_cache.get(f"{cache_key}_count", 0) + 1
            self._n_plus_one_cache[f"{cache_key}_count"] = count

            if count > 5:  # 1秒内执行超过5次相似查询
                logger.warning(f"检测到可能的N+1查询: {query[:100]} " f"(在1秒内执行了{count}次)")
        else:
            self._n_plus_one_cache[cache_key] = current_time
            self._n_plus_one_cache[f"{cache_key}_count"] = 1

    def _get_query_signature(self, query: str) -> str:
        """获取查询签名(去除参数值)"""
        # 简化实现:移除数字和引号内容
        import re

        signature = re.sub(r"\d+", "?", query)
        signature = re.sub(r"'[^']*'", "'?'", signature)
        signature = re.sub(r'"[^"]*"', '"?"', signature)
        return signature[:200]

    def analyze_query_plan(self, db: Session, query: str) -> Optional[str]:
        """分析查询计划(仅支持SQLite)"""
        try:
            # SQLite使用EXPLAIN QUERY PLAN
            explain_query = f"EXPLAIN QUERY PLAN {query}"
            result = db.execute(text(explain_query))

            plan_lines = []
            for row in result:
                plan_lines.append(str(row))

            return "\n".join(plan_lines)
        except Exception as e:
            logger.error(f"查询计划分析失败: {e}")
            return None

    def clear_slow_queries(self):
        """清空慢查询记录"""
        self._slow_queries.clear()
        logger.info("慢查询记录已清空")


# 全局查询分析器实例
query_analyzer = QueryAnalyzer()

# 查询性能监控装饰器


# 为测试兼容性添加别名
QueryAnalyzerService = QueryAnalyzer
