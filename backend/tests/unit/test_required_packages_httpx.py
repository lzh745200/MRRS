"""httpx 必须登记为「运行时必需」依赖（启动期硬依赖）。

背景：`app/services/alert_service.py` 在模块顶层 `import httpx`，该模块经
`services/monitoring_service.py` → `api/v1/monitoring_legacy.py` → `api/v1/__init__.py`
在**启动期**被导入。此前 httpx 只出现在 `requirements.txt`，未登记进
`app/core/required_packages.py` 的运行时必需清单 → 缺失时启动自检不告警。
"""

import sys
from pathlib import Path

from app.core.required_packages import (
    REQUIRED_RUNTIME_PACKAGES,
    is_importable,
    missing_runtime,
)

_BACKEND_DIR = Path(__file__).resolve().parents[2]


class TestHttpxRegisteredAsRequiredRuntime:
    def test_httpx_in_required_runtime_packages(self):
        by_module = {dep.module: dep for dep in REQUIRED_RUNTIME_PACKAGES}

        assert "httpx" in by_module, "httpx 必须在运行时必需清单中（启动期顶层 import）"

    def test_httpx_distribution_and_requirements_file(self):
        dep = next(d for d in REQUIRED_RUNTIME_PACKAGES if d.module == "httpx")

        assert dep.distribution == "httpx"
        assert dep.requirements == "requirements.txt"
        assert dep.purpose  # 用途非空，便于启动告警定位

    def test_requirements_txt_lists_same_distribution(self):
        """依赖清单单一事实源：登记表里的分发名必须在 requirements.txt 出现。"""
        dep = next(d for d in REQUIRED_RUNTIME_PACKAGES if d.module == "httpx")
        requirements = (_BACKEND_DIR / dep.requirements).read_text(encoding="utf-8")

        assert dep.distribution in requirements

    def test_httpx_not_reported_missing_when_importable(self):
        """本环境已安装 httpx → 运行时缺失清单不得包含它。"""
        if not is_importable("httpx"):  # pragma: no cover - 依赖环境
            import pytest

            pytest.skip("当前环境未安装 httpx")

        assert "httpx" not in {dep.module for dep in missing_runtime()}

    def test_alert_service_imports_httpx_at_startup(self):
        """回归：alert_service 顶层 import 是 httpx 成为启动期硬依赖的根因。"""
        import app.services.alert_service  # noqa: F401  （触发导入）

        assert "httpx" in sys.modules
