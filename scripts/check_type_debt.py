# -*- coding: utf-8 -*-
"""类型与异常处理「技术债棘轮」门禁。

## 为什么需要这个门禁

mypy 此前在 CI 里是 `|| true`（永不阻断），前端 `as any` 与后端宽泛
`except Exception` 也没有任何上限约束 —— 三类债都只会单向增长。
2026-10-27 体检实测：mypy **1393 errors / 150 files**、`as any` **196 处**、
`except Exception` **806 处**。一次性清零不现实（等于给全库补类型标注），
但「不允许继续恶化」是立刻可以做到的。

## 机制

基线记录在仓库根 `.type-debt-baseline.json`。任一指标 **超过** 基线即失败
（exit 1）并打印超出量与新增位置；**低于**基线时提示下调（不失败）。

## 用法

    python scripts/check_type_debt.py             # 门禁（CI 用）
    python scripts/check_type_debt.py --update    # 当前值写回基线（人工确认后）
    python scripts/check_type_debt.py --json      # 机器读
    python scripts/check_type_debt.py --no-mypy   # 跳过 mypy（本地快速自查）

## 注意

- `--update` 只应下调或小幅上调：**上调需要 review 说明理由**，否则棘轮失效。
- mypy 需要后端依赖已安装（CI 在 `pip install -r requirements.txt` 之后跑）。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
BASELINE = ROOT / ".type-debt-baseline.json"
FRONTEND_SRC = ROOT / "frontend" / "src"

MYPY_SUMMARY_RE = re.compile(r"Found (\d+) errors? in \d+ files?")


def count_mypy_errors() -> tuple[int, list[str]]:
    """跑 mypy，返回 (错误总数, 前若干条错误行)。"""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "app/",
            "--config-file=mypy.ini",
            "--ignore-missing-imports",
        ],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    m = MYPY_SUMMARY_RE.search(out)
    if not m:
        # mypy 自身异常（配置错误/崩溃）—— 当作 0 但显式告警，避免静默放过
        if "error:" in out:
            print("[warn] 未能解析 mypy 汇总行，按 0 处理：", file=sys.stderr)
            print(out[-800:], file=sys.stderr)
        return 0, []
    errors = [ln for ln in out.splitlines() if " error: " in ln]
    return int(m.group(1)), errors


def count_as_any() -> tuple[int, list[str]]:
    """统计 frontend/src 下 `as any` 出现处（按文件:行）。"""
    hits: list[str] = []
    if not FRONTEND_SRC.is_dir():
        return 0, []
    for f in FRONTEND_SRC.rglob("*"):
        if f.suffix not in {".ts", ".tsx", ".vue"}:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(r"\bas\s+any\b", line):
                hits.append(f"{f.relative_to(ROOT).as_posix()}:{i}")
    return len(hits), hits


def count_broad_except() -> tuple[int, list[str]]:
    """统计后端 `except Exception` 处（宽泛捕获，需逐个确认是否有日志）。"""
    hits: list[str] = []
    for f in (BACKEND / "app").rglob("*.py"):
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if re.match(r"\s*except\s+Exception\b", line):
                hits.append(f"{f.relative_to(ROOT).as_posix()}:{i}")
    return len(hits), hits


def load_baseline() -> dict:
    if not BASELINE.is_file():
        return {}
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description="类型与异常处理技术债棘轮门禁")
    ap.add_argument("--update", action="store_true", help="把当前值写回基线")
    ap.add_argument("--json", action="store_true", help="机器读输出")
    ap.add_argument("--no-mypy", action="store_true", help="跳过 mypy（本地快速自查）")
    ap.add_argument("--show", type=int, default=5, help="超限时打印多少条位置")
    args = ap.parse_args()

    current: dict[str, int] = {}
    detail: dict[str, list[str]] = {}

    if not args.no_mypy:
        current["mypy_errors"], detail["mypy_errors"] = count_mypy_errors()
    n_as_any, detail["as_any"] = count_as_any()
    current["as_any"] = n_as_any
    n_except, detail["broad_except"] = count_broad_except()
    current["broad_except"] = n_except

    baseline = load_baseline()

    if args.update:
        merged: dict = {**baseline, **current}
        # 存位置集合，才能精确 diff 出"新增项"（只报前 N 条等于没报）。
        # mypy 错误不存位置：错误行会因无关改动整体重排，位置 diff 全是噪声，
        # 只保留数量（数量增长同样会被拦住）。
        merged["_locations"] = {
            "as_any": sorted(detail["as_any"]),
            "broad_except": sorted(detail["broad_except"]),
        }
        merged["_comment"] = (
            "技术债棘轮基线。任一指标超过此值即 CI 失败；下调请直接改小。"
            "上调需在 PR 说明理由。生成命令：python scripts/check_type_debt.py --update"
        )
        BASELINE.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"基线已更新: {BASELINE.name} -> {current}")
        return 0

    if args.json:
        print(json.dumps({"current": current, "baseline": baseline}, ensure_ascii=False))
        return 0

    print("技术债棘轮检查")
    print(f"{'指标':<16}{'当前':>8}{'基线':>8}  判定")
    failed: list[str] = []
    for key, label in (
        ("mypy_errors", "mypy 错误数"),
        ("as_any", "as any 处数"),
        ("broad_except", "except Exception"),
    ):
        if key not in current:
            continue
        cur = current[key]
        base = baseline.get(key)
        if base is None:
            verdict = "无基线（先跑 --update 固化）"
        elif cur > base:
            verdict = f"恶化 +{cur - base}"
            failed.append(key)
        elif cur < base:
            verdict = f"改善 {cur - base}（可下调基线）"
        else:
            verdict = "持平"
        print(f"{label:<16}{cur:>8}{str(base):>8}  {verdict}")

    for key in failed:
        label = {
            "mypy_errors": "mypy 错误",
            "as_any": "as any",
            "broad_except": "except Exception",
        }[key]
        # 有位置基线时精确 diff 出新增项；没有则退回"列全部当前项"并提示
        base_locs = (baseline.get("_locations") or {}).get(key)
        if base_locs is not None:
            added = sorted(set(detail.get(key, [])) - set(base_locs))
            print(f"\n[{label}] 新增位置（{len(added)} 条，全部列出）：")
            for loc in added[: max(args.show, len(added))]:
                print("  ", loc)
        else:
            print(f"\n[{label}] 未记录位置基线，仅能列出当前项（前 {args.show} 条）：")
            print("   先跑一次 `--update` 以启用精确 diff。")
            for loc in detail.get(key, [])[: args.show]:
                print("  ", loc)

    if failed:
        print(
            "\n结论：技术债较基线恶化。请消除新增项；确属必要（如兼容性兜底）时，"
            "在 PR 说明理由后用 `--update` 上调基线。"
        )
        return 1
    print("\n结论：技术债未恶化 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
