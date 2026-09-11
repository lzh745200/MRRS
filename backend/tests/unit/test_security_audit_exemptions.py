"""R26-T01 回归测试：安全审计脚本的受控豁免机制。

锁定三条防滥用行为（见 scripts/security_audit.py 的 EXEMPTION_RE）：
  ① 有效标记被识别（带 ≥8 字符理由）；
  ② 无理由标记【不】被识别（空理由 / 理由 <8 字符 / 缺分隔符）；
  ③ 规则名不匹配不误伤（work_log 标记不会豁免 data_scope 扫描，反之亦然）。

额外锁定 Scan4/Scan5 端到端行为：被豁免模块不计入违规、无效标记不得消警。
"""

import importlib.util
import re
from pathlib import Path

import pytest

# ── 以文件路径加载脚本模块（scripts/ 非包，无法直接 import） ──
_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "security_audit.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("security_audit_r26", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = _load_script_module()


# ══════════════════════════════════════════════════════════════════
#  ① 有效标记被识别
# ══════════════════════════════════════════════════════════════════

class TestValidExemptionRecognized:
    def test_work_log_marker_after_docstring(self):
        content = (
            '"""模块文档字符串，不应被污染。"""\n'
            "\n"
            "# security-audit: exempt work_log — 只读AI分析端点，POST 仅承载复杂查询体，全程不落库\n"
            "from fastapi import APIRouter\n"
        )
        reason = audit._find_exemption(content, "work_log")
        assert reason is not None
        assert reason.startswith("只读AI分析端点")
        assert len(reason) >= 8

    def test_data_scope_marker_with_colon_separator(self):
        content = "# security-audit: exempt data_scope: 系统初始化引导，创建首个管理员，无数据权限主体\n"
        reason = audit._find_exemption(content, "data_scope")
        assert reason == "系统初始化引导，创建首个管理员，无数据权限主体"

    def test_marker_with_hyphen_separator(self):
        content = "# security-audit: exempt commit - 身份解码端点，无业务实体落库语义变更需求\n"
        assert audit._find_exemption(content, "commit") is not None

    def test_reason_boundary_exactly_eight_chars(self):
        content = "# security-audit: exempt work_log — 12345678\n"
        assert audit._find_exemption(content, "work_log") == "12345678"


# ══════════════════════════════════════════════════════════════════
#  ② 无理由标记【不】被识别
# ══════════════════════════════════════════════════════════════════

class TestReasonlessMarkerIgnored:
    def test_marker_without_reason(self):
        assert audit._find_exemption("# security-audit: exempt work_log\n", "work_log") is None

    def test_marker_with_only_separator(self):
        assert audit._find_exemption("# security-audit: exempt work_log —\n", "work_log") is None

    def test_reason_too_short_seven_chars(self):
        assert audit._find_exemption("# security-audit: exempt data_scope — 1234567\n", "data_scope") is None

    def test_plain_comment_is_not_exemption(self):
        assert audit._find_exemption("# 这只是普通注释，不是豁免标记\n", "work_log") is None


# ══════════════════════════════════════════════════════════════════
#  ③ 规则名不匹配不误伤
# ══════════════════════════════════════════════════════════════════

class TestRuleNameIsolation:
    def test_work_log_marker_does_not_exempt_data_scope(self):
        content = "# security-audit: exempt work_log — 只读AI分析端点，POST 仅承载复杂查询体\n"
        assert audit._find_exemption(content, "work_log") is not None
        assert audit._find_exemption(content, "data_scope") is None

    def test_data_scope_marker_does_not_exempt_commit(self):
        content = "# security-audit: exempt data_scope — 超级管理员全局管理域，无组织隔离主体\n"
        assert audit._find_exemption(content, "data_scope") is not None
        assert audit._find_exemption(content, "commit") is None

    def test_both_markers_resolved_independently(self):
        content = (
            "# security-audit: exempt work_log — 只读AI分析端点，全程不落库\n"
            "# security-audit: exempt data_scope — 认证身份域，按主键定位\n"
        )
        assert audit._find_exemption(content, "work_log") == "只读AI分析端点，全程不落库"
        assert audit._find_exemption(content, "data_scope") == "认证身份域，按主键定位"


# ══════════════════════════════════════════════════════════════════
#  端到端：Scan4 / Scan5 豁免生效且不计入违规
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def fake_backend(tmp_path, monkeypatch):
    """构造最小 backend/app 树并重定向脚本的扫描根目录。"""
    app_dir = tmp_path / "backend" / "app"
    v1 = app_dir / "api" / "v1"
    v1.mkdir(parents=True)
    monkeypatch.setattr(audit, "BACKEND_APP", app_dir)
    monkeypatch.setattr(audit, "PROJECT_ROOT", tmp_path)
    return v1


def _write(path: Path, text: str):
    path.write_text(text, encoding="utf-8")


class TestScanWriteWorkLogExemption:
    def test_valid_marker_suppresses_violation(self, fake_backend):
        _write(
            fake_backend / "ai.py",
            '"""AI"""\n'
            "# security-audit: exempt work_log — 只读AI分析端点，POST 仅承载复杂查询体，全程不落库\n"
            '@router.post("/analyze")\ndef analyze():\n    return {}\n',
        )
        assert audit.scan_missing_write_work_log() == []

    def test_reasonless_marker_still_flags(self, fake_backend):
        _write(
            fake_backend / "ai.py",
            '"""AI"""\n'
            "# security-audit: exempt work_log\n"
            '@router.post("/analyze")\ndef analyze():\n    return {}\n',
        )
        violations = audit.scan_missing_write_work_log()
        assert len(violations) == 1
        assert "ai.py" in violations[0]

    def test_missing_marker_still_flags(self, fake_backend):
        _write(
            fake_backend / "ai_enhanced.py",
            '"""AI enhanced"""\n'
            '@router.post("/predict")\ndef predict():\n    return {}\n',
        )
        violations = audit.scan_missing_write_work_log()
        assert len(violations) == 1
        assert "ai_enhanced.py" in violations[0]


class TestScanDataScopeExemption:
    def test_valid_marker_suppresses_violation(self, fake_backend):
        _write(
            fake_backend / "menus.py",
            '"""menus"""\n'
            "# security-audit: exempt data_scope — 按主键定位的身份域菜单配置\n"
            "def f(db):\n    return db.query(User).all()\n",
        )
        assert audit.scan_missing_data_scope() == []

    def test_reasonless_marker_still_flags(self, fake_backend):
        _write(
            fake_backend / "menus.py",
            '"""menus"""\n'
            "# security-audit: exempt data_scope\n"
            "def f(db):\n    return db.query(User).all()\n",
        )
        violations = audit.scan_missing_data_scope()
        assert len(violations) == 1
        assert "menus.py" in violations[0]

    def test_org_model_query_without_filter_flags(self, fake_backend):
        _write(
            fake_backend / "organization.py",
            '"""org"""\ndef f(db):\n    return db.query(SupportedVillage).all()\n',
        )
        violations = audit.scan_missing_data_scope()
        assert len(violations) == 1
        assert "organization.py" in violations[0]


def test_regex_compiled_and_public():
    """EXEMPTION_RE 存在且为已编译正则（防误改）。"""
    assert isinstance(audit.EXEMPTION_RE, re.Pattern)
    assert audit.EXEMPTION_RULES == ("commit", "work_log", "data_scope")
