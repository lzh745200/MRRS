"""发布前置门禁：校验「tag 指向的提交」自身的 PR Checks 全量结论。

背景（v1.14.2 修复 v1.14.1 构建被误拦）：
v1.13.1 引入的发布门禁只检查「main 最近一次 completed 的 PR Checks」。tag 推送瞬间，
该提交的 PR Checks 往往还在 in_progress，而"最近 completed"可能仍是更早一次失败
（v1.14.1 即因此被 smoke-test 门禁拒绝：tag commit 的 PR Checks 正常，但最近
completed 是上一提交的 e2e/upgrade-rehearsal 失败）。

本脚本逻辑：
1. 查询 tag commit（GITHUB_SHA）的 PR Checks：
   - completed success → 放行；
   - completed failure → 阻断（明确原因）；
   - completed cancelled（并发取消）→ 回退第 2 步；
   - in_progress / queued → 轮询等待（默认 75 分钟上限）直到 completed。
2. 回退：main 最近一次 completed PR Checks success → 放行，否则阻断。
3. 若 tag commit 完全无 PR Checks（例如未推送 main 的孤立 tag）→ 直接回退第 2 步。

用法（CI）：GH_TOKEN=... GITHUB_REPOSITORY=owner/repo GITHUB_SHA=<sha> \\
          python scripts/check_release_gate.py [--timeout-minutes 75] [--poll-seconds 60]

本地无 token 时走匿名 GitHub API（公开仓库可读，便于本地验证脚本逻辑）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

API_BASE = "https://api.github.com/repos/{repo}/actions/workflows/pr-checks.yml/runs"


def _get(url: str, token: str) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "mrrs-release-gate"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - 固定 GitHub API
        return json.load(resp)


def _latest_completed_on_main(api_base: str, token: str) -> dict | None:
    data = _get(f"{api_base}?branch=main&per_page=5&status=completed", token)
    runs = data.get("workflow_runs") or []
    return runs[0] if runs else None


def _tag_commit_runs(api_base: str, token: str, sha: str) -> list[dict]:
    data = _get(f"{api_base}?head_sha={sha}&per_page=10", token)
    return data.get("workflow_runs") or []


def main() -> int:
    parser = argparse.ArgumentParser(description="发布前置门禁：tag commit 的 PR Checks 全量结论")
    parser.add_argument("--timeout-minutes", type=int, default=75)
    parser.add_argument("--poll-seconds", type=int, default=60)
    args = parser.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "lzh745200/MRRS")
    sha = os.environ.get("GITHUB_SHA", "")
    token = os.environ.get("GH_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "")
    api_base = API_BASE.format(repo=repo)

    if not sha:
        print("::error::GITHUB_SHA 未设置，无法校验发布门禁")
        return 1
    print(f"发布前置门禁：tag commit {sha[:7]}（repo={repo}）")

    deadline = time.time() + args.timeout_minutes * 60
    last_note = ""
    while True:
        try:
            runs = _tag_commit_runs(api_base, token, sha)
        except urllib.error.HTTPError as exc:  # 403/404 等：回退保守判定
            print(f"::warning::查询 tag commit PR Checks 失败（HTTP {exc.code}），回退 main 结果")
            runs = []

        if runs:
            completed = [r for r in runs if r.get("status") == "completed"]
            if completed:
                latest = completed[0]
                conclusion = latest.get("conclusion")
                print(
                    f"tag commit PR Checks: {latest.get('head_sha', '')[:7]} "
                    f"conclusion={conclusion} url={latest.get('html_url')}"
                )
                if conclusion == "success":
                    print("发布前置门禁: PASS（tag commit 全量门禁通过）")
                    return 0
                if conclusion == "cancelled":
                    print("::warning::tag commit 的 PR Checks 被并发取消，回退 main 最近完成结果")
                    fallback = _latest_completed_on_main(api_base, token)
                    if fallback and fallback.get("conclusion") == "success":
                        print("发布前置门禁: PASS（回退 main 最近完成 PR Checks 通过）")
                        return 0
                    print("::error::main 最近完成 PR Checks 未通过，禁止发布构建")
                    return 1
                print("::error::tag commit 的 PR Checks 未通过，禁止发布构建（见上方 url）")
                return 1
            note = "tag commit PR Checks 运行中，等待完成…"
        else:
            note = "tag commit 暂无 PR Checks（等待触发/排队）…"

        if note != last_note:
            print(note)
            last_note = note
        if time.time() > deadline:
            print(f"::error::等待 tag commit PR Checks 超时（{args.timeout_minutes} 分钟），禁止发布构建")
            return 1
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    sys.exit(main())
