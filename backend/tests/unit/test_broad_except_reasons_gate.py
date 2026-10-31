# -*- coding: utf-8 -*-
"""宽泛异常捕获理由门禁的单测（含负向用例）。"""

import importlib.util
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_GATE = _REPO / "scripts" / "check_broad_except_reasons.py"
_spec = importlib.util.spec_from_file_location("check_broad_except_reasons", _GATE)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def test_no_reason_is_violation():
    """无理由的 BLE001 → 违规。"""
    assert gate.has_reason("except Exception as e:  # noqa: BLE001") is False


def test_dash_reason_ok():
    """- 说明 形式 → 合规。"""
    assert gate.has_reason("except Exception as e:  # noqa: BLE001 - 降级为 error_type") is True


def test_colon_reason_ok():
    """：说明 形式 → 合规。"""
    assert gate.has_reason("except Exception as e:  # noqa: BLE001：体检降级") is True


def test_comment_prefix_reason_ok():
    """# noqa: BLE001  # - 说明 形式 → 合规。"""
    assert gate.has_reason("except Exception:  # noqa: BLE001  # - 单项降级") is True


def test_pragma_style_reason_ok():
    """理由写在 pragma 注释里 → 合规（对齐 check_pragma_reasons 口径）。"""
    line = "except Exception:  # noqa: BLE001  # pragma: no cover -- 防御分支"
    assert gate.has_reason(line) is True


def test_line_without_ble001_ok():
    """不含 BLE001 的行一律合规。"""
    assert gate.has_reason("except ValueError:") is True
    assert gate.has_reason("# 普通注释") is True


def test_short_reason_rejected():
    """理由不足 2 个非空字符 → 仍算违规（防写个 '-' 糊弄）。"""
    assert gate.has_reason("except Exception:  # noqa: BLE001 -") is False
    assert gate.has_reason("except Exception:  # noqa: BLE001 - x") is False


def test_find_violations_uses_scan_dirs(tmp_path, monkeypatch):
    """find_violations 按 SCAN_DIRS 扫描（负向：注入坏行必须被抓到）。"""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("except Exception:  # noqa: BLE001\n", encoding="utf-8")
    (pkg / "b.py").write_text("except Exception:  # noqa: BLE001 - 有理由\n", encoding="utf-8")
    monkeypatch.setattr(gate, "SCAN_DIRS", [pkg])
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    bad = gate.find_violations()
    assert len(bad) == 1
    assert bad[0]["file"] == "pkg/a.py"


def test_json_mode(tmp_path, monkeypatch, capsys):
    """--json 输出纯 JSON。"""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("except Exception:  # noqa: BLE001\n", encoding="utf-8")
    monkeypatch.setattr(gate, "SCAN_DIRS", [pkg])
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    rc = gate.main(["--json"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["violations"] == 1


def test_real_repo_is_clean():
    """真实仓库零违规（理由已全部补齐，门禁零容忍）。"""
    assert gate.find_violations() == []
