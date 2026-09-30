# -*- coding: utf-8 -*-
"""app.api.v1.system 包 __init__ 覆盖率攻坚测试

__init__.py 对 18 个子路由做 try/import+include_router / except 结构：
- 正常执行：覆盖全部 try 分支（import + include_router + logger.debug）
- 子模块导入失败：覆盖全部 18 对 except 分支（logger.warning）

做法：用 spec_from_file_location 以独立模块名重复执行同一个 __init__.py
（不污染已加载的 app.api.v1.system 包对象），配合
patch.dict(sys.modules, {子模块: None}) 使 from-import 抛 ImportError。
"""

import importlib.util
import os
import sys
from unittest.mock import patch

import pytest

import app.api.v1.system as pkg

SUBMODULES = [
    "admin", "audit", "backup", "cache", "config_package", "env",
    "error_report", "health", "help", "i18n", "init", "metrics",
    "monitor", "system", "system_config", "tasks", "update_logs", "zero_trust",
]

INIT_PATH = os.path.join(os.path.dirname(pkg.__file__), "__init__.py")


def _exec_fresh(name):
    """以独立模块名重新执行 __init__.py，返回新模块对象"""
    spec = importlib.util.spec_from_file_location(name, INIT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_package_init_loads_all_subrouters():
    """正常路径：18 个子路由全部 import 成功并 include"""
    mod = _exec_fresh("system_pkg_init_a26_ok")
    assert mod.router is not None
    assert mod.__all__ == ["router"]
    # 每个子模块至少贡献一条路由
    assert len(mod.router.routes) >= len(SUBMODULES)


def test_package_init_fails_fast_on_submodule_import_failure():
    """异常路径（深审 #78 改写）：子模块导入失败必须 fail-fast。

    原实现把 import 与 include_router 一起包在 try 里，失败只记 warning ——
    端点静默缺失（审计/零信任/备份路由缺失时无人察觉）且原始栈被吞掉。
    现改为：导入失败即 RuntimeError（带模块名与原始异常链），不再挂载任何子路由。
    """
    broken = {f"app.api.v1.system.{name}": None for name in SUBMODULES}
    with patch.dict(sys.modules, broken):
        with pytest.raises(RuntimeError) as exc_info:
            _exec_fresh("system_pkg_init_a26_broken")
    assert "加载 system.admin 路由失败" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, ImportError)
