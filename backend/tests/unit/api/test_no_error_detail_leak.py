"""W1-T8 安全回归：内部异常细节不得直出客户端。

工单 .scratch/w1-security-redline/008
不变量：api/v1 下禁止 detail=f"...{e}/{str(e)}" 形式的异常插值出站。
历史缺陷：65 处 HTTPException detail 携带 SQLAlchemy/内部异常字符串，
可泄露表结构与 SQL 片段。
"""

import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
API_DIR = BACKEND_ROOT / "app" / "api" / "v1"

LEAK = re.compile(
    r'(detail|message|error)\s*=\s*f"[^"]*\{\s*(?:str\()?\s*(?:e|exc|ex|err)\b[^"]*\}"'
)


def _py_files():
    return sorted(API_DIR.rglob("*.py"))


class TestNoExceptionDetailLeak:
    def test_api_v1_has_no_exception_interpolation_in_responses(self):
        """源码扫描：响应字段不得内插异常对象。"""
        offenders = []
        for py in _py_files():
            for lineno, line in enumerate(
                py.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if LEAK.search(line) and "logger." not in line:
                    rel = py.relative_to(BACKEND_ROOT)
                    offenders.append(f"{rel}:{lineno}: {line.strip()[:120]}")
        assert not offenders, (
            "发现异常细节直出（W1-T8 不变量被破坏）:\n" + "\n".join(offenders)
        )

    def test_named_fix_points_are_sanitized(self):
        """工单点名的 todos.py / system/init.py 抽样确认已泛化。"""
        todos = (API_DIR / "todos.py").read_text(encoding="utf-8")
        assert not LEAK.search(todos), "todos.py 仍存在异常直出"
        init_src = (API_DIR / "system" / "init.py").read_text(encoding="utf-8")
        assert '"error": str(e)' not in init_src, "init.py 响应体仍外泄 str(e)"
