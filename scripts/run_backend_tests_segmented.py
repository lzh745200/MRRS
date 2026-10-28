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
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
COVERAGE_FILE = BACKEND_DIR / ".coverage"
LOG_DIR = BACKEND_DIR.parent / "logs" / "pytest-segments"
# 单实例锁：两个会话同时跑全量会互相重置 `.coverage` → 覆盖率假红（实测 28%/53%/82%）。
# 锁文件放在 backend/ 下（.gitignore 已忽略 .coverage* 之外的临时文件需显式忽略，见下）。
LOCK_FILE = BACKEND_DIR / ".pytest-segmented.lock"

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
    #
    # ⚠️ 2026-10-26 实测纠正（旧的注释写反了）：
    # coverage 的优先级是 **环境变量 COVERAGE_FILE > --cov-config 的 [run] data_file**。
    # 实验（同一份测试跑两次）：
    #   · 只给 --cov-config（data_file=.probe.seg7）→ 生成 .probe.seg7
    #   · 再设 COVERAGE_FILE=.probe.envwin        → 只生成 .probe.envwin，rc 被忽略
    # 因此**绝不**在逐段运行时设 COVERAGE_FILE：一旦设了，12 段全部追加进同一个文件，
    # 逐段分片不存在，`coverage combine` 只会得到 "No data to combine"
    # （这正是历史上每次全量跑都打印「覆盖率 combine 失败」的真正原因 ——
    #  而单文件累积"恰好"还能算出正确百分比，所以问题被长期忽略）。
    # 现在由调用方只传 cov_config（各段写自己的 `<data_file>.seg<N>`），
    # 全部段跑完后统一 combine。
    if cov_config:
        args += [f"--cov-config={cov_config}"]
    if cov_file:
        # 仅在**明确**要求单文件（如外部 CI 复用本函数）时才用；默认不传。
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


def _pid_alive(pid: int) -> bool:
    """进程是否还活着（用于识别崩溃遗留的陈旧锁）。

    注意：Windows 上绝不能直接用 os.kill(pid, 0) —— 它对任意 sig 都走
    TerminateProcess 语义，会把**正在跑的那个会话**杀掉（2026-10-28 实测）。
    这里改为 OpenProcess + GetExitCodeProcess 的只读探测。
    """
    if pid <= 0:
        return False

    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return False
                return code.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        except Exception:  # pragma: no cover - 极端平台差异
            return False

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except Exception:  # pragma: no cover - 非 POSIX/非 Windows 的异常实现兜底
        return True
    return True


def acquire_run_lock(lock_path: Path = LOCK_FILE, wait_seconds: int = 0) -> bool:
    """获取「同一时刻只允许一个分段全量」的锁（跨进程、跨平台、纯标准库）。

    背景（2026-10-28 实测两次）：两个会话同时跑 12 段时，后启动的会在清理阶段
    重置 `.coverage`，先启动的那次覆盖率判定就从 100% 掉成 28%/53% —— 表现为
    "12 段全 PASS 但覆盖率门禁红"，排查成本极高。加锁后第二个进程会直接得到
    可读提示，而不是静默互相破坏。

    实现：O_CREAT|O_EXCL 原子创建锁文件并写入 pid；已存在时读 pid 判断存活，
    陈旧锁（进程已退出）自动接管。wait_seconds>0 时轮询等待。

    Returns:
        True = 已持有锁；False = 超时仍未获取。
    """
    deadline = time.time() + max(wait_seconds, 0)
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, str(os.getpid()).encode("ascii"))
            finally:
                os.close(fd)
            return True
        except FileExistsError:
            stale = False
            try:
                holder = int(lock_path.read_text(encoding="ascii").strip() or "0")
            except (OSError, ValueError):
                holder = 0
            if holder and not _pid_alive(holder):
                stale = True
            elif not holder:
                # 空/不可读的锁文件：可能是创建瞬间被读到，给它一次机会
                time.sleep(0.2)
                try:
                    stale = lock_path.stat().st_size == 0
                except OSError:
                    stale = True
            if stale:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                continue
            if time.time() >= deadline:
                return False
            time.sleep(1.0)


def release_run_lock(lock_path: Path = LOCK_FILE) -> None:
    """释放锁（只删自己持有的那个文件；进程崩溃时依赖 pid 存活探测接管）。"""
    try:
        if lock_path.exists():
            lock_path.unlink()
    except OSError:  # pragma: no cover - 并发删除/只读介质
        pass


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
    parser.add_argument(
        "--wait-lock",
        type=int,
        default=0,
        metavar="SECONDS",
        help="另一个分段全量正在运行时的等待秒数（默认 0：立即退出；999 等很久）",
    )
    args = parser.parse_args()

    if args.list:
        for i, (name, patterns, _final) in enumerate(SEGMENTS, 1):
            print(f"{i:2d}. {name:24s} {' '.join(patterns)}")
        return 0

    if not BACKEND_DIR.is_dir():
        print(f"找不到 backend 目录: {BACKEND_DIR}", file=sys.stderr)
        return 1

    # 单实例锁（2026-10-28）：两个会话同时跑 12 段会互相重置 .coverage，
    # 表现为「12 段全 PASS 但覆盖率门禁红」（实测 28%/53%），排错成本极高。
    if not acquire_run_lock(wait_seconds=args.wait_lock):
        holder = ""
        try:
            holder = LOCK_FILE.read_text(encoding="ascii").strip()
        except OSError:
            pass
        print(
            f"另一个分段全量正在运行（锁 {LOCK_FILE}，pid={holder or '?'}）：\n"
            "  并发跑会互相重置 .coverage 导致覆盖率假红。\n"
            "  处理：等它跑完；或删掉该锁文件（确认无进程在跑）；"
            "或加 --wait-lock 秒数 排队。",
            file=sys.stderr,
        )
        return 3
    atexit.register(release_run_lock)

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
        # 中间文件一律放【系统临时目录】，不放 backend/：
        # 2026-10-26 实测 —— 多个会话并行跑全量时，后启动的一方会用
        # Get-ChildItem backend -Filter '.coveragerc.seg.*' | Remove-Item 之类通配
        # 清理自己的中间文件，**连带删掉本进程的 rc**，导致末段直接
        # ConfigError: Couldn't read ... as a config file（前 10 段全 PASS 却整轮红）。
        # 放进 mkdtemp 后与项目目录彻底无关，任何通配清理都碰不到。
        _tmp_dir = Path(tempfile.mkdtemp(prefix="mrrs-cov-"))
        cov_file_arg = str(_tmp_dir / f"coverage.gate.{stamp}")
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

        cov_config_path = _tmp_dir / f"coveragerc.gate.{stamp}"
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
            shutil.rmtree(_tmp_dir, ignore_errors=True)

        atexit.register(_cleanup_temp_cov_files)
        for idx, _seg in enumerate(SEGMENTS, 1):
            # 段数据文件名必须是 `<data_file>.<后缀>` —— coverage combine（无参）
            # 只按 `<data_file>.*` 的 glob 去找分片。历史写法是独立的
            # `.covseg.<stamp>.<idx>`，与 data_file 前缀不匹配 → combine 永远失败
            # （stdout 报 "No data to combine"，但代码只打印 stderr，于是只剩一行
            #  "覆盖率 combine 失败: "）；单段跑时还会把 28% 的残缺结果当门禁结论。
            seg_data = f"{cov_file_arg}.seg{idx}"
            seg_rc = _tmp_dir / f"coveragerc.seg.{stamp}.{idx}"
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
        # ⚠️ 两条实测结论（2026-10-26，均由实验确定，勿凭直觉改）：
        # ① 覆盖率数据的优先级是 **环境变量 COVERAGE_FILE > --cov-config 的 [run] data_file**；
        # ② 但 `--cov-config` 指定的 data_file **在走 pytest-cov 时不生效**
        #    （实测：只传 --cov-config，数据仍落在默认的 backend/.coverage）。
        # 因此分片只能靠 COVERAGE_FILE 指定：每段写成 `<base>.seg<N>`，
        # 全部跑完后 `coverage combine`（无参）按 `<data_file>.*` 合并回 `<base>`。
        # 历史 bug：早期把 `<base>` 本身当 COVERAGE_FILE 传给每段 → 12 段全追加进同一个
        # 文件、分片不存在 → combine 永远 "No data to combine"（而单文件累积"恰好"
        # 还能算出正确百分比，于是问题被长期忽略，只在单段运行时暴露成 28%）。
        _seg_cov_file = f"{cov_file_arg}.seg{i}" if seg_rcs else None
        code = run_segment(
            i, name, patterns, is_final, args.keep_logs, _seg_cov_file, _seg_rc
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
    # 覆盖率门禁：**只在跑完 12 段时**判定。单段运行（--segment）的累积数据
    # 天然不完整，把它的百分比当门禁结论只会产生假红灯（历史症状：单段跑报 28%）。
    if not args.skip_coverage_gate and selected != SEGMENTS:
        print("覆盖率门禁: 跳过（本次只跑了子集，比值无意义；全量请不带 --segment）")
    elif not args.skip_coverage_gate:
        env_cov = dict(os.environ)
        _cov_target = args.cov_file.strip()
        if _cov_target:
            env_cov["COVERAGE_FILE"] = _cov_target
        _rc_for_report = str(cov_config_path) if cov_config_path else ".coveragerc"
        # ⚠️ 只有 **--cov-unique**（多会话防覆盖模式）才需要合并分片：
        # 该模式下每段用 COVERAGE_FILE=`<base>.seg<N>` 写独立分片，必须 combine。
        # 默认模式（不带该开关）全部段都用 `--cov-append` 追进同一个 backend/.coverage，
        # **根本没有分片** —— 此时跑 combine 只会得到 "No data to combine"。
        # （历史代码无条件 combine：提示永远失败但被忽略，随后 report 读单文件仍正确，
        #  所以问题长期不可见；本轮曾误把该失败改成致命错误，反而让默认模式直接失败。）
        if seg_rcs:
            combine_cmd = [sys.executable, "-m", "coverage", "combine", f"--rcfile={_rc_for_report}"]
            combine = subprocess.run(
                combine_cmd,
                cwd=str(BACKEND_DIR), env=env_cov, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            if combine.returncode != 0:
                # coverage 把 "No data to combine" 一类提示写在 **stdout**，
                # 只打印 stderr 会得到一行空消息（历史坑）。
                detail = ((combine.stdout or "") + (combine.stderr or "")).strip()
                print(f"覆盖率 combine 失败（--cov-unique 分片合并）: {detail[-200:] or '(无输出)'}")
                print("=" * 70)
                return 1
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
    print(
        "全部段通过；覆盖率门禁已在上面按 .coveragerc(fail_under) 统一判定"
        if selected == SEGMENTS
        else f"子集段通过（本次只跑 {len(selected)} 段，覆盖率阈值未判定）"
    )
    if args.cov_file.strip():
        print(f"覆盖率数据文件: backend/{args.cov_file.strip()}（独立文件，不受其他会话清理影响）")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
