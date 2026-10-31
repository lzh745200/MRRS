#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""仓库门禁统一入口（本地一键 = CI 同款）。

## 为什么需要

2026-10-28 体检时，29 道门禁的调用方式各不相同，我本人一天内就踩了三次：

- check_route_auth.py 必须在 backend/ 下跑（否则 ModuleNotFoundError: app）；
- check_branch_coverage.py 需要 --json coverage-branch.json --baseline ...（直接跑只得到
  argparse 报错，看起来像"门禁红了"）；
- check_type_debt.py 曾在 GBK 控制台崩掉（已修）。

门禁自己跑不起来 = 门禁失效。本脚本把「每个门禁在哪跑、带什么参数」固化成注册表，
本地一条命令与 CI 同款；并支持 --list / --only / --json 便于排查。

用法::

    python scripts/run_gates.py                # 跑全部（默认 keep-going）
    python scripts/run_gates.py --list         # 看注册表
    python scripts/run_gates.py --only changelog,office_formats
    python scripts/run_gates.py --slow         # 追加慢门禁（升级演练等）
    python scripts/run_gates.py --json         # 机器读

退出码：0 = 全绿；1 = 有红；2 = 用法错误。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PYTHON = sys.executable

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):  # 门禁输出含中文/符号，Windows GBK 控制台会崩
        _stream.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class Gate:
    """一条门禁：名字 + 工作目录 + 命令 + 说明。"""

    name: str
    cwd: Path
    argv: List[str]
    why: str = ""
    slow: bool = False
    requires: Optional[Path] = None  # 缺失则 SKIP（如需要构建产物/覆盖率 json）

    def command(self) -> List[str]:
        return [PYTHON, *self.argv]


def _gate(name: str, script: str, *, backend: bool = False, args: Optional[List[str]] = None,
          why: str = "", slow: bool = False, requires: Optional[Path] = None) -> Gate:
    return Gate(
        name=name,
        cwd=BACKEND if backend else ROOT,
        argv=[script, *(args or [])],
        why=why,
        slow=slow,
        requires=requires,
    )


# ── 注册表：与 .github/workflows/pr-checks.yml 一一对应（有单测守护）──
GATES: List[Gate] = [
    _gate("changelog", "scripts/check_changelog.py", why="当前版本必须已记录"),
    _gate("doc_numbers", "scripts/check_doc_numbers.py", args=["--full"], why="文档数字与实测一致"),
    _gate("office_formats", "scripts/check_office_formats.py", why="WPS 导入/导出格式"),
    _gate("menu_alignment", "scripts/check_menu_alignment.py", why="菜单单一源"),
    _gate("console_tab", "scripts/check_console_tab_mapping.py", why="console tab 与组件一致"),
    _gate("hardcoded_styles", "scripts/check_hardcoded_styles.py", why="硬编码色棘轮"),
    _gate("stack_alignment", "../scripts/check_stack_alignment.py", backend=True, why="前后端/库四层对齐"),
    _gate("route_auth", "../scripts/check_route_auth.py", backend=True, why="路由认证覆盖"),
    _gate("type_debt", "../scripts/check_type_debt.py", backend=True, args=["--no-mypy"],
          why="技术债棘轮（本地快速档，不含 mypy）"),
    _gate("error_leaks", "scripts/check_error_message_leaks.py", why="错误文案不泄技术细节"),
    _gate("raw_sql_fstrings", "scripts/check_raw_sql_fstrings.py", why="裸 SQL f-string 豁免理由"),
    _gate("update_log", "scripts/check_update_log.py", why="应用内更新日志与 CHANGELOG 一致"),
    _gate("constants_sync", "scripts/check_constants_sync.py", why="常量漂移"),
    _gate("css_vars", "scripts/check_css_vars.py", why="CSS 变量引用"),
    _gate("tokens_sync", "scripts/check_tokens_sync.py", why="设计 Token 同步"),
    _gate("migrations", "scripts/check_migrations.py", why="Alembic 迁移健康"),
    _gate("unused_scope", "scripts/check_unused_scope_params.py", why="作用域形参未使用"),
    _gate("userdata_path", "scripts/check_userdata_path_consistency.py", why="userData 目录口径"),
    _gate("no_print", "scripts/check_no_print.py", why="生产代码不得 print（Logger 唯一出口）"),
    _gate("dist_size", "scripts/check_dist_size.py", why="前端产物体积棘轮"),
    _gate("pagination_cap", "scripts/check_pagination_cap.py", backend=True, args=["--root", "."],
          why="分页硬上限"),
    _gate("soft_delete", "scripts/check_soft_delete_usage.py", backend=True, why="软删除过滤"),
    _gate("no_assert_tests", "scripts/check_no_assert_tests.py", backend=True, why="零断言测试棘轮"),
    _gate("foreign_keys", "scripts/check_foreign_keys.py", backend=True, why="外键一致性"),
    _gate("sync_coverage", "scripts/check_sync_coverage.py", backend=True, why="同步链覆盖"),
    _gate("os_exit", "scripts/check_os_exit.py", backend=True, why="禁止 os._exit"),
    _gate("unbounded_read", "scripts/check_unbounded_read.py", backend=True, why="禁止无界读取"),
    _gate("upload_endpoints", "scripts/check_upload_endpoints.py", backend=True, why="上传端点限长"),
    _gate("subprocess_encoding", "scripts/check_subprocess_encoding.py", backend=True, why="子进程编码"),
    _gate("dir_replace", "scripts/check_dir_replace.py", backend=True, why="目录替换安全"),
    _gate("scheduler_reg", "scripts/check_scheduler_registration.py", backend=True, why="定时任务注册"),
    _gate("silent_swallow", "scripts/check_silent_swallow.py", backend=True,
          why="except Exception 必须留痕或显式豁免（棘轮）"),
    _gate("mojibake", "scripts/scan_mojibake.py", args=["--check"], why="乱码/NUL/非 UTF-8"),
    _gate("pragma_reasons", "scripts/check_pragma_reasons.py",
          args=["--diff-base", "auto", "--allow-missing-base", "--max-bare", "0"],
          why="pragma 豁免必须写理由"),
    _gate("migration_evidence", "scripts/check_migration_self_evidence.py",
          why="会改 schema 的迁移必须自带旧库自证测试"),
    _gate("package_contract", "scripts/check_package_contract.py", backend=True,
          why="数据包 manifest 字段契约棘轮（删字段/改类型/改必填即红）"),
    # 需要真实实例 / 冻结产物：缺失或未构建自动 SKIP，不伪装成绿
    _gate("endpoint_500", "scripts/check_endpoint_500.py", backend=True, slow=True,
          why="逐 GET 端点巡检：无登录态返回 5xx 即红（--slow 启用）"),
    _gate("frozen_smoke", "scripts/check_frozen_smoke.py", backend=True, slow=True,
          requires=BACKEND / "dist" / "assistance-backend" / "assistance-backend.exe",
          why="冻结后端产物冒烟：导入自检 + 真实起服务"),
    # 需要构建产物或外部数据：缺失自动 SKIP，不伪装成绿
    _gate("branch_coverage", "../scripts/check_branch_coverage.py", backend=True,
          args=["--json", "coverage-branch.json",
                "--baseline", "scripts/gate_baselines/branch_coverage_baseline.json"],
          requires=BACKEND / "coverage-branch.json", slow=True,
          why="分支覆盖率棘轮（需新鲜 coverage-branch.json；默认跳过，--slow 启用）"),
    _gate("upgrade_rehearsal", "scripts/upgrade_rehearsal.py", backend=True, slow=True,
          why="旧库升级演练（慢，需后端依赖）"),
    # 性能基线只报警不阻断（CI 机器噪声大），--slow 时纳入观察
    _gate("bench", "scripts/bench.py", args=["--rows", "5000,20000"], slow=True,
          why="关键路径性能基线（5000/20000 两档，只报警不阻断）"),
    # 打 tag 前确认 main 的 PR Checks 已 success（需 gh 已登录 + 网络，默认跳过）
    _gate("main_ci", "scripts/check_main_ci.py", slow=True, why="tag 前确认 main CI 已绿"),
]


def run_one(gate: Gate) -> dict:
    if gate.requires is not None and not gate.requires.exists():
        return {"gate": gate.name, "status": "SKIP", "seconds": 0.0,
                "tail": "缺少 " + str(gate.requires.relative_to(ROOT))}
    started = time.time()
    try:
        proc = subprocess.run(
            gate.command(), cwd=str(gate.cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=900,
        )
    except subprocess.TimeoutExpired:
        return {"gate": gate.name, "status": "FAIL", "seconds": time.time() - started,
                "tail": "超时 900s"}
    seconds = time.time() - started
    output = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    tail = output[-1].strip() if output else ""
    return {
        "gate": gate.name,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "seconds": seconds,
        "tail": tail[:200],
        "output": output,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="仓库门禁统一入口")
    parser.add_argument("--list", action="store_true", help="列出注册的门禁")
    parser.add_argument("--only", default="", help="逗号分隔的门禁名（默认全部）")
    parser.add_argument("--slow", action="store_true", help="包含慢门禁（默认跳过）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--stop-on-fail", action="store_true", help="遇到第一个红就停")
    args = parser.parse_args(argv)

    selected = [gate for gate in GATES if args.slow or not gate.slow]
    if args.only:
        wanted = {name.strip() for name in args.only.split(",") if name.strip()}
        unknown = wanted - {gate.name for gate in GATES}
        if unknown:
            print("未知门禁: " + ", ".join(sorted(unknown)) + "（用 --list 查看）", file=sys.stderr)
            return 2
        selected = [gate for gate in selected if gate.name in wanted]
    if not selected:
        print("没有选中任何门禁", file=sys.stderr)
        return 2

    if args.list:
        for gate in selected:
            rel = gate.cwd.relative_to(ROOT).as_posix() or "."
            print(f"{gate.name:22s} cwd={rel:8s} " + " ".join(gate.argv) + "  # " + gate.why)
        return 0

    results = []
    for gate in selected:
        result = run_one(gate)
        results.append(result)
        if not args.json:
            icon = {"PASS": "OK  ", "FAIL": "RED ", "SKIP": "SKIP"}[result["status"]]
            print(f"{icon} {result['gate']:22s} {result['seconds']:6.1f}s  {result['tail']}")
        if result["status"] == "FAIL" and args.stop_on_fail:
            break

    failed = [r for r in results if r["status"] == "FAIL"]
    skipped = [r for r in results if r["status"] == "SKIP"]
    if args.json:
        print(json.dumps({"ok": not failed, "results": results}, ensure_ascii=False, indent=2))
    else:
        print("=" * 70)
        print(f"合计 {len(results)} 道：PASS {len(results) - len(failed) - len(skipped)}"
              f" / FAIL {len(failed)} / SKIP {len(skipped)}")
        if failed:
            print("失败门禁：" + ", ".join(r["gate"] for r in failed))
            for result in failed:
                print("-" * 70)
                print("[" + result["gate"] + "] 输出尾部：")
                for line in result.get("output", [])[-25:]:
                    print("  " + line)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
