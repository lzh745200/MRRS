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

# 2026-08-29 增强: 封堵两类历史绕过
# 1) f-string 内插任意含 err/exc/error/exception 的标识符(如 evt_err) —— 旧规则
#    的 \b 只匹配 e/exc/ex/err 开头, projects.py:1060 曾借 evt_err 绕过;
# 2) 500 路径的 detail=str(<var>) —— 非 f-string, 旧规则完全不可见,
#    data_packages.py 曾有 4 处内部异常文本直出 500 响应。
LEAK_FSTRING = re.compile(
    r'(detail|message|error)\s*=\s*f"[^"]*\{\s*(?:str\()?\s*'
    r'[A-Za-z_]*(?:err|exc|error|exception)[A-Za-z_0-9]*\s*\)?[^"]*\}"'
)
LEAK_STR_500 = re.compile(
    r'status_code\s*=\s*(?:status\.)?(?:HTTP_500_INTERNAL_SERVER_ERROR|500)'
    r'[^)]*detail\s*=\s*str\('
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
                if (LEAK.search(line) or LEAK_FSTRING.search(line)) and "logger." not in line:
                    rel = py.relative_to(BACKEND_ROOT)
                    offenders.append(f"{rel}:{lineno}: {line.strip()[:120]}")
        assert not offenders, (
            "发现异常细节直出（W1-T8 不变量被破坏）:\n" + "\n".join(offenders)
        )

    def test_no_detail_str_in_500_responses(self):
        """500 路径禁止 detail=str(<var>): 内部异常文本不得直出客户端。

        400/ValueError 业务文案的 detail=str(e) 不受影响(属预期用户可见消息)。
        """
        offenders = []
        for py in _py_files():
            for lineno, line in enumerate(
                py.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if LEAK_STR_500.search(line):
                    rel = py.relative_to(BACKEND_ROOT)
                    offenders.append(f"{rel}:{lineno}: {line.strip()[:120]}")
        assert not offenders, (
            "发现 500 响应外泄内部异常文本（W1-T8 不变量被破坏）:\n"
            + "\n".join(offenders)
        )

    def test_named_fix_points_are_sanitized(self):
        """工单点名的 todos.py / system/init.py 抽样确认已泛化。"""
        todos = (API_DIR / "todos.py").read_text(encoding="utf-8")
        assert not LEAK.search(todos), "todos.py 仍存在异常直出"
        init_src = (API_DIR / "system" / "init.py").read_text(encoding="utf-8")
        assert '"error": str(e)' not in init_src, "init.py 响应体仍外泄 str(e)"
