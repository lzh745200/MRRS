"""进程内业务指标计数器（离线部署，不引入 prometheus 依赖）。

短期项 7「备份 / 日志 / 指标结构化」（2026-11-01 审计路线图）：
原有的 ``middleware/metrics_middleware.py`` 只统计 HTTP 方法/路径/状态码，
运维在机器上无法回答「今天这台机器导出了几次、备份成功几次、导入失败几次」。
这里补一层**业务事件计数**，由 ``GET /api/v1/system/metrics`` 的 ``business``
段落暴露。

约束：
- 完全离线 —— 不引入 prometheus_client 等新依赖，进程内字典即可；
- 线程安全 —— 写入来自线程池（``async_utils.run_in_thread``），用锁保护；
- 进程级、重启归零 —— 这是"本机自启动以来"的口径，不做持久化（持久化会
  给每次写操作增加磁盘 I/O，离线单机场景不值得）。
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Dict

_lock = threading.Lock()
_counters: Dict[str, int] = defaultdict(int)


def incr(event: str) -> None:
    """把事件 ``event`` 的计数加一（空事件名忽略，避免脏键）。"""
    if not event:
        return
    with _lock:
        _counters[event] += 1


def snapshot() -> Dict[str, int]:
    """返回计数快照（按事件名排序，调用方修改返回值不影响内部状态）。"""
    with _lock:
        return dict(sorted(_counters.items()))


def reset() -> None:
    """清空计数（测试与"重置统计"运维动作使用）。"""
    with _lock:
        _counters.clear()
