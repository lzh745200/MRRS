"""security_audit.py「写操作用审计」（Scan 4）的棘轮行为。

背景（R34-3）：原实现用 25 项硬编码模块清单（含 sentiment / user_permissions
等已删除模块），实测只覆盖 22/54 个顶层写模块；households（PII 最密集，9 个
写端点）、media、files、data_sync、reminders、recycle_bin 等长期在扫描范围外。
现改为动态发现 + 基线棘轮：基线内存量不阻断，基线外新增即失败。
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "security_audit.py"


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("_security_audit_probe", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_module(tmp_path, name, body='@router.post("/x")\ndef f():\n    pass\n'):
    fake = tmp_path / f"{name}.py"
    fake.write_text(body, encoding="utf-8")
    return fake.read_text(encoding="utf-8")


class TestDiscover:
    def test_discovers_all_write_modules(self, audit):
        modules = audit.discover_write_modules()
        assert len(modules) > 30, "写模块发现数异常偏少，动态发现可能失效"

    def test_previously_uncovered_sensitive_modules_are_discovered(self, audit):
        """原硬编码清单遗漏的高敏模块必须被动态发现覆盖。"""
        paths = {rel for _, _, rel in audit.discover_write_modules()}
        for expected in (
            "backend/app/api/v1/households.py",
            "backend/app/api/v1/media.py",
            "backend/app/api/v1/files.py",
            "backend/app/api/v1/data_sync.py",
        ):
            assert expected in paths, f"{expected} 未被动态发现"


class TestRatchet:
    def test_current_state_has_no_new_violations(self, audit):
        """当前代码必须与基线一致（NEW=0）；补审计后应跑 --write-audit-baseline 收敛。"""
        assert audit.scan_missing_write_work_log() == []

    def test_new_unaudited_module_is_reported(self, audit, monkeypatch, tmp_path):
        content = _fake_module(tmp_path, "brand_new")
        monkeypatch.setattr(audit, "discover_write_modules", lambda: [
            (tmp_path / "brand_new.py", content, "backend/app/api/v1/brand_new.py"),
        ])
        monkeypatch.setattr(audit, "_load_audit_baseline", lambda: [])
        violations = audit.scan_missing_write_work_log()
        assert len(violations) == 1
        assert "brand_new" in violations[0]

    def test_baselined_module_is_not_reported(self, audit, monkeypatch, tmp_path):
        """存量债务（基线内）不阻断，避免历史欠账让门禁永久变红。"""
        content = _fake_module(tmp_path, "known_debt")
        monkeypatch.setattr(audit, "discover_write_modules", lambda: [
            (tmp_path / "known_debt.py", content, "backend/app/api/v1/known_debt.py"),
        ])
        monkeypatch.setattr(audit, "_load_audit_baseline",
                            lambda: ["backend/app/api/v1/known_debt.py"])
        assert audit.scan_missing_write_work_log() == []

    def test_audited_module_is_not_reported(self, audit, monkeypatch, tmp_path):
        content = _fake_module(
            tmp_path, "audited", '@router.post("/x")\ndef f():\n    write_work_log()\n'
        )
        monkeypatch.setattr(audit, "discover_write_modules", lambda: [
            (tmp_path / "audited.py", content, "backend/app/api/v1/audited.py"),
        ])
        monkeypatch.setattr(audit, "_load_audit_baseline", lambda: [])
        assert audit.scan_missing_write_work_log() == []

    def test_exempted_module_is_not_reported(self, audit, monkeypatch, tmp_path):
        """受控豁免（带 ≥8 字符理由）生效。"""
        body = (
            "# security-audit: exempt work_log — 纯读接口无写副作用\n"
            '@router.post("/x")\ndef f():\n    pass\n'
        )
        content = _fake_module(tmp_path, "exempted", body)
        monkeypatch.setattr(audit, "discover_write_modules", lambda: [
            (tmp_path / "exempted.py", content, "backend/app/api/v1/exempted.py"),
        ])
        monkeypatch.setattr(audit, "_load_audit_baseline", lambda: [])
        assert audit.scan_missing_write_work_log() == []

    def test_auditlogger_counts_as_audit(self, audit, monkeypatch, tmp_path):
        """AuditLogger 等入口同样视为已留痕。"""
        body = '@router.delete("/x")\ndef f():\n    AuditLogger().log()\n'
        content = _fake_module(tmp_path, "loggerd", body)
        monkeypatch.setattr(audit, "discover_write_modules", lambda: [
            (tmp_path / "loggerd.py", content, "backend/app/api/v1/loggerd.py"),
        ])
        monkeypatch.setattr(audit, "_load_audit_baseline", lambda: [])
        assert audit.scan_missing_write_work_log() == []
