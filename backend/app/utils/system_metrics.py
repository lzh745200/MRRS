"""
系统资源监控

提供CPU、内存、磁盘等系统资源监控指标

prometheus_client 是可选依赖，完全延迟导入，确保在 PyInstaller
打包环境中缺失 prometheus_client 时模块仍可正常加载。
"""

import logging
import os
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# prometheus_client 延迟加载
_PROMETHEUS_AVAILABLE = False
_Gauge: Any = None

# 指标变量（延迟初始化）
system_cpu_usage_percent: Any = None
process_cpu_usage_percent: Any = None
system_memory_total_bytes: Any = None
system_memory_available_bytes: Any = None
system_memory_usage_percent: Any = None
process_memory_rss_bytes: Any = None
process_memory_vms_bytes: Any = None
system_disk_total_bytes: Any = None
system_disk_used_bytes: Any = None
system_disk_usage_percent: Any = None
process_open_fds: Any = None
process_threads: Any = None


def _ensure_prometheus():
    """延迟初始化 prometheus_client 指标"""
    global _PROMETHEUS_AVAILABLE, _Gauge
    global system_cpu_usage_percent, process_cpu_usage_percent
    global system_memory_total_bytes, system_memory_available_bytes, system_memory_usage_percent
    global process_memory_rss_bytes, process_memory_vms_bytes
    global system_disk_total_bytes, system_disk_used_bytes, system_disk_usage_percent
    global process_open_fds, process_threads

    if _PROMETHEUS_AVAILABLE:
        return True

    try:
        from prometheus_client import Gauge, REGISTRY
        _Gauge = Gauge

        def _safe_gauge(name: str, desc: str, *labels):
            """幂等注册：模块被 reload/多次导入时先注销同名旧采集器。

            修复 xdist 单 worker 内跨测试文件重复导入导致的
            "Duplicated timeseries in CollectorRegistry"（CI nightly 实测）。
            """
            try:
                existing = REGISTRY._names_to_collectors.get(name)
                if existing is not None:
                    REGISTRY.unregister(existing)
            except Exception:
                pass
            return Gauge(name, desc, *labels)

        system_cpu_usage_percent = _safe_gauge("system_cpu_usage_percent", "System CPU usage percentage")
        process_cpu_usage_percent = _safe_gauge("process_cpu_usage_percent", "Process CPU usage percentage")
        system_memory_total_bytes = _safe_gauge("system_memory_total_bytes", "Total system memory in bytes")
        system_memory_available_bytes = _safe_gauge("system_memory_available_bytes", "Available system memory in bytes")
        system_memory_usage_percent = _safe_gauge("system_memory_usage_percent", "System memory usage percentage")
        process_memory_rss_bytes = _safe_gauge("process_memory_rss_bytes", "Process resident memory size in bytes")
        process_memory_vms_bytes = _safe_gauge("process_memory_vms_bytes", "Process virtual memory size in bytes")
        system_disk_total_bytes = _safe_gauge("system_disk_total_bytes", "Total disk space in bytes", ["path"])
        system_disk_used_bytes = _safe_gauge("system_disk_used_bytes", "Used disk space in bytes", ["path"])
        system_disk_usage_percent = _safe_gauge("system_disk_usage_percent", "Disk usage percentage", ["path"])
        process_open_fds = _safe_gauge("process_open_fds", "Number of open file descriptors")
        process_threads = _safe_gauge("process_threads", "Number of threads")

        _PROMETHEUS_AVAILABLE = True
        return True
    except ImportError:  # pragma: no cover
        _PROMETHEUS_AVAILABLE = False
        return False


class SystemMetrics:
    """系统资源指标收集器"""

    def __init__(self, process=None):
        """
        初始化系统指标收集器。

        Args:
            process: 可选的 psutil.Process 实例，用于测试注入 mock。
        """
        self.process = process if process is not None else psutil.Process()
        _ensure_prometheus()  # 初始化 prometheus 指标

    def collect_all(self):
        """收集所有系统指标"""
        try:
            self.collect_cpu_metrics()
            self.collect_memory_metrics()
            self.collect_disk_metrics()
            self.collect_process_metrics()
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}", exc_info=True)

    def collect_cpu_metrics(self):
        """收集CPU指标"""
        if not _PROMETHEUS_AVAILABLE:
            return
        try:
            # 系统CPU使用率
            system_cpu = psutil.cpu_percent(interval=0.1)
            system_cpu_usage_percent.set(system_cpu)

            # 进程CPU使用率
            process_cpu = self.process.cpu_percent(interval=0.1)
            process_cpu_usage_percent.set(process_cpu)
        except Exception as e:
            logger.error(f"Failed to collect CPU metrics: {e}")

    def collect_memory_metrics(self):
        """收集内存指标"""
        if not _PROMETHEUS_AVAILABLE:
            return
        try:
            # 系统内存
            mem = psutil.virtual_memory()
            system_memory_total_bytes.set(mem.total)
            system_memory_available_bytes.set(mem.available)
            system_memory_usage_percent.set(mem.percent)

            # 进程内存
            process_mem = self.process.memory_info()
            process_memory_rss_bytes.set(process_mem.rss)
            process_memory_vms_bytes.set(process_mem.vms)
        except Exception as e:
            logger.error(f"Failed to collect memory metrics: {e}")

    def collect_disk_metrics(self, paths: list = None):
        """
        收集磁盘指标

        Args:
            paths: 要监控的磁盘路径列表，默认监控根目录
        """
        if not _PROMETHEUS_AVAILABLE:
            return
        if paths is None:
            paths = [os.environ.get("SystemDrive", "C:\\")]

        try:
            for path in paths:
                try:
                    usage = psutil.disk_usage(path)
                    system_disk_total_bytes.labels(path=path).set(usage.total)
                    system_disk_used_bytes.labels(path=path).set(usage.used)
                    system_disk_usage_percent.labels(path=path).set(usage.percent)
                except Exception as e:
                    logger.warning(f"Failed to collect disk metrics for {path}: {e}")
        except Exception as e:
            logger.error(f"Failed to collect disk metrics: {e}")

    def collect_process_metrics(self):
        """收集进程指标"""
        if not _PROMETHEUS_AVAILABLE:
            return
        try:
            # 文件描述符数量（仅Unix系统）
            try:
                num_fds = self.process.num_fds()
                process_open_fds.set(num_fds)
            except (AttributeError, NotImplementedError):
                # Windows系统不支持num_fds
                pass

            # 线程数量
            num_threads = self.process.num_threads()
            process_threads.set(num_threads)
        except Exception as e:
            logger.error(f"Failed to collect process metrics: {e}")


# 全局系统指标实例
_system_metrics = None


def get_system_metrics() -> SystemMetrics:
    """获取系统指标实例（单例）"""
    global _system_metrics
    if _system_metrics is None:
        _system_metrics = SystemMetrics()
    return _system_metrics
