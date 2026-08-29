"""W1 安全不变量 8 回归扫描：禁止对 app.services 子模块 importlib.reload。

背景（AGENTS.md W1 #8, 2026-08-24）：
    importlib.reload 会**就地重建**模块内的类对象——其他模块经
    ``from app.services.xxx import Y`` 持有的旧类引用与新类分裂，
    导致跨文件 ``patch.object`` 静默失效，测试假绿/假红交替。
    正确做法：``monkeypatch.setattr`` 打模块常量。

规则：
    - tests/ 下任何文件, 只要同时出现 ``importlib.reload`` 与对
      ``app.services.<子模块>`` 的 import（import/from 两种形式均算）,
      即判定违规。
    - ``import app.services``（包聚合层）不违规：包 __init__ 的 reload
      仅重绑定包属性, 类对象本身不重建（导入回退测试必需）。

历史违规（2026-08-29 已全部改写为子进程/monkeypatch 方案）：
    - tests/unit/test_cov_b4a_services_init.py（reload app.services 包, 豁免）
    - tests/unit/test_resource_monitor_cov.py（reload resource_monitor → 子进程）
    - tests/unit/test_anomaly_detection_service_complete.py（reload anomaly → 子进程）
"""

import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = BACKEND_ROOT / "tests"

RELOAD_CALL = re.compile(r"importlib\.reload\s*\(")
RELOAD_TARGET = re.compile(r"importlib\.reload\s*\(\s*([A-Za-z_][\w\.]*)\s*\)")
IMPORT_ALIAS = re.compile(
    r"^\s*import\s+([\w\.]+)(?:\s+as\s+(\w+))?", re.MULTILINE
)
SERVICES_SUBMODULE_IMPORT = re.compile(
    r"^\s*(?:import\s+app\.services\.\w|from\s+app\.services\.\w)", re.MULTILINE
)


def _reloaded_service_module(text: str):
    """返回 (目标表达式, 解析到的完整模块名), 若 reload 目标为 services 子模块。

    别名感知: ``import app.services.resource_monitor as rm`` + ``reload(rm)``
    解析为 app.services.resource_monitor。无法解析的目标按原名判断。
    """
    module_of = {}
    for m in IMPORT_ALIAS.finditer(text):
        full, alias = m.group(1), m.group(2)
        module_of[alias or full.split(".")[-1]] = full
    for m in RELOAD_TARGET.finditer(text):
        target = m.group(1)
        full = module_of.get(target, target)
        if full.startswith("app.services."):
            return target, full
    return None


def _test_files():
    return sorted(TESTS_DIR.rglob("test_*.py"))


class TestNoServiceModuleReload:
    def test_tests_do_not_reload_services_submodules(self):
        """源码扫描: services 子模块禁止 reload, 防类对象分裂。"""
        offenders = []
        for py in _test_files():
            text = py.read_text(encoding="utf-8", errors="replace")
            if not RELOAD_CALL.search(text):
                continue
            hit = _reloaded_service_module(text)
            if hit:
                rel = py.relative_to(BACKEND_ROOT)
                offenders.append(f"{rel}: reload({hit[0]}) -> {hit[1]}")
        assert not offenders, (
            "发现对 app.services 子模块的 importlib.reload（W1 不变量 8 被破坏, "
            "类对象分裂会使跨文件 patch 失效）:\n  " + "\n  ".join(offenders)
        )

    def test_known_compliant_reload_targets_unchanged(self):
        """抽样确认豁免与合法目标未被扩散:
        - app.services 包聚合 reload（导入回退测试）仍允许
        - app.core.* 的 reload 与本不变量无关
        """
        b4a = BACKEND_ROOT / "tests" / "unit" / "test_cov_b4a_services_init.py"
        text = b4a.read_text(encoding="utf-8", errors="replace")
        # 包聚合层 reload 保留, 且不得出现对子模块的 import + reload 组合滥用
        assert "importlib.reload(app.services)" in text
