# -*- coding: utf-8 -*-
r"""覆盖率豁免（`# pragma: no cover`）理由检查 —— F2 ratchet（2026-09-12）。

背景：《架构评估整改配套约定》F2 条规定"豁免手段唯一（`# pragma: no cover`）
且**必须同行注明理由**，无理由的裸 pragma 视同违规"。但该规则此前**零执行力**：
实测 `backend/app` 有 170 处 pragma，其中 128 处没有理由 —— 规则写在文档里，
门禁里没有对应检查。

策略：**ratchet（棘轮）**，不下调覆盖率门禁，也不要求一次性补完 128 处历史欠账：

* 默认模式（CI 用）：只检查**本次改动新增的行**（`--diff-base <git-ref>`，
  取 `git diff -U0` 的新增行），新增/修改的 pragma 必须带理由；
* `--all` 模式：列出全部无理由 pragma（供分批清理用，**不阻断**）；
* `--max-bare N`：当全量裸 pragma 超过 N 时报错（防止一边清理一边新增抵消）。

"理由"的判定：pragma 之后同行出现 `—`/`-`/`:`/`：` 后带至少 2 个非空字符，
或紧跟 `#` 注释（如 `# pragma: no cover  # 说明...`）。
"""
import argparse
import re
import subprocess
import sys

# ── Windows CI 编码兜底：本脚本输出中文，cp1252 控制台下会 UnicodeEncodeError ──
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_PRAGMA_RE = re.compile(r"#\s*pragma:\s*no\s*cover(?P<tail>.*)$")
_REASON_RE = re.compile(r"^\s*(?:[—\-–:：]\s*\S|\s*#\s*\S)")

DEFAULT_PATHS = ("backend/app", "scripts")


def emit_error(message: str) -> None:
    """GitHub 注解（job 日志需 admin；注解可通过 API 匿名读取）。"""
    print("::error::%s" % message)
    sys.stdout.flush()


def has_reason(line: str) -> bool:
    """同行 pragma 之后是否带理由。"""
    m = _PRAGMA_RE.search(line)
    if not m:
        return True  # 该行没有 pragma
    return bool(_REASON_RE.match(m.group("tail") or ""))


def _pragma_comments(full_path: str):
    """用 tokenize 取**注释 token**，只在注释里找 pragma。

    为什么不用朴素行扫描：字符串里出现 `"# pragma: no cover"`（本脚本自身的实现行
    与 help 文案即是）会被误判成豁免 —— 自检实测报了 2 处假阳性。
    解析失败（文件语法错误）时退回行扫描，保证检查本身不崩。
    """
    import io as _io
    import tokenize

    try:
        with open(full_path, encoding="utf-8-sig", errors="replace") as fh:
            for tok in tokenize.generate_tokens(fh.readline):
                if tok.type == tokenize.COMMENT and "# pragma: no cover" in tok.string:
                    yield tok.start[0], tok.string
    except (tokenize.TokenError, SyntaxError, OSError):
        with _io.open(full_path, encoding="utf-8-sig", errors="replace") as fh:
            for lineno, line in enumerate(fh, 1):
                if "# pragma: no cover" in line:
                    yield lineno, line.rstrip("\n")


def iter_pragma_lines(paths):
    """遍历 python 文件，产出 (相对路径, 行号, pragma 注释内容)。"""
    import os

    for root in paths:
        for dirpath, _dirnames, filenames in os.walk(root):
            if "__pycache__" in dirpath:
                continue
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                full = os.path.join(dirpath, name)
                for lineno, comment in _pragma_comments(full):
                    yield full.replace("\\", "/"), lineno, comment


def changed_lines(base: str):
    """相对 `base` 的新增行：{(路径, 行号)}。

    包含两部分：工作区相对 base 的改动（git diff，含已暂存），以及
    **未跟踪的新文件**（git ls-files --others）—— 后者不被 git diff 覆盖，
    而"新文件里塞一个无理由 pragma"正是最容易漏掉的路径（自检时实测漏过）。
    """
    paths = ["backend/app", "scripts"]
    result = subprocess.run(
        ["git", "diff", "-U0", base, "--", *paths],
        capture_output=True,
    )
    diff = result.stdout.decode("utf-8", "replace")
    added = set()
    current = None
    new_lineno = 0
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:].strip()
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                new_lineno = int(m.group(1))
                count = int(m.group(2) or 1)
                if count == 0:
                    new_lineno = -1  # 纯删除块
        elif line.startswith("+") and not line.startswith("+++") and new_lineno > 0:
            added.add((current, new_lineno))
            new_lineno += 1

    others = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", *paths],
        capture_output=True,
    ).stdout.decode("utf-8", "replace").splitlines()
    for rel in others:
        rel = rel.strip().replace("\\", "/")
        if not rel.endswith(".py"):
            continue
        try:
            with open(rel, encoding="utf-8-sig", errors="replace") as fh:
                for lineno, _line in enumerate(fh, 1):
                    added.add((rel, lineno))
        except OSError:
            continue
    return added


def _rev_exists(ref: str) -> bool:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref + "^{commit}"],
        capture_output=True,
    ).returncode == 0


def resolve_base(explicit: str, allow_missing: bool):
    """决定 diff 基线。

    CI 里 `origin/main` 常常不存在（浅克隆）或**就等于 HEAD**（push 到 main 场景，
    此时 diff 恒为空、检查形同虚设）。因此按顺序挑选第一个"能解析且不等于 HEAD"
    的基线：origin/main → HEAD~1。都不可用则按 `--allow-missing-base` 决定
    是明确报错（默认）还是大声告警后跳过 —— 绝不静默通过。
    """
    candidates = []
    if explicit and explicit != "auto":
        candidates.append(explicit)
    else:
        candidates += ["origin/main", "HEAD~1"]
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True).stdout.decode().strip()

    for ref in candidates:
        if not _rev_exists(ref):
            continue
        sha = subprocess.run(
            ["git", "rev-parse", ref], capture_output=True
        ).stdout.decode().strip()
        if sha and sha != head:
            return ref, None

    message = "无可用 diff 基线（候选: %s；origin/main 缺失或等于 HEAD）" % ", ".join(candidates)
    if allow_missing:
        return None, message
    return "", message


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 # pragma: no cover 是否带理由（F2 ratchet）")
    parser.add_argument("--diff-base", default=None,
                        help="仅检查相对该 git ref 的新增行（CI 用）；auto=origin/main→HEAD~1")
    parser.add_argument("--allow-missing-base", action="store_true",
                        help="基线不可用时告警跳过（默认报错退出，避免静默通过）")
    parser.add_argument("--all", action="store_true", help="列出全部无理由 pragma（不阻断）")
    parser.add_argument("--max-bare", type=int, default=None,
                        help="全量裸 pragma 上限，超出即失败（防止新增抵消清理）")
    parser.add_argument("--paths", nargs="*", default=list(DEFAULT_PATHS))
    args = parser.parse_args()

    rows = list(iter_pragma_lines(args.paths))
    bare = [(p, n, line) for p, n, line in rows if not has_reason(line)]

    print("=== pragma 理由检查（F2 ratchet）===")
    print("pragma 总数: %d，无理由: %d" % (len(rows), len(bare)))

    failed = False

    if args.max_bare is not None and len(bare) > args.max_bare:
        print("ERROR: 无理由 pragma %d 处 > 上限 %d（一边清理一边新增会抵消）"
              % (len(bare), args.max_bare))
        emit_error("裸 pragma %d 处超过上限 %d" % (len(bare), args.max_bare))
        failed = True

    if args.diff_base:
        base, problem = resolve_base(args.diff_base, args.allow_missing_base)
        if base is None:
            print("WARNING: %s —— 跳过新增行校验（--max-bare 仍然生效）" % problem)
            print("::warning::pragma 新增行校验已跳过: %s" % problem)
            sys.stdout.flush()
        elif base == "":
            print("ERROR: %s" % problem)
            emit_error("pragma 检查无法确定 diff 基线: %s" % problem)
            return 2
        else:
            print("diff 基线: %s" % base)
            try:
                added = changed_lines(base)
            except Exception as exc:  # noqa: BLE001 — 取不到 diff 不静默通过
                print("ERROR: 无法计算 diff（%s）" % exc)
                emit_error("pragma 检查无法计算 diff: %s" % exc)
                return 2
            new_bare = [(p, n, line) for p, n, line in bare if (p, n) in added]
            print("本次新增/修改行中的裸 pragma: %d" % len(new_bare))
            for p, n, line in new_bare[:20]:
                print("  %s:%d  %s" % (p, n, line.strip()[:120]))
            if new_bare:
                print("ERROR: 新增豁免必须同行注明理由，例如："
                      "# pragma: no cover — 仅防御性兜底，测试无法注入")
                emit_error("新增 %d 处无理由 pragma（首个: %s:%d）"
                           % (len(new_bare), new_bare[0][0], new_bare[0][1]))
                failed = True

    if args.all:
        _print_all(bare)

    if failed:
        return 1
    print("OK: 豁免理由检查通过")
    return 0


def _print_all(bare) -> None:
    print("\n--- 全部无理由 pragma（分批清理清单）---")
    for p, n, line in bare:
        print("  %s:%d  %s" % (p, n, line.strip()[:120]))


if __name__ == "__main__":
    sys.exit(main())
