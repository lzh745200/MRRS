#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""静默吞异常门禁（棘轮，2026-10-28）。

## 为什么

仓库里 `except Exception` 有 800+ 处，其中一部分**既不记日志也不重新抛出** —— 这类不是
"兜底"，而是"故障被彻底吞掉"：现场只看到功能没反应，日志里连一行线索都没有，
排查成本极高（本轮体检用 AST 扫出 67 处）。

本门禁不要求把所有 `except Exception` 换成具体异常（很多地方确实需要兜底），只锁一件事：
**兜底必须留痕或显式声明豁免**。合规写法：

    except Exception:
        logger.warning("xxx 失败：%s", exc, exc_info=True)   # 留痕 ✓

    except Exception:
        raise                                                # 重新抛出 ✓

    except Exception:  # nosec:swallow - 关闭日志 handler 时的兜底，logger 已不可用
        pass                                                 # 显式豁免 ✓（必须写理由）

## 约定

- 基线：backend/scripts/gate_baselines/silent_swallow.txt（一行一条，只减不增）
- 清理后跑 `--baseline` 收敛；`STALE BASELINE` 提示哪些已被修好

用法::

    python backend/scripts/check_silent_swallow.py
    python backend/scripts/check_silent_swallow.py --baseline   # 人工确认后写回基线
"""

import ast
import re
import sys

from _gate_common import BACKEND, iter_py_files, rel, run_gate

GATE = "silent_swallow"
EXEMPT_MARKER = "nosec:swallow"
# 只认真实的 Exception / BaseException：HTTPException、CancelledError 等是具体异常，
# 不属于「宽泛兜底」，不该被本门禁检查（2026-10-28 修：原先前缀匹配把它们也算进来）。
EXCEPTION_TYPE_RE = re.compile(r"(?<![A-Za-z_])(?:Base)?Exception\b")
# 日志调用标记
LOG_MARKERS = ("logger", "logging", "_log", "warn(", "warning(", "error(", "exception(", "print(")
# 失败已"显式外化"到输出里的标记：把 error_type / failed / unavailable 等写进返回值或结果字典，
# 也算没吞掉（诊断类接口就是这种模式：把错误类型回给调用方，而不是记日志）。
SURFACED_MARKERS = ("error", "failed", "failure", "unavailable", "degraded", "exception")


def _is_logging_call(node: ast.AST) -> bool:
    """判断节点是否是日志调用（按源码片段粗判，够用且不误伤）。"""
    return any(marker in ast.dump(node) for marker in LOG_MARKERS)


def _surfaces_error(node: ast.ExceptHandler) -> bool:
    """失败是否被"外化"到输出里（返回/写入 error_type、failed、unavailable 等字段）。"""
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            low = child.value.lower()
            if any(marker in low for marker in SURFACED_MARKERS):
                return True
    return False


def _handler_is_silent(node: ast.ExceptHandler, segment: str) -> bool:
    """既不打日志、也不重新抛出、也不把失败外化到输出，且未显式豁免 → 视为静默吞异常。"""
    if EXEMPT_MARKER in segment.split("\n", 1)[0]:
        return False
    for child in node.body:
        if isinstance(child, ast.Raise):
            return False
        if isinstance(child, (ast.Expr, ast.Assign, ast.Return, ast.If, ast.Try)):
            if _is_logging_call(child):
                return False
    if _surfaces_error(node):
        return False
    return True


def scan_text(rel_path: str, text: str) -> list:
    violations = []
    try:
        tree = ast.parse(text)
    except SyntaxError:  # pragma: no cover - 语法错误由别的门禁/CI 处理
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or node.type is None:
            continue
        type_src = ast.get_source_segment(text, node.type) or ""
        if not EXCEPTION_TYPE_RE.search(type_src):
            continue
        segment = ast.get_source_segment(text, node) or ""
        if not _handler_is_silent(node, segment):
            continue
        code = "except %s" % type_src.replace("\n", " ").strip()
        violations.append("%s:%d:%s" % (rel_path, node.lineno, code))
    return violations


def main() -> int:
    violations = []
    for path in iter_py_files(BACKEND / "app"):
        violations.extend(scan_text(rel(path), path.read_text(encoding="utf-8", errors="replace")))
    return run_gate(GATE, violations)


if __name__ == "__main__":
    sys.exit(main())