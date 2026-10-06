#!/usr/bin/env python3
"""分支覆盖棘轮门禁（2026-10-06 新增，配套测试质量审计 P0-1）。

背景：backend/.coveragerc 的门禁只度量语句/行（未开 branch=true），
「语句 100%」对条件组合（`a and b` 短路、except 兜底、嵌套 if 部分真值）零约束。
本脚本用 `--cov-branch` 的 coverage JSON 把**分支覆盖**钉在基线上：只紧不松，
待分模块清零后再把 .coveragerc 升级为 branch=true 全局门禁。

用法（CI backend-test 作业）：
    python -m pytest tests/ -q -n auto --cov=app --cov-branch \
        --cov-fail-under=0 --cov-report=json:coverage-branch.json
    python scripts/check_branch_coverage.py \
        --json coverage-branch.json \
        --baseline backend/scripts/gate_baselines/branch_coverage_baseline.json

基线更新（有意提升后）：
    python scripts/check_branch_coverage.py --json coverage-branch.json \
        --baseline <path> --update-baseline
"""
import argparse
import json
import sys
from datetime import date


def load_branch_pct(json_path: str) -> tuple:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    totals = data["totals"]
    num = totals.get("num_branches", 0)
    covered = totals.get("covered_branches", 0)
    pct = round(covered / num * 100, 2) if num else 100.0
    return pct, num, covered, data


def main() -> int:
    ap = argparse.ArgumentParser(description="分支覆盖棘轮门禁")
    ap.add_argument("--json", required=True, help="coverage json 路径")
    ap.add_argument("--baseline", required=True, help="基线 JSON 路径")
    ap.add_argument("--update-baseline", action="store_true",
                    help="用当前值覆盖基线（仅用于有意提升后）")
    ap.add_argument("--top", type=int, default=10, help="失败时列出缺口最大的文件数")
    args = ap.parse_args()

    pct, num, covered, data = load_branch_pct(args.json)

    if args.update_baseline:
        payload = {
            "branches": pct,
            "covered_branches": covered,
            "num_branches": num,
            "generated": date.today().isoformat(),
            "note": "棘轮基线：只紧不松；提升方式=补分支用例后 --update-baseline",
        }
        with open(args.baseline, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"[branch-ratchet] 基线已更新为 {pct:.2f}%（{covered}/{num}）")
        return 0

    try:
        with open(args.baseline, encoding="utf-8") as f:
            base = json.load(f)
        base_pct = float(base["branches"])
    except (OSError, KeyError, ValueError) as e:
        print(f"[branch-ratchet] 基线文件不可读（{e}）——请先运行 --update-baseline 生成", file=sys.stderr)
        return 2

    if pct + 1e-9 < base_pct:
        print(f"[branch-ratchet] FAIL：分支覆盖 {pct:.2f}% < 基线 {base_pct:.2f}%")
        files = []
        for path, info in data.get("files", {}).items():
            miss = info.get("summary", {}).get("missing_branches", 0)
            if miss:
                files.append((miss, path))
        files.sort(reverse=True)
        if files:
            print(f"[branch-ratchet] 缺口最大的 {args.top} 个文件（missing branches）：")
            for miss, path in files[: args.top]:
                print(f"  {miss:5d}  {path}")
        print("[branch-ratchet] 棘轮只紧不松：请补分支用例，或（确有提升时）--update-baseline")
        return 1

    print(f"[branch-ratchet] OK：分支覆盖 {pct:.2f}% ≥ 基线 {base_pct:.2f}%"
          f"（{covered}/{num}，棘轮只紧不松）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
