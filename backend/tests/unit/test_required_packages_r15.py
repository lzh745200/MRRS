"""R15 运行时依赖登记表回归（2026-09-14 修复"恒报依赖缺失"）。

覆盖 `app/core/required_packages.py`：
- import 名判定（find_spec）与版本尽力而为；
- 三级清单（必需/可选/仅开发）与缺失聚合；
- 冻结运行时（安装包）不给 pip 建议；
- 修复命令：优先 requirements 文件，文件缺失时退化为按分发名安装。
"""

import sys
from unittest.mock import patch

import pytest

from app.core import required_packages as rp


class TestImportability:
    def test_importable_true_for_stdlib_module(self):
        assert rp.is_importable("json") is True

    def test_importable_false_for_bogus_module(self):
        assert rp.is_importable("definitely_not_a_real_module_xyz") is False

    def test_importable_false_when_find_spec_raises(self):
        with patch("app.core.required_packages.importlib_util.find_spec",
                   side_effect=ValueError("broken package")):
            assert rp.is_importable("json") is False

    def test_installed_version_known_and_unknown(self):
        assert rp.installed_version("pytest")  # venv 里必有 pytest
        assert rp.installed_version("definitely-not-installed-xyz") is None

    def test_installed_version_swallows_metadata_errors(self):
        with patch("importlib.metadata.version", side_effect=RuntimeError("boom")):
            assert rp.installed_version("pytest") is None


class TestRegistry:
    def test_runtime_registry_has_core_stack(self):
        names = {dep.distribution for dep in rp.REQUIRED_RUNTIME_PACKAGES}
        assert {"fastapi", "uvicorn", "sqlalchemy", "pandas", "openpyxl"} <= names

    def test_dev_only_packages_are_not_runtime(self):
        """pytest/flake8/bandit 只属开发期 —— 曾因混入运行时清单导致生产恒报缺失。"""
        runtime = {dep.distribution for dep in rp.REQUIRED_RUNTIME_PACKAGES}
        dev = {dep.distribution for dep in rp.DEV_ONLY_PACKAGES}
        assert dev == {"pytest", "flake8", "bandit"}
        assert not (runtime & dev)
        assert "fpdf2" not in runtime | {d.distribution for d in rp.OPTIONAL_RUNTIME_PACKAGES}

    def test_every_registry_entry_targets_existing_requirements_file(self):
        from pathlib import Path

        backend = Path(rp.__file__).resolve().parent.parent.parent
        for dep in rp.REQUIRED_RUNTIME_PACKAGES + rp.OPTIONAL_RUNTIME_PACKAGES + rp.DEV_ONLY_PACKAGES:
            assert (backend / dep.requirements).exists(), f"{dep.distribution} 指向 {dep.requirements} 不存在"

    def test_describe_shape(self):
        items = rp.describe(rp.REQUIRED_RUNTIME_PACKAGES[:2])
        assert len(items) == 2
        first = items[0]
        assert set(first) == {"distribution", "module", "purpose", "requirements", "installed", "version"}
        assert first["installed"] is True and first["version"]

    def test_describe_marks_missing(self):
        dep = rp.Dependency("ghost", "ghost_module_xyz", "幻影依赖")
        items = rp.describe([dep])
        assert items[0]["installed"] is False and items[0]["version"] is None

    def test_missing_helpers(self):
        ghost = rp.Dependency("ghost", "ghost_module_xyz", "幻影依赖")
        with patch.object(rp, "REQUIRED_RUNTIME_PACKAGES", (ghost,)), \
             patch.object(rp, "OPTIONAL_RUNTIME_PACKAGES", ()), \
             patch.object(rp, "DEV_ONLY_PACKAGES", ()):
            assert rp.missing_runtime() == [ghost]
            assert rp.missing_optional() == []
            assert rp.missing_dev() == []
        assert rp.missing(rp.REQUIRED_RUNTIME_PACKAGES) == []


class TestFrozenAndFixCommand:
    def test_is_frozen_false_by_default(self):
        assert rp.is_frozen() is False

    def test_is_frozen_true_when_sys_frozen(self):
        with patch.object(sys, "frozen", True, create=True):
            assert rp.is_frozen() is True

    def test_fix_command_none_without_missing(self):
        assert rp.fix_command([]) is None

    def test_fix_command_none_in_frozen_runtime(self):
        dep = rp.Dependency("pandas", "pandas", "数据分析")
        assert rp.fix_command([dep], frozen=True) is None

    def test_fix_command_uses_requirements_file(self):
        dep = rp.Dependency("pandas", "pandas", "数据分析")
        cmd = rp.fix_command([dep], frozen=False)
        assert cmd and "-m pip install -r" in cmd and "requirements.txt" in cmd

    def test_fix_command_falls_back_to_distribution_names(self):
        dep = rp.Dependency("ghost", "ghost_module_xyz", "幻影依赖", "no_such_requirements.txt")
        cmd = rp.fix_command([dep], frozen=False)
        assert cmd and cmd.endswith("ghost") and "-r" not in cmd

    def test_fix_command_auto_detects_frozen(self):
        dep = rp.Dependency("pandas", "pandas", "数据分析")
        with patch.object(rp, "is_frozen", return_value=True):
            assert rp.fix_command([dep]) is None


@pytest.mark.parametrize("group", ["runtime", "optional", "dev"])
def test_registry_groups_non_empty(group):
    mapping = {
        "runtime": rp.REQUIRED_RUNTIME_PACKAGES,
        "optional": rp.OPTIONAL_RUNTIME_PACKAGES,
        "dev": rp.DEV_ONLY_PACKAGES,
    }
    assert len(mapping[group]) > 0
