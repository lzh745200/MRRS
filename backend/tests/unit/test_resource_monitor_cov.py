"""app.services.resource_monitor 覆盖率攻坚测试

覆盖缺口：
- 模块导入时 psutil 缺失的 ImportError 分支（21-24，经 reload + sys.modules 隔离模拟，
  结束后立即二次 reload 还原模块正常状态）
- get_current 的 fallback 采集分支（90）与 _collect_fallback 全方法（194-202）
- check_health 各项超阈值告警（142/144/146）与 critical/warning 状态（149）
- _collect_with_psutil 磁盘采集失败回退系统盘（177-181）与整体异常分支（189-190）
"""

import sys
from unittest.mock import MagicMock, patch

import app.services.resource_monitor as rm
from app.services.resource_monitor import ResourceMonitor, ResourceSnapshot


class TestPsutilImportFallback:
    def test_import_without_psutil(self):
        """psutil 不可导入时模块仍可加载并使用 fallback（21-24）。

        W1 不变量 8: 禁止对 services 子模块 importlib.reload（reload 就地重建
        类对象, 导致跨文件 patch 失效）。导入分支改在子进程中验证, 零模块状态污染。
        """
        import subprocess
        from pathlib import Path

        code = (
            "import sys\n"
            "sys.modules['psutil'] = None\n"
            "import app.services.resource_monitor as m\n"
            "assert m.PSUTIL_AVAILABLE is False and m.psutil is None\n"
            "s = m.ResourceMonitor().get_current()\n"
            "assert s.disk_total > 0\n"
            "print('OK')\n"
        )
        backend_dir = str(Path(__file__).resolve().parents[2])
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"子进程失败:\n{result.stderr}"
        assert "OK" in result.stdout


class TestGetCurrentFallback:
    def test_fallback_when_psutil_unavailable(self):
        monitor = ResourceMonitor()
        with patch.object(rm, "PSUTIL_AVAILABLE", False):
            snapshot = monitor.get_current()  # 90 → _collect_fallback
        assert snapshot.timestamp > 0
        assert snapshot.disk_total > 0
        assert 0 <= snapshot.disk_percent <= 100

    def test_fallback_disk_error_swallowed(self):
        monitor = ResourceMonitor()
        with patch.object(rm, "PSUTIL_AVAILABLE", False):
            with patch("shutil.disk_usage", side_effect=OSError("no disk")):
                snapshot = monitor.get_current()  # 201-202
        # 采集失败时保留默认值，不向外抛
        assert snapshot.disk_total == 0
        assert snapshot.disk_percent == 0.0


class TestCheckHealthThresholds:
    def test_critical_when_all_high(self):
        monitor = ResourceMonitor()
        snap = ResourceSnapshot(timestamp=1.0, cpu_percent=99.0, memory_percent=96.0, disk_percent=97.0)
        with patch.object(monitor, "get_current", return_value=snap):
            health = monitor.check_health()  # 142/144/146/149
        assert health["status"] == "critical"
        assert len(health["warnings"]) == 3
        assert any("CPU" in w for w in health["warnings"])
        assert any("内存" in w for w in health["warnings"])
        assert any("磁盘" in w for w in health["warnings"])
        assert health["snapshot"]["cpu"]["percent"] == 99.0

    def test_warning_when_only_cpu_high(self):
        monitor = ResourceMonitor()
        snap = ResourceSnapshot(timestamp=1.0, cpu_percent=98.0, memory_percent=50.0, disk_percent=50.0)
        with patch.object(monitor, "get_current", return_value=snap):
            health = monitor.check_health()  # 149 的 warning 分支
        assert health["status"] == "warning"
        assert len(health["warnings"]) == 1

    def test_healthy_when_all_low(self):
        monitor = ResourceMonitor()
        snap = ResourceSnapshot(timestamp=1.0, cpu_percent=10.0, memory_percent=40.0, disk_percent=60.0)
        with patch.object(monitor, "get_current", return_value=snap):
            health = monitor.check_health()  # 151 healthy 分支（确定性，不依赖宿主机状态）
        assert health["status"] == "healthy"
        assert health["warnings"] == []


class TestCollectWithPsutilEdgeCases:
    def _fake_psutil(self, **overrides):
        fake = MagicMock()
        fake.cpu_percent.return_value = 12.5
        fake.virtual_memory.return_value = MagicMock(total=1024**3, used=512 * 1024**2, percent=50.0)
        fake.disk_usage.return_value = MagicMock(total=1000, used=500, percent=50.0)
        fake.pids.return_value = [1, 2, 3]
        proc = MagicMock()
        proc.memory_info.return_value = MagicMock(rss=128 * 1024 * 1024)
        fake.Process.return_value = proc
        for attr, val in overrides.items():
            setattr(fake, attr, val)
        return fake

    def test_disk_failure_falls_back_to_system_drive(self):
        monitor = ResourceMonitor()
        usage = MagicMock(total=1000, used=500, percent=50.0)
        fake = self._fake_psutil()
        fake.disk_usage.side_effect = [OSError("cwd gone"), usage]
        with patch.object(rm, "psutil", fake):
            snapshot = monitor.get_current()  # 177-181
        assert fake.disk_usage.call_count == 2
        assert snapshot.disk_total == 1000
        assert snapshot.disk_used == 500
        assert snapshot.disk_percent == 50.0
        # 其余字段走正常采集
        assert snapshot.cpu_percent == 12.5
        assert snapshot.memory_percent == 50.0
        assert snapshot.process_count == 3
        assert snapshot.python_memory_mb == 128.0

    def test_psutil_failure_logged_and_defaults_kept(self):
        monitor = ResourceMonitor()
        fake = self._fake_psutil()
        fake.cpu_percent.side_effect = RuntimeError("psutil boom")
        with patch.object(rm, "psutil", fake):
            snapshot = monitor.get_current()  # 189-190
        # 采集整体失败时保留默认值，不向外抛
        assert snapshot.cpu_percent == 0.0
        assert snapshot.memory_total == 0
