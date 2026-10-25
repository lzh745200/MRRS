#!/usr/bin/env python3
"""按 CI 的 12 段方式运行后端测试（本地一条命令等价 CI 门禁）。

## 为什么必须分段

单进程跑 `pytest tests/` 在本仓库会在约 88% 处直接崩溃 ——
`tests/unit/test_system_audit_api.py` 的 fixture teardown 调用
`engine.dispose()` 时触发 `Windows fatal exception: access violation`
（SQLAlchemy C 扩展 + SQLite 连接池释放路径）。崩溃前无任何 FAILED/ERROR，
所以这是**进程级不稳定**，不是测试失败。CI 因此在
`.github/workflows/pr-checks.yml` 里拆成 12 个独立进程段。

本地只有 `make test-backend`（单进程）时无法验证"覆盖率 100%"门禁，
文档说能跑、实际跑不完。本脚本把 CI 的分段逻辑搬到本地，Windows / Linux 通用，
覆盖率用 `--cov-append` 跨进程合并，最后一段由 `.coveragerc` 的 fail_under 判定。

## 用法

    python scripts/run_backend_tests_segmented.py            # 全部 12 段
    python scripts/run_backend_tests_segmented.py --segment 3 # 只跑第 3 段
    python scripts/run_backend_tests_segmented.py --list      # 列出分段
    python scripts/run_backend_tests_segmented.py --keep-logs # 保留每段日志

退出码：任一段失败即 1（与 CI 一致）。
"""

from __future__ import annotations

import argparse
import atexit
import glob
import os
import subprocess
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
COVERAGE_FILE = BACKEND_DIR / ".coverage"
LOG_DIR = BACKEND_DIR.parent / "logs" / "pytest-segments"

# (段名, 目标路径/glob 模式, 是否最后一段)
# 与 `.github/workflows/pr-checks.yml` 的 12 个 step 一一对应。
SEGMENTS = [
    ("seg01-integration", ["tests/integration", "tests/security"], False),
    ("seg02-unit-api", ["tests/unit/api"], False),
    (
        "seg03-unit-services",
        [
            "tests/unit/services",
            "tests/unit/middleware",
            "tests/unit/interfaces",
            "tests/unit/utils",
        ],
        False,
    ),
    ("seg04-unit-root-a", ["tests/unit/test_a*.py", "tests/unit/test_e*.py", "tests/unit/test_f*.py"], False),
    ("seg05-unit-root-i", ["tests/unit/test_i*.py", "tests/unit/test_n*.py", "tests/unit/test_o*.py"], False),
    ("seg06-unit-root-p", ["tests/unit/test_p*.py", "tests/unit/test_t*.py", "tests/unit/test_u*.py"], False),
    ("seg07-unit-root-w", ["tests/unit/test_w*.py", "tests/unit/test_y*.py", "tests/unit/test_z*.py"], False),
    ("seg08-unit-root-b", ["tests/unit/test_b*.py", "tests/unit/test_d*.py"], False),
    (
        "seg09-unit-root-g",
        [
            "tests/unit/test_g*.py",
            "tests/unit/test_h*.py",
            "tests/unit/test_j*.py",
            "tests/unit/test_l*.py",
        ],
        False,
    ),
    ("seg10-unit-root-m", ["tests/unit/test_m*.py", "tests/unit/test_q*.py", "tests/unit/test_s*.py"], False),
    ("seg11-tests-root", ["tests/test_*.py"], False),
    ("seg12-unit-root-c", ["tests/unit/test_c*.py", "tests/unit/test_r*.py", "tests/unit/test_v*.py"], True),
]


def resolve_targets(patterns, backend_dir: Path):
    """把 glob 模式展开为 pytest 可接受的路径列表（相对 backend/）。

    目录直接保留；glob 无命中则跳过该模式（避免 pytest 报 file not found）。
    """
    resolved = []
    for pattern in patterns:
        candidate = backend_dir / pattern
        if candidate.is_dir():
            resolved.append(pattern)
            continue
        matches = sorted(glob.glob(str(candidate)))
        if matches:
            resolved.extend(
                os.path.relpath(m, str(backend_dir)).replace("\\", "/") for m in matches
            )
    return resolved


def run_segment(index, name, patterns, is_final, keep_logs, cov_file=None, cov_config=None):
    targets = resolve_targets(patterns, BACKEND_DIR)
    if not targets:
        print(f"[{index:02d}/12] {name}: 无匹配目标，跳过")
        return 0

    args = [
        sys.executable, "-m", "pytest", *targets, "-q", "--tb=short", "-rR",
        # 与 CI 的 scripts/ci_backend_test_segment.sh 逐项对齐：
        #   --cov-branch   显式启用分支覆盖（.coveragerc 里 branch=True 在
        #                  pytest-cov 用 --cov 指定 source 时不保证生效，
        #                  CI 显式传，本地也必须显式传，否则两边口径不同）
        #   --cov-report=  非末段抑制报告（CI 同款；避免每段都渲染大表）
        #   --reruns 2     与 CI 同款重试（消除顺序相关 flaky 的假失败）
        "--cov=app", "--cov-branch", "--cov-append",
        "--reruns", "2", "--reruns-delay", "1",
    ]
    if is_final:
        # 末段输出报表；但**不在此处判定阈值** —— 多会话并发时，段内读到的可能是
        # 被别的进程中途改写的残缺数据（历史症状：每段都 PASS，末段却报 53%）。
        # 真正的 fail_under 判定放到全部段跑完之后统一执行（见 main）。
        args += [
            "--cov-report=term-missing",
            "--cov-report=json:coverage-branch.json",
            "--cov-fail-under=0",
        ]
    else:
        args += ["--cov-report=", "--cov-fail-under=0"]

    env = dict(os.environ)
    # 多会话并发：把覆盖率数据写到独立文件，避免彼此的 --cov-append 互相覆盖。
    # 症状：每段都 PASS，但最终 report 只有 50~75%（仿佛分片丢失）。
    # 注意：pytest-cov **不读** COVERAGE_FILE 环境变量，必须走 --cov-config 的
    # [run] data_file（实测：仅设 env 时数据仍写默认 .coverage）。
    if cov_config:
        args += [f"--cov-config={cov_config}"]
    if cov_file:
        env["COVERAGE_FILE"] = cov_file
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    # 与 CI 一致：崩溃时打出 Python 级栈便于定位
    env.setdefault("PYTHONFAULTHANDLER", "1")

    print(f"[{index:02d}/12] {name}: {len(targets)} 个目标")
    started = time.time()
    proc = subprocess.run(args, cwd=str(BACKEND_DIR), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    elapsed = time.time() - started
    output = (proc.stdout or "") + (proc.stderr or "")

    log_path = None
    if keep_logs:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"{name}.log"
        log_path.write_text(output, encoding="utf-8")

    tail = [line for line in output.splitlines() if line.strip()][-1:] or [""]
    status = "PASS" if proc.returncode == 0 else "FAIL"
    print(f"           {status} ({elapsed:.0f}s) {tail[0][:150]}")
    if proc.returncode != 0:
        print("           ---- 失败信号 ----")
        for line in output.splitlines():
            if any(k in line for k in ("FAILED", "ERROR", "Fatal", "INTERNALERROR", "Coverage failure")):
                print(f"           {line[:200]}")
        if log_path:
            print(f"           完整日志: {log_path}")
    return proc.returncode


def main():
    parser = argparse.ArgumentParser(description="按 CI 12 段运行后端测试")
    parser.add_argument("--segment", type=int, help="只跑指定段（1-12）")
    parser.add_argument("--list", action="store_true", help="列出分段")
    parser.add_argument("--keep-logs", action="store_true", help="保留每段日志到 logs/pytest-segments/")
    parser.add_argument("--fresh", action="store_true", help="运行前清理 .coverage（默认清理）")
    parser.add_argument("--keep-coverage", action="store_true", help="保留既有 .coverage 继续追加")
    parser.add_argument(
        "--cov-file",
        default="",
        help="覆盖率数据文件（相对 backend）。多会话并发时用独立文件",
    )
    parser.add_argument(
        "--cov-unique",
        action="store_true",
        help="自动生成含 PID 与时间戳的覆盖率数据文件（多会话并发时彻底避免同名覆盖）",
    )
    parser.add_argument(
        "--skip-coverage-gate",
        action="store_true",
        help="跳过跑完后的统一覆盖率判定（仅排障用）",
    )
    args = parser.parse_args()

    if args.list:
        for i, (name, patterns, _final) in enumerate(SEGMENTS, 1):
            print(f"{i:2d}. {name:24s} {' '.join(patterns)}")
        return 0

    if not BACKEND_DIR.is_dir():
        print(f"找不到 backend 目录: {BACKEND_DIR}", file=sys.stderr)
        return 1

    # 覆盖率门禁依赖 backend/.coveragerc 的 fail_under；文件缺失时 pytest-cov 退回默认
    # 配置，门禁会【静默失效】（历史踩坑：清理分片误删它）。此处 fail-fast。
    coveragerc = BACKEND_DIR / ".coveragerc"
    if not coveragerc.is_file():
        print(
            "错误: backend/.coveragerc 缺失 —— 覆盖率门禁会静默失效。恢复: git checkout -- backend/.coveragerc",
            file=sys.stderr,
        )
        return 2

    cov_file_arg = args.cov_file.strip()
    cov_config_path = None
    seg_rcs: list[tuple[str, str]] = []
    if args.cov_unique:
        # 每段写**自己的**数据文件，全部跑完后 coverage combine 合并。
        # 实测两条路都不可靠：--cov-append 在多段独立进程下只留最后一段；
        # [run] parallel 会被 pytest-cov 覆盖。故直接每段一个 data_file。
        stamp = f"{os.getpid()}-{time.strftime('%Y%m%d-%H%M%S')}"
        cov_file_arg = f".coverage.gate.{stamp}"
        base_rc = coveragerc.read_text(encoding="utf-8")

        def _rc_with_data_file(target: str) -> str:
            """把 data_file 插进 [run] 段（coverage 不允许它出现在别的段）。"""
            ls = base_rc.splitlines()
            out_ls, ok = [], False
            for one in ls:
                out_ls.append(one)
                if not ok and one.strip() == "[run]":
                    out_ls.append(f"data_file = {target}")
                    ok = True
            if not ok:
                out_ls = ["[run]", f"data_file = {target}", ""] + ls
            return "\n".join(out_ls) + "\n"

        cov_config_path = BACKEND_DIR / f".coveragerc.gate.{stamp}"
        cov_config_path.write_text(_rc_with_data_file(cov_file_arg), encoding="utf-8")
        # --cov-unique 会生成 .coveragerc.gate.* / .coveragerc.seg.* / .covseg.* 中间文件，
        # 属于纯粹的本机临时产物：跑完（含异常退出）必须自行清理，否则每次跑全量都会
        # 在 backend/ 下留下一堆未跟踪文件（2026-10-25 实测一次 12 段留 13 个）。
        _temp_paths: list[Path] = [cov_config_path]

        def _cleanup_temp_cov_files() -> None:
            for _p in _temp_paths:
                try:
                    _p.unlink(missing_ok=True)
                except OSError:
                    pass

        atexit.register(_cleanup_temp_cov_files)
        for idx, _seg in enumerate(SEGMENTS, 1):
            seg_data = f".covseg.{stamp}.{idx}"
            seg_rc = BACKEND_DIR / f".coveragerc.seg.{stamp}.{idx}"
            seg_rc.write_text(_rc_with_data_file(seg_data), encoding="utf-8")
            _temp_paths.append(seg_rc)
            _temp_paths.append(BACKEND_DIR / seg_data)
            seg_rcs.append((seg_data, str(seg_rc)))
    data_file = (BACKEND_DIR / cov_file_arg) if cov_file_arg else COVERAGE_FILE
    if not args.keep_coverage and data_file.exists():
        data_file.unlink()
        # 精确匹配 .coverage.*；**不要**用 .coverage*（会连 .coveragerc 一起删）
        for stale in BACKEND_DIR.glob(".coverage.*"):
            stale.unlink(missing_ok=True)

    selected = SEGMENTS
    if args.segment:
        if not 1 <= args.segment <= len(SEGMENTS):
            print(f"--segment 取值 1-{len(SEGMENTS)}", file=sys.stderr)
            return 2
        selected = [SEGMENTS[args.segment - 1]]

    print("=" * 70)
    print("后端测试（CI 12 段等价；单进程跑全量会在 88% 处进程崩溃）")
    print("=" * 70)

    failures = []
    started = time.time()
    for i, (name, patterns, is_final) in enumerate(SEGMENTS, 1):
        if selected != SEGMENTS and SEGMENTS[i - 1] not in selected:
            continue
        _seg_rc = seg_rcs[i - 1][1] if seg_rcs else None
        code = run_segment(
            i, name, patterns, is_final, args.keep_logs, cov_file_arg or None, _seg_rc
        )
        if code != 0:
            failures.append(name)

    print("=" * 70)
    print(f"总耗时 {time.time() - started:.0f}s")
    if failures:
        print(f"失败段 ({len(failures)}): {', '.join(failures)}")
        print("=" * 70)
        return 1

    # 覆盖率门禁：全部段跑完后，对**累积数据**统一判定一次。
    # 与"末段内联报告"相比，这里读的是所有段写入完毕后的最终文件，
    # 不会被并发会话的中途读写打断（历史症状：末段报 53%）。
    if not args.skip_coverage_gate:
        env_cov = dict(os.environ)
        _cov_target = args.cov_file.strip()
        if _cov_target:
            env_cov["COVERAGE_FILE"] = _cov_target
        _rc_for_report = str(cov_config_path) if cov_config_path else ".coveragerc"
        # 每段一个独立 data_file → 先 combine 成一份，再 report。
        _seg_files = [d for d, _rc in seg_rcs]
        combine_cmd = [sys.executable, "-m", "coverage", "combine", f"--rcfile={_rc_for_report}"]
        if _seg_files:
            combine_cmd += _seg_files
        combine = subprocess.run(
            combine_cmd,
            cwd=str(BACKEND_DIR), env=env_cov, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if combine.returncode != 0:
            print(f"覆盖率 combine 失败: {(combine.stderr or '').strip()[:150]}")
        report = subprocess.run(
            [sys.executable, "-m", "coverage", "report", f"--rcfile={_rc_for_report}"],
            cwd=str(BACKEND_DIR), env=env_cov, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        tail = [ln for ln in (report.stdout or "").splitlines() if ln.strip()][-1:] or [""]
        print(f"覆盖率门禁: {tail[0].strip()[:150]}")
        if report.returncode != 0:
            out = (report.stdout or "") + (report.stderr or "")
            for line in out.splitlines():
                if "Coverage failure" in line or line.startswith("TOTAL"):
                    print(f"  {line.strip()[:200]}")
            print("=" * 70)
            return 1
    # 清理 --cov-unique 生成的临时 rc（数据文件本身保留供复核/排障）
    for _data, _rc in seg_rcs:
        try:
            Path(_rc).unlink(missing_ok=True)
        except OSError:
            pass
    print("全部段通过；覆盖率门禁已在上面按 .coveragerc(fail_under) 统一判定")
    if args.cov_file.strip():
        print(f"覆盖率数据文件: backend/{args.cov_file.strip()}（独立文件，不受其他会话清理影响）")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
