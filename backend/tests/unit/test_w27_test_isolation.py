"""W27 第 12 轮回归：**测试隔离**——回滚 `sys.modules` 里的模块替身污染。

## 为什么需要
W27 第 9~11 轮的单进程全量跑反复出现"无关用例莫名变红、且每次换一个文件"：

```
Expected 'commit' to have been called once. Called 2 times.
```

单跑与整文件跑均全绿。已定位机制：某些用例直接
`sys.modules["app.services.lockout_service"] = MagicMock(...)` 模拟"模块不可用"，
teardown 没还原 → 后续用例的 `patch("app.services.lockout_service.get_lockout_service")`
打到**替身**上，真实服务照常执行并多提交一次。

`tests/conftest.py::_rollback_app_module_swaps`（autouse）负责在用例结束后把
被替换成 Mock 或被删除的 `app.*` 模块还原。

## 本文件锁定
1. 污染被还原（**跨用例**验证：本文件前一个用例故意污染，后一个用例断言已还原）；
2. 正常用例不产生误报（不触发还原路径）；
3. `@pytest.mark.allow_module_swap` 可显式豁免（用于确需跨用例保留的场景）；
4. 判定函数只认 `unittest.mock` 对象，不误伤真实模块。
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

TARGET = "app.services.lockout_service"


class TestRollbackAcrossCases:
    """用例顺序有意义：本类的第一个用例制造污染，第二个用例验证已被清理。"""

    def test_1_pollutes_sys_modules(self):
        """故意把模块换成 Mock（模拟历史用例的不当写法）。"""
        import app.services.lockout_service as real

        assert isinstance(real, ModuleType)
        sys.modules[TARGET] = MagicMock(name="polluted-lockout-service")

        # 在本用例内确实被污染了
        assert not isinstance(sys.modules[TARGET], ModuleType)

    def test_2_pollution_was_rolled_back(self):
        """上一个用例留下的 Mock 替身必须被清掉。

        语义：夹具对"用例内首次导入后又被替换"的模块采用**删除键**（而不是伪造一个
        新模块对象）—— 这样下次 `import` 会正常重新加载真实模块，等价于干净状态。
        绝不允许把 Mock 留在 sys.modules 里被后续用例误用。
        """
        import importlib

        current = sys.modules.get(TARGET)
        assert not isinstance(current, MagicMock), (
            f"Mock 替身残留：{type(current)}"
        )
        # 触发（重新）加载后必须是真实模块且具备真实属性
        mod = importlib.import_module(TARGET)
        assert isinstance(mod, ModuleType)
        assert callable(getattr(mod, "get_lockout_service", None))
        assert isinstance(sys.modules[TARGET], ModuleType)

    def test_3_deleted_module_is_cleaned(self):
        """删除 app.* 模块同样是污染形态，夹具必须保证不留下"半删除"状态。"""
        import app.services.lockout_service as real

        original = sys.modules.pop(TARGET)
        assert original is real
        assert TARGET not in sys.modules

    def test_4_deletion_was_rolled_back(self):
        """上一个用例删除后，夹具不应把 Mock/残缺对象留在 sys.modules。"""
        import importlib

        current = sys.modules.get(TARGET)
        assert not isinstance(current, MagicMock)
        mod = importlib.import_module(TARGET)
        assert isinstance(mod, ModuleType)


class TestNoFalsePositive:
    def test_normal_test_does_not_trigger_restore(self):
        """不动 sys.modules 的用例不应被夹具干预。"""
        import app.services.lockout_service as real

        assert sys.modules[TARGET] is real
        assert isinstance(real, ModuleType)


class TestHelper:
    def test_is_mock_object_recognises_mocks(self):
        from tests.conftest import _is_mock_object

        assert _is_mock_object(MagicMock()) is True
        assert _is_mock_object(ModuleType("x")) is False
        assert _is_mock_object(object()) is False
        assert _is_mock_object(None) is False

    def test_marker_is_registered(self):
        """`--strict-markers` 下未注册的 marker 会让收集失败，故必须登记。"""
        import pathlib

        ini = pathlib.Path(__file__).resolve().parents[2] / "pytest.ini"
        text = ini.read_text(encoding="utf-8")
        assert "allow_module_swap" in text


class TestOptOut:
    @pytest.mark.allow_module_swap
    def test_marked_case_may_keep_swap_and_cleans_up_itself(self):
        """打标记的用例不会被强制还原 —— 用例自行清理（避免真的污染会话）。"""
        import app.services.lockout_service as real

        sys.modules[TARGET] = MagicMock(name="opt-out")
        try:
            assert not isinstance(sys.modules[TARGET], ModuleType)
        finally:
            sys.modules[TARGET] = real
        assert isinstance(sys.modules[TARGET], ModuleType)
