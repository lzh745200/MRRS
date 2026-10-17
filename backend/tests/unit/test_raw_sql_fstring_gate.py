# -*- coding: utf-8 -*-
"""原始 SQL f-string 豁免门禁的回归（`scripts/check_raw_sql_fstrings.py`）。

背景（2026-10-17）：bandit B608 只警告"字符串里拼了变量"，无法区分"拼的是
SQL 关键字/表名白名单"与"拼的是用户输入"。R28 收尾时只给 `analytics_service`
的 9 处补了 `# nosec B608 - <理由>`，其余 26 处在全仓散落且**无理由**，
且没有任何门禁阻止新增 —— "拼 SQL 必须人工复核并留理由"此前零执行力。

本文件锁定检查器行为：

1. **AST 定位**：`text(f"...")` 的完整语句范围由 ast 节点给出 —— 多行
   f-string（SQL 内含 `COUNT(*)` 等括号）不会被"拼括号"启发式带偏；
2. **理由判定**：`# nosec B608 - 说明` / `— 说明` / `: 说明` 算有理由，
   裸 `# nosec B608` 与完全没有 nosec 都算违规；
3. **范围语义**：理由必须落在语句范围内 —— 写在上一行（范围外）不算，
   这正是本检查器第一次落地时踩过的坑（3 处理由写到上一行被正确判红）；
4. **仓库级 ratchet**：仓库自身 0 违规钉死（新增即被拦）。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "check_raw_sql_fstrings.py"

_spec = importlib.util.spec_from_file_location("check_raw_sql_fstrings", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


class TestReasonDetection:
    def test_reasoned_nosec_variants_ok(self):
        span = [
            'x = text(f"SELECT ...")  # nosec B608 - 表名来自白名单',
            'x = text(f"SELECT ...")  # nosec B608 — 表名来自白名单',
            'x = text(f"SELECT ...")  # nosec B608: 表名来自白名单',
        ]
        for line in span:
            assert mod.has_reasoned_nosec([line], 1, 1) is True, line

    def test_bare_nosec_flagged(self):
        assert mod.has_reasoned_nosec(['x = text(f"SELECT ...")  # nosec B608'], 1, 1) is False

    def test_no_nosec_flagged(self):
        assert mod.has_reasoned_nosec(['x = text(f"SELECT ...")'], 1, 1) is False


class TestAstSpans:
    def test_multiline_fstring_with_reason_on_closing_line(self, tmp_path):
        """多行 f-string：理由在收尾行（SQL 括号不影响范围判定）。"""
        probe = tmp_path / "probe.py"
        probe.write_text(
            "from sqlalchemy import text\n"
            "def f(db, t):\n"
            '    return db.execute(text(f"""\n'
            "        SELECT COUNT(*) FROM {t} WHERE (a, b) IN (1, 2)\n"
            '    """))  # nosec B608 - 表名白名单\n',
            encoding="utf-8",
        )
        found = mod.scan_file(probe)
        assert len(found) == 1
        _lineno, _end, _snippet, ok = found[0]
        assert ok is True

    def test_reason_outside_statement_span_is_not_counted(self, tmp_path):
        """理由写在语句范围之外（上一行）不算 —— 落地时踩过的坑。"""
        probe = tmp_path / "probe.py"
        probe.write_text(
            "from sqlalchemy import text\n"
            "def f(db, t):\n"
            "    # nosec B608 - 写在上一行，范围外\n"
            '    return db.execute(text(f"SELECT * FROM {t}"))\n',
            encoding="utf-8",
        )
        found = mod.scan_file(probe)
        assert len(found) == 1
        assert found[0][3] is False

    def test_non_text_call_and_non_fstring_are_ignored(self, tmp_path):
        probe = tmp_path / "probe.py"
        probe.write_text(
            "from sqlalchemy import text\n"
            "def f(db):\n"
            '    a = text("SELECT 1")\n'
            "    b = compute(f\"x\")\n"
            "    return a, b\n",
            encoding="utf-8",
        )
        assert mod.scan_file(probe) == []

    def test_syntax_error_file_does_not_crash(self, tmp_path):
        probe = tmp_path / "broken.py"
        probe.write_text("def f(:\n    x\n", encoding="utf-8")
        assert mod.scan_file(probe) == []

    def test_attribute_call_form_is_detected(self, tmp_path):
        """`sqlalchemy.text(...)` 属性调用形态也必须被抓到。"""
        probe = tmp_path / "probe.py"
        probe.write_text(
            "import sqlalchemy\n"
            "def f(db, t):\n"
            '    return db.execute(sqlalchemy.text(f"SELECT * FROM {t}"))\n',
            encoding="utf-8",
        )
        found = mod.scan_file(probe)
        assert len(found) == 1
        assert found[0][3] is False


class TestRepoWideRatchet:
    def test_repo_sql_fstrings_all_have_reason(self):
        """仓库自身：拼接 SQL 全部带理由（新增未登记即红）。"""
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
        )
        assert result.returncode == 0, result.stdout
        assert "未登记理由: 0" in result.stdout

    def test_violation_probe_dir_fails_loudly(self, tmp_path):
        """探测目录里有未登记调用点 → 退出码 1 且给出 ::error:: 注解。"""
        probe_dir = tmp_path / "probe_app"
        probe_dir.mkdir()
        (probe_dir / "probe.py").write_text(
            "from sqlalchemy import text\n"
            "def f(db, t):\n"
            '    return db.execute(text(f"SELECT * FROM {t}"))\n',
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(probe_dir)],
            capture_output=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
        )
        assert result.returncode == 1
        assert "::error::" in result.stdout

    def test_list_mode_never_fails(self, tmp_path):
        """--list 仅供盘点，不判定失败。"""
        probe_dir = tmp_path / "probe_app"
        probe_dir.mkdir()
        (probe_dir / "probe.py").write_text(
            "from sqlalchemy import text\n"
            "def f(db, t):\n"
            '    return db.execute(text(f"SELECT * FROM {t}"))\n',
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(probe_dir), "--list"],
            capture_output=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
        )
        assert result.returncode == 0
