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
    - 2026-10-08 扩展（同源缺陷族）：``app.core.*`` 模块被其它模块
      【按值导入】（如 ``app/api/v1/policy.py`` 的 ``from ...core.cache
      import cache_manager``），因此禁止对其 reload；确需 reload 覆盖
      兼容分支时，必须在本文件内对同一别名就地还原 ``__dict__``
      （``mod.__dict__.clear(); mod.__dict__.update(original)``），
      否则 reload 出的新对象与各处旧引用失配，跨文件 patch 静默失效。

历史违规（2026-08-29 已全部改写为子进程/monkeypatch 方案）：
    - tests/unit/test_cov_b4a_services_init.py（reload app.services 包, 豁免）
    - tests/unit/test_resource_monitor_cov.py（reload resource_monitor → 子进程）
    - tests/unit/test_anomaly_detection_service_complete.py（reload anomaly → 子进程）

事故记录（2026-10-08）：
    tests/unit/test_branch_final_core_api.py 的
    ``test_cache_module_compat_branch_false`` 对 ``app.core.cache`` 两次
    ``importlib.reload`` 且未还原命名空间，使 ``app.core.cache.cache_manager``
    变为新对象，而 ``app.api.v1.policy.cache_manager`` 仍是旧对象 →
    ``test_policy_api.py::test_get_policies_no_filter_cached`` 在特定 worker
    分布下随机 KeyError，拦截 v1.12.15 的 Windows 构建。已就地还原
    ``__dict__`` 修复，并纳入下方 core 模块族扫描规则。
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

# app.core.* 被多处模块【按值导入】（policy.py / organization.py /
# system/cache.py / services/cache_service.py ...），属「reload 即身份失配」的高危族。
CORE_FAMILY_PREFIX = "app.core."
# 就地还原命名空间：``<alias>.__dict__.clear()`` 或 ``<alias>.__dict__.update(...)``
INPLACE_RESTORE_TMPL = r"\b{0}\s*\.__dict__\.(?:clear|update)\s*\("


def _module_alias_map(text: str) -> dict:
    """收集 ``import X [as Y]`` 的别名 → 完整模块名映射。"""
    module_of = {}
    for m in IMPORT_ALIAS.finditer(text):
        full, alias = m.group(1), m.group(2)
        module_of[alias or full.split(".")[-1]] = full
    return module_of


def _reload_targets(text: str):
    """解析文件内全部 ``importlib.reload(...)`` 为 (表达式, 完整模块名) 列表。

    别名感知: ``import app.core.cache as cm`` + ``reload(cm)`` →
    (``cm``, ``app.core.cache``)；无法解析的目标按原名判断。
    """
    module_of = _module_alias_map(text)
    targets = []
    for m in RELOAD_TARGET.finditer(text):
        target = m.group(1)
        targets.append((target, module_of.get(target, target)))
    return targets


def _reloaded_service_module(text: str):
    """返回 (目标表达式, 解析到的完整模块名), 若 reload 目标为 services 子模块。

    别名感知: ``import app.services.resource_monitor as rm`` + ``reload(rm)``
    解析为 app.services.resource_monitor。无法解析的目标按原名判断。
    """
    for target, full in _reload_targets(text):
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

    def test_core_modules_reload_requires_identity_restore(self):
        """app.core.* 被按值导入: 若 reload 则必须就地还原 __dict__ 身份。

        2026-10-08 事故：test_branch_final_core_api.py 对 app.core.cache 两次
        reload 且未还原命名空间，使 cache_manager 变成新对象、而 app.api.v1.policy
        仍持旧引用 → test_get_policies_no_filter_cached 在特定 worker 分布下随机
        KeyError。本规则与该缺陷同源，且与执行顺序/分片无关。
        """
        offenders = []
        for py in _test_files():
            text = py.read_text(encoding="utf-8", errors="replace")
            if not RELOAD_CALL.search(text):
                continue
            rel = py.relative_to(BACKEND_ROOT)
            for target, full in _reload_targets(text):
                if not full.startswith(CORE_FAMILY_PREFIX):
                    continue
                if re.search(INPLACE_RESTORE_TMPL.format(re.escape(target)), text):
                    continue
                offenders.append(f"{rel}: reload({target}) -> {full}")
        assert not offenders, (
            "发现对 app.core.* 模块的 importlib.reload 缺少 __dict__ 就地还原（"
            "reload 出的新对象会与被按值导入它的模块所持旧引用失配, "
            "跨文件 patch 静默失效）:\n  " + "\n  ".join(offenders)
        )

    def test_known_compliant_reload_targets_unchanged(self):
        """抽样确认豁免与合法目标未被扩散:
        - app.services 包聚合 reload（导入回退测试）仍允许
        - app.core.* 的 reload 由上方 core 族规则单独约束（须带 __dict__ 还原）
        """
        b4a = BACKEND_ROOT / "tests" / "unit" / "test_cov_b4a_services_init.py"
        text = b4a.read_text(encoding="utf-8", errors="replace")
        # 包聚合层 reload 保留, 且不得出现对子模块的 import + reload 组合滥用
        assert "importlib.reload(app.services)" in text
