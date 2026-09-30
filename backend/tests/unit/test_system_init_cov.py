"""app.api.v1.system.__init__ 覆盖率攻坚测试

18 个子路由的 try/import + fail-fast 结构：
- 正常路径：18 个子模块全部 import 成功（已被全量套件覆盖）
- 异常路径（本文件）：sys.modules 注入 None 使 import 失败 → RuntimeError
  （深审 #78 改写：原实现只记 warning 并静默丢端点，现为 fail-fast，
  首个失败子模块即抛出，异常链保留原始 ImportError）
"""

import importlib
import sys
from unittest.mock import patch

import pytest

SUBMODULES = [
    "admin", "audit", "backup", "cache", "config_package", "env",
    "error_report", "health", "help", "i18n", "init", "metrics",
    "monitor", "system", "system_config", "tasks", "update_logs", "zero_trust",
]


def test_submodule_import_failure_is_fatal():
    """深审 #78：任一子路由导入失败都必须让包加载失败（不再静默降级）。"""
    import app.api.v1.system as system_pkg

    injected = {f"app.api.v1.system.{name}": None for name in SUBMODULES}
    with patch.dict(sys.modules, injected):
        with pytest.raises(RuntimeError) as exc_info:
            importlib.reload(system_pkg)
    assert "加载 system.admin 路由失败" in str(exc_info.value)

    # 恢复真实现（patch.dict 已还原 sys.modules，重新 reload 回正常路由）
    importlib.reload(system_pkg)
    assert len(system_pkg.router.routes) > 0


@pytest.mark.parametrize("name", [n for n in SUBMODULES if n != "admin"])
def test_each_submodule_failure_is_fatal(name):
    """逐个把子路由替换为不可导入，确认其 except 分支 fail-fast 且报出模块名。

    必须先放行排在目标之前的子模块（否则会被更早的失败抢先抛出），
    因此这里只把目标子模块设为 None，其余保持真实实现。
    """
    import app.api.v1.system as system_pkg

    with patch.dict(sys.modules, {f"app.api.v1.system.{name}": None}):
        with pytest.raises(RuntimeError) as exc_info:
            importlib.reload(system_pkg)
    assert f"加载 system.{name} 路由失败" in str(exc_info.value)

    # 还原真实现，避免污染同 worker 的后续用例
    importlib.reload(system_pkg)


def test_normal_reload_registers_routers():
    """正常路径：全部子路由注册成功（防御 reload 后状态完好）"""
    import app.api.v1.system as system_pkg

    importlib.reload(system_pkg)
    assert len(system_pkg.router.routes) > 0
