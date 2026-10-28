# -*- coding: utf-8 -*-
"""静默吞异常门禁的判定语义回归。

门禁只锁一件事：`except Exception` 必须**留痕或显式豁免**。本文件用最小样例锁住四种判定：
留痕放行、重新抛出放行、`nosec:swallow` 显式豁免放行、纯 `pass` 必须被抓。
"""

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load_gate():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "check_silent_swallow", SCRIPTS / "check_silent_swallow.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SILENT = """
def f():
    try:
        g()
    except Exception:
        pass
"""

LOGGED = """
def f():
    try:
        g()
    except Exception:
        logger.warning("failed: %s", exc, exc_info=True)
"""

RERAISED = """
def f():
    try:
        g()
    except Exception:
        raise
"""

EXEMPT = """
def f():
    try:
        g()
    except Exception:  # nosec:swallow - logger 自身不可用时的兜底
        pass
"""

NARROW = """
def f():
    try:
        g()
    except ValueError:
        pass
"""


class TestSilentSwallowGate:
    def test_pure_pass_is_flagged(self):
        gate = _load_gate()
        hits = gate.scan_text("app/x.py", SILENT)
        assert hits and "except Exception" in hits[0]

    def test_logging_is_compliant(self):
        gate = _load_gate()
        assert gate.scan_text("app/x.py", LOGGED) == []

    def test_reraise_is_compliant(self):
        gate = _load_gate()
        assert gate.scan_text("app/x.py", RERAISED) == []

    def test_explicit_exemption_is_compliant(self):
        gate = _load_gate()
        assert gate.scan_text("app/x.py", EXEMPT) == []

    def test_narrow_exception_is_out_of_scope(self):
        gate = _load_gate()
        assert gate.scan_text("app/x.py", NARROW) == []
