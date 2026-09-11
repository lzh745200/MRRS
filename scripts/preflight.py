#!/usr/bin/env python3
"""本地门禁脚本 —— 一次跑齐镜像 CI 六 job 的本地门禁。

设计目标
--------
CI（``.github/workflows/pr-checks.yml``）在 Linux/Node22 上跑六个 job。
本脚本在开发者本机（Windows / Linux）以**同口径**复跑这些门禁，输出
PASS/FAIL/SKIP 摘要与统一退出码（任一阻断门失败 → ``exit 1``），
使开发者提交前即可发现 CI 会拦下的问题。

为什么是 Python 而非 ``.sh``
----------------------------
本仓同时支持 Windows 本地开发与 Linux CI，``.sh`` 在 Windows 不可用；
Python 跨平台且本仓后端已是 Python 工程。

门禁映射（G1..G6）
------------------
======== ================ ====================================================
门        CI job           本地命令要点
======== ================ ====================================================
G1       backend-test     ``cd backend && <py> -m pytest tests/ -q --cov=app``
G2       frontend-check   ``cd frontend && npx vue-tsc --noEmit && npm run
                          lint:check && npx vitest run --coverage``
G3       lint             ``cd backend && <py> -m flake8 app/ ...`` +
                          ``bandit -r app/ -ll``（mypy 非阻断）
G4       security         ``cd frontend && npm audit --audit-level=high``
                          （pip-audit 非阻断）
G5       static-analysis  ``check_soft_delete_usage`` + ``sync-version --check``
                          + ``check_menu_alignment`` + ``security_audit --strict``
G6       e2e-test         ``cd frontend && npx playwright test``（重；
                          ``--fast`` / ``--skip-e2e`` 跳过）
======== ================ ====================================================

用法
----
    python scripts/preflight.py                 # 全部门禁
    python scripts/preflight.py --fast          # 跳过 E2E（G6）
    python scripts/preflight.py --skip-e2e      # 同 --fast
    python scripts/preflight.py --only G1,G5    # 只跑指定门
    python scripts/preflight.py --python /path/to/python   # 覆盖解释器
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND = PROJECT_ROOT / "backend"
FRONTEND = PROJECT_ROOT / "frontend"

IS_WINDOWS = os.name == "nt"

# 门禁标识（顺序即执行/展示顺序）
ALL_GATES = ("G1", "G2", "G3", "G4", "G5", "G6")

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_SKIP = "SKIP"


@dataclass
class GateResult:
    """单个门禁的执行结果。"""

    gate: str
    name: str
    status: str
    detail: str = ""


def _resolve_python(explicit: str | None) -> str:
    """解析后端解释器路径。

    优先级：``--python`` 显式参数 > 仓库内 venv（Win: Scripts/python.exe，
    Linux: bin/python）> 当前解释器 ``sys.executable``。
    """
    if explicit:
        return explicit

    candidates = (
        [BACKEND / ".venv" / "Scripts" / "python.exe", BACKEND / ".venv" / "python.exe"]
        if IS_WINDOWS
        else [BACKEND / ".venv" / "bin" / "python"]
    )
    for cand in candidates:
        if cand.exists():
            return str(cand)
    return sys.executable


def _npx(explicit_npx: str | None) -> str:
    """返回 npx 可执行名（Windows 需 ``.cmd`` 后缀）。"""
    if explicit_npx:
        return explicit_npx
    return "npx.cmd" if IS_WINDOWS else "npx"


def _npm(explicit_npm: str | None) -> str:
    """返回 npm 可执行名（Windows 需 ``.cmd`` 后缀）。"""
    if explicit_npm:
        return explicit_npm
    return "npm.cmd" if IS_WINDOWS else "npm"


def _node(explicit_node: str | None) -> str:
    """返回 node 可执行名。"""
    return explicit_node or "node"


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """执行一条命令，实时落盘到 stdout/stderr，返回 (returncode, combined_output)。

    采用 ``shell=False``（优先）；``capture_output=True`` 以提取失败摘要，
    同时把完整输出透传到控制台。
    """
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            shell=False,
        )
    except FileNotFoundError as exc:
        return 127, f"命令未找到: {exc}"
    combined = (proc.stdout or "") + (proc.stderr or "")
    sys.stdout.write(combined)
    sys.stdout.flush()
    return proc.returncode, combined


def _run_chain(steps: list[tuple[list[str], Path]]) -> tuple[int, str]:
    """顺序执行多条命令，遇非 0 立即短路返回。"""
    last = ""
    for cmd, cwd in steps:
        rc, out = _run(cmd, cwd)
        last = out
        if rc != 0:
            return rc, out
    return 0, last


# ════════════════════════════════════════════════════════════════════
#  各门禁实现
# ════════════════════════════════════════════════════════════════════

def gate_backend_test(py: str) -> GateResult:
    """G1 backend-test：pytest + 覆盖率（阈值由 backend/.coveragerc 承载）。"""
    rc, _ = _run_chain([([py, "-m", "pytest", "tests/", "-q", "--cov=app"], BACKEND)])
    return GateResult("G1", "backend-test", STATUS_PASS if rc == 0 else STATUS_FAIL, f"exit={rc}")


def gate_frontend_check(py: str, npx: str, npm: str) -> GateResult:
    """G2 frontend-check：vue-tsc + lint:check + vitest --coverage。"""
    rc, _ = _run_chain(
        [
            ([npx, "vue-tsc", "--noEmit"], FRONTEND),
            ([npm, "run", "lint:check"], FRONTEND),
            ([npx, "vitest", "run", "--coverage"], FRONTEND),
        ]
    )
    return GateResult("G2", "frontend-check", STATUS_PASS if rc == 0 else STATUS_FAIL, f"exit={rc}")


def gate_lint(py: str) -> GateResult:
    """G3 lint：flake8（阻断）+ bandit（阻断）+ mypy（非阻断）。"""
    rc, _ = _run_chain(
        [
            ([py, "-m", "flake8", "app/", "--max-line-length=120", "--count", "--max-complexity=16"], BACKEND),
            ([py, "-m", "bandit", "-r", "app/", "-ll"], BACKEND),
        ]
    )
    if rc != 0:
        return GateResult("G3", "lint", STATUS_FAIL, f"exit={rc}")
    # mypy 非阻断（与 CI 一致：|| true）
    _run([py, "-m", "mypy", "app/", "--ignore-missing-imports"], BACKEND)
    return GateResult("G3", "lint", STATUS_PASS, "flake8+bandit ok (mypy 非阻断)")


def gate_security(npm: str) -> GateResult:
    """G4 security：npm audit --audit-level=high（阻断）；pip-audit 非阻断。"""
    rc, _ = _run([npm, "audit", "--audit-level=high"], FRONTEND)
    status = STATUS_PASS if rc == 0 else STATUS_FAIL
    return GateResult("G4", "security", status, f"npm audit exit={rc} (pip-audit 非阻断)")


def gate_static_analysis(py: str, node: str) -> GateResult:
    """G5 static-analysis：软删扫描 + 版本一致性 + 菜单对齐 + 安全审计 --strict。"""
    rc, _ = _run_chain(
        [
            ([py, str(BACKEND / "scripts" / "check_soft_delete_usage.py")], PROJECT_ROOT),
            ([node, str(PROJECT_ROOT / "scripts" / "sync-version.js"), "--check"], PROJECT_ROOT),
            ([py, str(PROJECT_ROOT / "scripts" / "check_menu_alignment.py")], PROJECT_ROOT),
            ([py, str(PROJECT_ROOT / "scripts" / "security_audit.py"), "--strict"], PROJECT_ROOT),
        ]
    )
    return GateResult("G5", "static-analysis", STATUS_PASS if rc == 0 else STATUS_FAIL, f"exit={rc}")


def gate_e2e(py: str, npx: str) -> GateResult:
    """G6 e2e-test：Playwright（重；由 --fast/--skip-e2e 跳过）。"""
    rc, _ = _run_chain([([npx, "playwright", "test", "--reporter=line"], FRONTEND)])
    return GateResult("G6", "e2e-test", STATUS_PASS if rc == 0 else STATUS_FAIL, f"exit={rc}")


# ════════════════════════════════════════════════════════════════════
#  主流程
# ════════════════════════════════════════════════════════════════════

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地门禁（镜像 CI 六 job）")
    parser.add_argument("--fast", action="store_true", help="快速模式：跳过 E2E（G6）")
    parser.add_argument("--skip-e2e", action="store_true", help="跳过 E2E（G6）")
    parser.add_argument("--only", default=None, help="只跑指定门（逗号分隔，如 G1,G5）")
    parser.add_argument("--python", default=None, help="后端解释器路径（默认解析 backend/.venv）")
    parser.add_argument("--npx", default=None, help="npx 可执行名（默认 npx / npx.cmd）")
    parser.add_argument("--npm", default=None, help="npm 可执行名（默认 npm / npm.cmd）")
    parser.add_argument("--node", default=None, help="node 可执行名（默认 node）")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    py = _resolve_python(args.python)
    npx = _npx(args.npx)
    npm = _npm(args.npm)
    node = _node(args.node)

    skip_e2e = args.fast or args.skip_e2e

    if args.only:
        selected = [g.strip().upper() for g in args.only.split(",") if g.strip()]
        invalid = [g for g in selected if g not in ALL_GATES]
        if invalid:
            print(f"[preflight] --only 含未知门禁: {', '.join(invalid)}（有效: {', '.join(ALL_GATES)}）")
            return 2
    else:
        selected = list(ALL_GATES)

    print("=" * 64)
    print("本地门禁 preflight（镜像 CI 六 job）")
    print(f"python={py}")
    print(f"npx={npx}  npm={npm}  node={node}")
    print(f"门禁: {', '.join(selected)}" + ("  (--fast: 跳过 E2E)" if skip_e2e else ""))
    print("=" * 64)

    results: list[GateResult] = []
    for gate in ALL_GATES:
        if gate not in selected:
            continue
        print(f"\n--- {gate} ---")
        if gate == "G6" and skip_e2e:
            results.append(GateResult("G6", "e2e-test", STATUS_SKIP, "已按 --fast/--skip-e2e 跳过"))
            print("  SKIP（--fast/--skip-e2e）")
            continue

        if gate == "G1":
            res = gate_backend_test(py)
        elif gate == "G2":
            res = gate_frontend_check(py, npx, npm)
        elif gate == "G3":
            res = gate_lint(py)
        elif gate == "G4":
            res = gate_security(npm)
        elif gate == "G5":
            res = gate_static_analysis(py, node)
        else:  # G6
            res = gate_e2e(py, npx)
        results.append(res)

    print("\n" + "=" * 64)
    print("摘要")
    print("=" * 64)
    for res in results:
        line = f"{res.gate} {res.status:4} {res.name}"
        if res.detail:
            line += f"  ({res.detail})"
        print(line)

    failed = [r for r in results if r.status == STATUS_FAIL]
    total = len(results)
    print("-" * 64)
    print(f"Total: {total} gates, {len(failed)} failed")
    print("=" * 64)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
