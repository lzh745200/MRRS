"""打 tag 之前确认「这个 commit 的 PR Checks 真的绿了」。

## 为什么需要

`scripts/check_release_gate.py` 是在 **tag 构建内部**轮询等待，属于"兜底"；
本脚本是**发布动作之前**的一次主动确认，用来挡住一类真实的误判：
「代码推上去了 → 以为验证过了 → 直接打 tag」。

2026-10-25 实测：main 上连续 5 次 PR Checks **全部 cancelled**（`concurrency.cancel-in-progress`
遇到快速连续推送会中断前一次运行），那段时间 main 实际**没有任何一次完整验证**。
`pr-checks.yml` 已改为 main 不取消（只对 PR 取消），但"排队中"仍不等于"绿"，
所以发布前必须有这一步显式检查。

## 用法

    # 一次性检查（默认不等待）：当前 HEAD 是否已有 success 运行
    python scripts/check_main_ci.py

    # 指定 commit / 仓库
    python scripts/check_main_ci.py --sha 1c41ef5 --repo lzh745200/MRRS

    # 等它绿（最多 40 分钟，每 60 秒查一次）
    python scripts/check_main_ci.py --wait-minutes 40

退出码：0 = 该 commit 的 PR Checks 已 success；1 = 无完成运行 / 在跑 / 失败 / 被取消。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

API_BASE = "https://api.github.com/repos/{repo}/actions/workflows/pr-checks.yml/runs"

# 中文 Windows 控制台默认 gbk，脚本里出现 ✓/emoji 会 UnicodeEncodeError（门禁假红），
# 与仓库其它脚本口径一致：显式兜底成 replace。
try:  # pragma: no cover - 环境相关
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

FAIL_STATES = {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}


def _get(url: str, token: str) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "mrrs-main-ci-check"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - 固定 GitHub API
        return json.load(resp)


def _fetch_runs(api_base: str, token: str, sha: str) -> list[dict]:
    data = _get(f"{api_base}?head_sha={sha}&per_page=20", token)
    return data.get("workflow_runs") or []


def _judge(runs: list[dict]) -> tuple[str, dict | None]:
    """返回 (verdict, run)；verdict ∈ completed_ok / completed_fail / running / none。"""
    if not runs:
        return "none", None
    completed = [r for r in runs if r.get("status") == "completed"]
    if completed:
        # 取最早完成的那个：同一 commit 多次运行时，只要有一次全绿即视为已验证；
        # 但如果全部失败，则报最近一次失败（通常是修复后的最后一次）。
        ok = [r for r in completed if r.get("conclusion") == "success"]
        if ok:
            return "completed_ok", ok[0]
        return "completed_fail", completed[-1]
    return "running", runs[0]


def _full_sha(sha: str) -> str:
    """把短 SHA 补全成 40 位。

    踩坑记录：GitHub 的 `head_sha` 过滤**只认完整 40 位**，传 7 位短号会返回空数组
    —— 看起来像"这个 commit 没有运行记录"，实际是参数没补全（本地实测：
    `?head_sha=1c41ef5` → total_count 0；`?head_sha=1c41ef5e8f49...` → total_count 1）。
    """
    sha = sha.strip()
    if len(sha) >= 40:
        return sha
    try:
        out = subprocess.run(
            ["git", "rev-parse", sha],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        full = out.stdout.strip()
        return full if len(full) >= 40 else sha
    except (OSError, subprocess.CalledProcessError):
        return sha


def _resolve_sha(explicit: str) -> str:
    if explicit:
        return _full_sha(explicit)
    env_sha = os.environ.get("GITHUB_SHA", "").strip()
    if env_sha:
        return _full_sha(env_sha)
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="发布前检查：目标 commit 的 PR Checks 是否已 success")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "lzh745200/MRRS"))
    parser.add_argument("--sha", default="", help="目标 commit（默认取 GITHUB_SHA 或 git HEAD）")
    parser.add_argument("--wait-minutes", type=int, default=0, help="0 = 只查一次不等待")
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = parser.parse_args(argv)

    sha = _resolve_sha(args.sha)
    if not sha:
        print("[main-ci] 无法确定目标 commit；用 --sha 指定", file=sys.stderr)
        return 1

    token = os.environ.get("GH_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "")
    api_base = API_BASE.format(repo=args.repo)
    deadline = time.time() + max(args.wait_minutes, 0) * 60
    short = sha[:7]

    while True:
        try:
            runs = _fetch_runs(api_base, token, sha)
        except urllib.error.HTTPError as exc:
            print(f"[main-ci] GitHub API 失败: HTTP {exc.code}（未鉴权时限流 60 次/小时）", file=sys.stderr)
            return 1
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"[main-ci] 网络/解析失败: {exc}", file=sys.stderr)
            return 1

        verdict, run = _judge(runs)

        if verdict == "completed_ok":
            url = (run or {}).get("html_url", "")
            if args.json:
                print(json.dumps({"sha": sha, "verdict": verdict, "url": url}, ensure_ascii=False))
            else:
                print(f"[main-ci] PASS：{short} 的 PR Checks 已 success")
                if url:
                    print(f"          {url}")
            return 0

        if verdict == "completed_fail":
            url = (run or {}).get("html_url", "")
            conclusion = (run or {}).get("conclusion", "unknown")
            print(f"[main-ci] FAIL：{short} 的 PR Checks 结论为 {conclusion}", file=sys.stderr)
            if url:
                print(f"          {url}", file=sys.stderr)
            if conclusion == "cancelled":
                print(
                    "          被取消通常是并发组被后续推送打断；重跑该 commit 或等新的 push 跑完",
                    file=sys.stderr,
                )
            return 1

        if verdict == "running":
            url = (run or {}).get("html_url", "")
            print(f"[main-ci] {short} 的运行仍在进行中：{url}")
        else:
            print(f"[main-ci] {short} 尚无 PR Checks 运行记录（可能刚推送，尚未创建）")

        if time.time() >= deadline:
            print("[main-ci] 未在等待期限内拿到 success；发布前请先等 CI 绿", file=sys.stderr)
            return 1
        time.sleep(max(args.poll_seconds, 5))


if __name__ == "__main__":
    sys.exit(main())
