# -*- coding: utf-8 -*-
r"""原始 SQL f-string（`text(f"...")`）必须带 `# nosec B608` 理由 —— 门禁（2026-10-17）。

背景：bandit B608（hardcoded_sql_expressions）只警告"字符串里拼了变量"，无法区分
"拼的是 SQL 关键字/表名白名单"与"拼的是用户输入"。R28 收尾时 `analytics_service`
的 9 处按仓库约定在**多行 f-string 的收尾行**加了 `# nosec B608 - <理由>` 豁免，
但全仓还有 20+ 处同类写法未登记，且**没有任何门禁阻止新增** ——
"SQL 拼接必须人工复核并留下理由"这条规则此前零执行力。

策略：全量门禁（非棘轮）。任何 `text(f"...")` 调用的**完整语句范围**内
（ast 节点 lineno..end_lineno）必须出现 `# nosec B608` 且带理由：
`# nosec B608 - 表名来自白名单` / `# nosec B608 — FTS 表名为常量` 等。

为什么用 ast 而不是行扫描：SQL 文本里含有 `COUNT(*)`、`COALESCE(x, 0)`
这类括号，多行 f-string 的"拼括号"启发式会被 SQL 内容带偏；ast 给出的
Call 节点范围是精确的。

用法：
  python scripts/check_raw_sql_fstrings.py                # 门禁（有未登记即失败）
  python scripts/check_raw_sql_fstrings.py --list         # 仅列出全部调用点
"""
import argparse
import ast
import re
import sys
from pathlib import Path

# ── Windows CI/本地控制台编码兜底：脚本输出中文，cp936/cp1252 下会 UnicodeEncodeError ──
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPO / "backend" / "app"

# 与 bandit 的豁免注释同形；理由 = 分隔符（- — : ：）后至少 2 个非空字符
_NOSEC_RE = re.compile(r"#\s*nosec\s+B608(?P<tail>.*)$")
_REASON_RE = re.compile(r"^\s*(?:[—\-–:：]\s*\S|\s*#\s*\S)")


def is_text_call(node: ast.Call) -> bool:
    """是否 `text(...)` / `xxx.text(...)` 调用。"""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "text"
    return isinstance(func, ast.Attribute) and func.attr == "text"


def contains_fstring(node: ast.Call) -> bool:
    """调用参数里是否含 f-string（JoinedStr）。"""
    return any(isinstance(arg, ast.JoinedStr) for arg in node.args)


def snippet_of(lines, start: int, end: int) -> str:
    """归一化代码片段（去掉行号影响，供报告定位）。"""
    text = " ".join(line.strip() for line in lines[start - 1:end])
    return re.sub(r"\s+", " ", text)[:150]


def has_reasoned_nosec(lines, start: int, end: int) -> bool:
    """语句范围内是否有带理由的 `# nosec B608`。"""
    for line in lines[start - 1:end]:
        m = _NOSEC_RE.search(line)
        if m and _REASON_RE.match(m.group("tail") or ""):
            return True
    return False


def scan_file(path: Path):
    """产出 (行号, 结束行号, 片段, 是否带理由豁免)。"""
    source = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_text_call(node) and contains_fstring(node):
            end = node.end_lineno or node.lineno
            found.append(
                (
                    node.lineno,
                    end,
                    snippet_of(lines, node.lineno, end),
                    has_reasoned_nosec(lines, node.lineno, end),
                )
            )
    return found


def display_path(path: Path) -> str:
    """报告用路径：仓库内给相对路径，仓库外（测试用探测目录）退回绝对路径。"""
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="text(f-string) SQL 必须带 # nosec B608 理由")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="扫描根目录（默认 backend/app）")
    parser.add_argument("--list", action="store_true", help="仅列出全部调用点（不判定失败）")
    args = parser.parse_args()

    root = Path(args.root)
    total, violations = 0, []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for lineno, _end, snippet, ok in scan_file(path):
            total += 1
            if not ok:
                violations.append((display_path(path), lineno, snippet))

    print("=== text(f-string) SQL 豁免检查 ===")
    print("调用点总数: %d，未登记理由: %d" % (total, len(violations)))
    if args.list:
        return 0
    for rel, lineno, snippet in violations:
        print("MISSING: %s:%d  %s" % (rel, lineno, snippet))
        print("::error::%s:%d 的 text(f-string) 缺 `# nosec B608 - <理由>`" % (rel, lineno))
    if violations:
        print("\nERROR: 拼接 SQL 必须人工复核后在语句范围内注明理由，例如：")
        print('  text(f"SELECT COUNT(*) FROM {table}")  # nosec B608 - table 来自硬编码白名单')
        return 1
    print("OK: 全部拼接 SQL 均已登记豁免理由")
    return 0


if __name__ == "__main__":
    sys.exit(main())
