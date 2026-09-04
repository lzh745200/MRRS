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

# 2026-08-30 增强: 封堵第三类绕过 —— data={...} 字典值形态
# success_response(data={"error": str(e)}) 是 kwargs 规则的扫描盲区
# （评审发现 monitor.py /database-size 曾以该形态把异常文本与服务器路径出站）。
# 与 LEAK_FSTRING 同口径：内插含 err/exc/error/exception 片段的标识符即命中。
LEAK_DICT_STR = re.compile(
    r'["\'](error|message|detail)["\']\s*:\s*str\(\s*'
    r'[A-Za-z_]*(?:err|exc|error|exception)[A-Za-z_0-9]*\s*\)'
)
LEAK_DICT_FSTRING = re.compile(
    r'["\'](error|message|detail)["\']\s*:\s*f"[^"]*\{\s*(?:str\()?\s*'
    r'[A-Za-z_]*(?:err|exc|error|exception)[A-Za-z_0-9]*\s*\)?[^"]*\}"'
)


def _py_files():
    return sorted(API_DIR.rglob("*.py"))


# ── 2026-09-03 增强: 覆盖 service/util/core 层 ──
# 盲区成因：permission_package_service.confirm_import 曾在 service 层把异常原文
# 放进返回字典的 message，再由 API 层 `detail=result.get("message")` 转发出站。
# 文本产生在 app/services/、出站动作在 app/api/v1/，旧扫描器只看 api/v1 的
# 字面内插，结构上看不见这条间接路径。
SVC_DIRS = [
    BACKEND_ROOT / "app" / "services",
    BACKEND_ROOT / "app" / "utils",
    BACKEND_ROOT / "app" / "core",
]

# 裸异常变量（e/exc/ex/err）或含 err/exc/error/exception 片段的标识符（如 error_msg）
_EXC_VAR = r'(?:(?:e|exc|ex|err)\b|[A-Za-z_]*(?:err|exc|error|exception)[A-Za-z_0-9]*)'

# (a) detail= 的 f-string 内插异常变量 —— 任意状态码都禁止（与 LEAK/LEAK_FSTRING 同口径）
SVC_DETAIL_FSTRING = re.compile(
    rf'HTTPException\([^)]*detail\s*=\s*f"[^"]*\{{\s*(?:str\()?\s*{_EXC_VAR}[^"]*\}}"'
)
# (b) detail=str(<异常变量>) —— 仅 500 禁止。沿用 LEAK_STR_500 的刻意放行：
#     400 级 detail=str(e) 多为 ValueError 业务文案，属预期用户可见消息。
SVC_DETAIL_STR_500 = re.compile(
    rf'HTTPException\([^)]*status_code\s*=\s*(?:status\.)?'
    rf'(?:HTTP_500_INTERNAL_SERVER_ERROR|500)[^)]*detail\s*=\s*str\(\s*{_EXC_VAR}\s*\)'
)


def _svc_py_files():
    for d in SVC_DIRS:
        yield from sorted(d.rglob("*.py"))


class TestNoExceptionDetailLeak:
    def test_api_v1_has_no_exception_interpolation_in_responses(self):
        """源码扫描：响应字段不得内插异常对象。"""
        offenders = []
        for py in _py_files():
            for lineno, line in enumerate(
                py.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if (
                    LEAK.search(line)
                    or LEAK_FSTRING.search(line)
                    or LEAK_DICT_STR.search(line)
                    or LEAK_DICT_FSTRING.search(line)
                ) and "logger." not in line:
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

    def test_service_util_core_layers_have_no_http_detail_leak(self):
        """W1-T8 扩面：service/util/core 层直接构造 HTTPException 时不得内插异常。

        这三层不在旧扫描范围内，而 permission_package_service.confirm_import 曾在
        service 层生成异常原文、由 API 层 `detail=result.get("message")` 转发出站，
        旧规则完全看不见。已修的三处：
          * services/permission_package_service.py confirm_import / JSON 解析分支
          * services/policy_import_service.py 导入兜底 500
          * utils/db_error_handler.py IntegrityError 兜底（str(exc.orig) 含表名/列名）
            与 catch-all 500

        刻意不扫 service 返回字典里的 "message":/"errors": —— 那类多为面向导入
        用户的行级校验反馈（含行号/字段/格式原因），一刀切泛化会损害可用性，
        需按调用链逐点判定是否真的出站，不适用源码扫描。
        """
        offenders = []
        for py in _svc_py_files():
            for lineno, line in enumerate(
                py.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if "logger." in line:
                    continue
                if SVC_DETAIL_FSTRING.search(line) or SVC_DETAIL_STR_500.search(line):
                    rel = py.relative_to(BACKEND_ROOT)
                    offenders.append(f"{rel}:{lineno}: {line.strip()[:120]}")
        assert not offenders, (
            "service/util/core 层存在异常细节直出 HTTPException detail"
            "（W1-T8 不变量被破坏）:\n" + "\n".join(offenders)
        )
