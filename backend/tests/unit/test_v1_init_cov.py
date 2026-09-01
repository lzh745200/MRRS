"""app.api.v1 静态导入架构测试（v1.11.3 Kylin 403 事故回归锁）

事故：业务模块经 f-string 动态 importlib 加载，PyInstaller 静态分析不可见，
冻结包缺 organization/policy/projects 等 47 个模块 → 后端"部分启动"、
前端业务页面全量报错。

锁定的新契约：
1. 47 个业务模块全部静态导入并注册（数量锁，防菜单键漂移式回退）
2. 注册顺序不变量：supported_village_export 先于 supported_village
3. 快速失败：任一路由模块导入失败 → 启动中止（禁止静默降级）
4. 禁止回退到动态 importlib 加载
"""

import importlib
import sys

import pytest

PKG = "app.api.v1"

EXPECTED_BUSINESS_MODULE_COUNT = 47


def _fresh_pkg():
    import app.api.v1 as v1_pkg

    importlib.reload(v1_pkg)
    return v1_pkg


def test_all_business_modules_statically_registered():
    """47 个业务模块全部静态导入且带 router（数量锁）"""
    pkg = _fresh_pkg()
    assert len(pkg._BUSINESS_MODULES) == EXPECTED_BUSINESS_MODULE_COUNT
    for mod in pkg._BUSINESS_MODULES:
        assert hasattr(mod, "router"), f"{mod.__name__} 缺少 router"
    # 回归阈值：全量路由数（曾因动态导入丢失 47 模块 → 路由数骤减）
    assert len(pkg.api_v1_router.routes) >= 700


def test_export_route_registered_before_dynamic_route():
    """顺序不变量：静态导出路由必须先于 /{village_id} 动态路由注册"""
    pkg = _fresh_pkg()
    paths = [r.path for r in pkg.api_v1_router.routes]
    export_idx = next(
        i for i, p in enumerate(paths)
        if "supported-villages" in p and p.endswith("/export")
    )
    dynamic_idx = paths.index("/api/v1/supported-villages/{village_id}")
    assert export_idx < dynamic_idx, "静态导出路由被动态路由遮蔽 → /export 422"


def test_broken_module_fails_fast(monkeypatch):
    """任一业务模块导入失败 → reload 直接抛 ImportError（快速失败，不静默降级）"""
    import app.api.v1 as v1_pkg

    with monkeypatch.context() as mp:
        # reload 会复用旧模块对象的属性，须同时删属性 + 注入 sys.modules
        mp.delattr(v1_pkg, "funds", raising=False)
        mp.setitem(sys.modules, f"{PKG}.funds", None)  # None → ImportError
        with pytest.raises(ImportError):
            importlib.reload(v1_pkg)
    # 恢复真实路由，避免污染同会话后续测试
    pkg = _fresh_pkg()
    assert len(pkg._BUSINESS_MODULES) == EXPECTED_BUSINESS_MODULE_COUNT


def test_no_dynamic_import_regression():
    """禁止回退到动态 importlib 加载（PyInstaller 打包缺失的事故根因）"""
    import ast
    import inspect

    import app.api.v1 as v1_pkg

    # 剥离文档字符串/普通字符串后只检查可执行代码（说明文字允许提及历史）
    tree = ast.parse(inspect.getsource(v1_pkg))
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    bad_imports = [
        n for n in imports
        if (isinstance(n, ast.Import) and any("importlib" in a.name for a in n.names))
        or (isinstance(n, ast.ImportFrom) and n.module == "importlib")
    ]
    assert not bad_imports, "出现动态 importlib 加载——将复现冻结包业务模块缺失事故"
    tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)]
    assert not tries, "出现异常吞噬（try/except）——违反快速失败契约"
