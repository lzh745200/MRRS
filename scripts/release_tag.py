#!/usr/bin/env python3
"""发布唯一入口：校验 → 等 PR Checks 全绿 → 打 tag → 推送 tag。

## 为什么需要

2026-10-25 的真实事故链：
1. 代码 push 到 main 后**立刻**打 tag 并推送；
2. tag 触发的构建工作流有 `check_release_gate.py` 前置门禁，它要求该 commit 的
   PR Checks 结论为 success（或 main 最近一次 completed success）；
3. 当时 PR Checks 还在 `in_progress` / 被并发推送取消 / 甚至失败，
   于是 Windows 与 ARM64 两个构建**必然失败**；
4. 表面现象是"Release 没出来"，根因是"tag 打早了"。

`scripts/check_main_ci.py` 已经能查单个 commit 的 PR Checks 结论，但**靠人记得去跑**
就是不可靠。本脚本把它变成发布动作本身：没有绿就不打 tag。

## 用法

    # 只看计划（默认 dry-run，不改仓库）
    python scripts/release_tag.py

    # 真正执行：等当前 HEAD 的 PR Checks 变绿（最多 40 分钟）后打 tag 并推送
    python scripts/release_tag.py --apply

    # 指定 tag / 等待时长
    python scripts/release_tag.py --apply --tag v1.18.7 --wait-minutes 60

退出码：0 = 已完成（或 dry-run 计划可行）；1 = 前置条件不满足；2 = 参数/环境错误。

## 前置条件（任一不满足即拒绝）

- 当前分支是 `main`；
- 工作区干净（`git status --porcelain` 为空）——避免把未提交改动当已发布；
- `package.json` 的 version 与 tag（去掉 `v`）一致；
- `CHANGELOG.md` 已记录该版本（复用 `scripts/check_changelog.py`）；
- HEAD 的 PR Checks 结论为 success（`scripts/check_main_ci.py --wait-minutes N`）。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def _run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=check)


def read_version() -> str:
    """读取根 package.json 的 version（版本唯一权威来源）。"""
    data = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    return str(data["version"])


def current_branch() -> str:
    return _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()


def head_sha() -> str:
    return _run(["git", "rev-parse", "HEAD"]).stdout.strip()


def is_worktree_clean() -> bool:
    return _run(["git", "status", "--porcelain"]).stdout.strip() == ""


def _is_ancestor(sha: str, head: str) -> bool:
    """sha 是否为 head 的祖先（防止把未合入 main 的提交打上发布 tag）。"""
    return _run(["git", "merge-base", "--is-ancestor", sha, head]).returncode == 0


def tag_exists_locally(tag: str) -> bool:
    return _run(["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"]).returncode == 0


def validate_tag(tag: str) -> tuple[bool, str]:
    """tag 形式 + 与 package.json 版本一致。"""
    if not TAG_RE.match(tag):
        return False, f"tag 必须形如 vX.Y.Z，当前为 {tag!r}"
    if tag.lstrip("v") != read_version():
        return False, f"tag {tag} 与 package.json version {read_version()} 不一致"
    return True, ""


def changelog_recorded() -> tuple[bool, str]:
    """复用 changelog 门禁脚本，避免两套口径。"""
    proc = _run([sys.executable, str(ROOT / "scripts" / "check_changelog.py")])
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()[-400:]


def ci_green(sha: str, wait_minutes: int, repo: str) -> tuple[bool, str]:
    """调用 check_main_ci.py 校验/等待该 commit 的 PR Checks 结论。"""
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "check_main_ci.py"),
        "--sha",
        sha,
        "--wait-minutes",
        str(wait_minutes),
        "--repo",
        repo,
    ]
    proc = _run(cmd)
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()[-400:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="发布唯一入口：绿了才打 tag")
    parser.add_argument("--tag", default=None, help="默认 v<package.json version>")
    parser.add_argument("--wait-minutes", type=int, default=40, help="等 PR Checks 的上限（分钟）")
    parser.add_argument(
        "--sha",
        default=None,
        help="要发布的 commit（默认 HEAD）；必须是 HEAD 的祖先，用于 main 已被他人推进时仍发布自己验证过的提交",
    )
    parser.add_argument(
        "--repo", default="lzh745200/MRRS", help="owner/repo（默认本仓库）"
    )
    parser.add_argument("--apply", action="store_true", help="真正打 tag 并推送（默认 dry-run）")
    args = parser.parse_args(argv)

    tag = args.tag or f"v{read_version()}"
    problems: list[str] = []

    ok, msg = validate_tag(tag)
    if not ok:
        problems.append(msg)

    branch = current_branch()
    if branch != "main":
        problems.append(f"当前分支是 {branch}，发布必须从 main 切")

    if not is_worktree_clean():
        problems.append("工作区不干净：先提交或 stash，避免把未提交改动当已发布")

    if tag_exists_locally(tag):
        problems.append(f"本地已存在 tag {tag}（不允许重打已发布版本）")

    ok, msg = changelog_recorded()
    if not ok:
        problems.append(f"CHANGELOG 门禁未通过：{msg}")

    sha = args.sha or head_sha()
    if args.sha and not _is_ancestor(args.sha, head_sha()):
        problems.append(f"--sha {args.sha[:8]} 不是当前 HEAD 的祖先，拒绝发布未合入 main 的提交")
    print(f"[release] tag={tag} commit={sha[:8]} branch={branch} dry-run={not args.apply}")
    if problems:
        for p in problems:
            print(f"  ✗ {p}")
        return 1

    ok_ci, detail = ci_green(sha, args.wait_minutes, args.repo)
    print(f"[release] PR Checks on {sha[:8]}: {'GREEN' if ok_ci else 'NOT GREEN'}")
    if not ok_ci:
        print(f"  {detail}")
        print(
            "  规则：main 的 PR Checks 未 success 之前禁止打 tag —— "
            "否则 tag 构建会被 check_release_gate.py 拒绝（历史上 v1.18.4/v1.18.5 即因此失败）。"
        )
        return 1

    if not args.apply:
        print(f"[release] dry-run 通过。执行：python scripts/release_tag.py --apply --tag {tag}")
        return 0

    for cmd in (
        ["git", "tag", tag, sha],
        ["git", "push", "origin", tag],
    ):
        proc = _run(cmd)
        if proc.returncode != 0:
            print(f"[release] {' '.join(cmd)} 失败：{proc.stdout}{proc.stderr}")
            return 1
    print(f"[release] 已推送 {tag}；构建与 Release 由 tag 触发的两个工作流产出。")
    print(f"[release] 跟踪：gh run list --branch {tag} --limit 5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
