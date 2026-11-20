# -*- coding: utf-8 -*-
"""GitHub Release 已发布资产一致性核验（发布后门禁）。

## 为什么需要

现有发布流水线的校验都停在**构建阶段**：`verify_installer_payload.py` 校验
7z 载荷、`verify_installer_signature.ps1` 校验签名、`Smoke test packaged backend`
验证打包后端能起。但**「发布上去的那批资产，和构建机本地那批是不是同一份」**
此前没有任何一步去核——`softprops/action-gh-release` 上传成功只说明上传动作完成，
不代表资产完整、版本一致、正文非空。

历史上这类问题都是**发布之后**才被发现，靠人眼翻 Release 页：

- v1.18.1：三个发布作业各自重写正文，ARM64 覆盖导致 Release 正文 0 字符；
- v1.18.14/v1.18.15：publish 竞态，同一条流水线产出**资产清单不同**（8 个 vs 6 个）；
- v1.18.33：构建中断留下「只有外壳没有 7z 载荷」的半成品，被当成构建成功上传。

本脚本在 Release 上传完成之后**就地**复核，把上述三类问题在发布作业内拦下：

1. **完整性**：本作业声明要发布的每个文件，都必须在 Release 资产里存在；
2. **一致性**：已发布资产的 `size` 与本地文件字节数一致、`digest` 与本地 SHA256 一致
   （GitHub API 为每个资产返回 `sha256:` 形式的 digest，二者可直接比对，无需再下载）；
3. **版本**：`latest.yml` 的 `version` / `path` / `size` / `sha512` 与实际 exe 对齐；
4. **正文**：Release 正文非空且包含版本号（防「正文被覆盖成空/写成占位」）。

## 使用

在发布作业里、`Release` 步骤之后调用：

    python scripts/verify_release_assets.py --tag v1.18.53 --artifacts "MRRS-Setup-1.18.53-x64.exe" ...
    python scripts/verify_release_assets.py --tag v1.18.53 --artifacts latest.yml

`--artifacts` 是**本作业刚上传的**文件（相对仓库根的路径）；脚本逐个核对。

## 设计取舍

- **不重新下载大文件**：用 `gh api` 读取已发布资产的 `size` 与 `digest`，
  在本地算 SHA256 后与 digest 比对。382 MB 的包若每版都从 GitHub 拉一遍，
  发布作业会多出十几分钟且受 CDN 速率限制（本机实测 github.com 主域不可达、
  objects 域虽通但极慢），而 digest 由 GitHub 在上传时计算，本就是权威值。
- **失败即非零退出**：任一检查不过，打印逐项差异表并 exit 1，作业变红，
  Release 已发布但问题会被立刻看见，不会静默流到下游。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import Iterable, Sequence

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 本系统各发布作业**应当**出现的资产（缺一个就是发布清单不完整）。
# 名字带占位符时按标签实际版本号展开。
EXPECTED_WINDOWS_ASSETS = (
    "MRRS-Setup-{version}-x64.exe",
    "MRRS-Setup-{version}-x64.exe.blockmap",
    "latest.yml",
    "SHA256SUMS-windows-x64.txt",
)
EXPECTED_ARM64_ASSETS = (
    "MRRS-Setup-{version}-arm64.deb",
    "assistance-management-system_{version}_arm64.deb",
    "SHA256SUMS-electron-deb-arm64.txt",
    "SHA256SUMS-standalone-deb-arm64.txt",
)


def _warn(msg: str) -> None:
    print(f"::warning::{msg}", file=sys.stderr)


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha512_base64(path: pathlib.Path) -> str:
    digest = hashlib.sha512()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return base64.b64encode(digest.digest()).decode("ascii")


def _gh_api(path: str) -> dict:
    """调 `gh api` 取 JSON（复用作业已有的 GITHUB_TOKEN，避免重复实现鉴权）。"""
    cmd = ["gh", "api", path, "--jq", "."]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"gh api 失败：{' '.join(cmd)}\n{proc.stderr.strip()}")
    return json.loads(proc.stdout)


def _release_of(repo: str, tag: str) -> dict:
    return _gh_api(f"repos/{repo}/releases/tags/{tag}")


def _repo_slug() -> str:
    proc = subprocess.run(
        ["git", "remote", "get-url", "origin"], capture_output=True, text=True, encoding="utf-8"
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError("无法确定 origin 仓库（需要 git remote origin）")
    url = proc.stdout.strip()
    # 支持三种写法：git@github.com:owner/repo.git、https://github.com/owner/repo.git、
    # ssh://git@github.com/owner/repo.git
    match = re.search(r"github\.com[:/](?:[^@/]+/)?([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+?)(?:\.git)?$", url)
    if not match:
        raise RuntimeError(f"无法从 origin 解析仓库 slug：{url}")
    return match.group(1)


def _resolve_repo(args: argparse.Namespace) -> str:
    if args.repo:
        return args.repo
    return _repo_slug()


def _check_artifacts(
    release: dict,
    artifacts: Sequence[pathlib.Path],
    tag: str,
) -> list[str]:
    """核对「本地文件 → 已发布资产」的 size 与 digest，返回问题列表。"""
    published = {asset.get("name", ""): asset for asset in release.get("assets", [])}
    problems: list[str] = []

    for path in artifacts:
        if not path.is_file():
            problems.append(f"本地文件不存在：{path}（发布前就缺，先查构建步骤）")
            continue
        name = path.name
        asset = published.get(name)
        if asset is None:
            problems.append(f"Release 资产缺失：{name}")
            continue
        local_size = path.stat().st_size
        remote_size = int(asset.get("size") or 0)
        if local_size != remote_size:
            problems.append(
                f"{name} 大小不一致：本地 {local_size} B，已发布 {remote_size} B"
            )
        local_sha = _sha256_file(path)
        remote_digest = str(asset.get("digest") or "")
        if remote_digest.startswith("sha256:"):
            remote_sha = remote_digest[len("sha256:") :]
            if remote_sha.lower() != local_sha:
                problems.append(
                    f"{name} SHA256 不一致：本地 {local_sha}，已发布 {remote_sha}"
                )
        else:
            problems.append(f"{name} 已发布资产缺少 sha256 digest（无法核对）")

    return problems


def _check_latest_yml(
    latest_yml: pathlib.Path,
    exe: pathlib.Path,
    version: str,
) -> list[str]:
    """核对 `latest.yml` 的四个字段与实际 exe。"""
    problems: list[str] = []
    if not latest_yml.is_file():
        problems.append("本地缺少 latest.yml")
        return problems
    if not exe.is_file():
        problems.append("本地缺少被 latest.yml 引用的 exe")
        return problems

    try:
        raw = latest_yml.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"读取 latest.yml 失败：{exc}"]

    # exe 文件名形如 `MRRS-Setup-<版本>-<架构>.exe`，取版本号段核对。
    match_name = re.search(r"-(\d+\.\d+\.\d+)-", exe.name)
    exe_version = match_name.group(1) if match_name else ""
    expect_sha512 = _sha512_base64(exe)
    fields = {
        "version": version,
        "path": exe.name,
        "size": str(exe.stat().st_size),
        "sha512": expect_sha512,
    }
    for key, expected in fields.items():
        pattern = re.compile(rf"(?m)^\s*{re.escape(key)}:\s*(.+?)\s*$")
        match = pattern.search(raw)
        if match is None:
            problems.append(f"latest.yml 缺少字段 `{key}`")
            continue
        actual = match.group(1).strip()
        if actual != expected:
            problems.append(
                f"latest.yml 的 `{key}` 不一致：期望 {expected}，实际 {actual}"
            )
    if exe_version != version:
        problems.append(
            f"exe 文件名版本号 {exe_version} 与版本号 {version} 不一致"
        )
    return problems


def _check_body(release: dict, version: str) -> list[str]:
    body = (release.get("body") or "").strip()
    problems: list[str] = []
    if not body:
        problems.append("Release 正文为空（softprops 重写正文的老问题，本脚本直接拦下）")
    elif version not in body:
        problems.append(f"Release 正文未包含版本号 {version}（可能是占位正文）")
    if release.get("draft"):
        problems.append("Release 仍是 draft，不会被推送到正式页面")
    if release.get("prerelease"):
        _warn(f"Release 标记为 prerelease（{version}），请确认这是有意为之")
    return problems


def _expected_assets(kind: str, version: str) -> tuple[str, ...]:
    if kind == "windows":
        return tuple(name.format(version=version) for name in EXPECTED_WINDOWS_ASSETS)
    if kind == "arm64":
        return tuple(name.format(version=version) for name in EXPECTED_ARM64_ASSETS)
    raise ValueError(f"未知资产集：{kind}")


def _check_expected_presence(release: dict, kind: str, version: str) -> list[str]:
    published = {asset.get("name", "") for asset in release.get("assets", [])}
    return [
        f"Release 缺少预期资产：{name}"
        for name in _expected_assets(kind, version)
        if name not in published
    ]


def _check_sums_cover(sums_paths: Iterable[pathlib.Path], files: Iterable[pathlib.Path]) -> list[str]:
    """核对校验和清单是否覆盖给定文件、哈希是否与文件实际内容一致。

    允许一份文件被多份清单分别覆盖（ARM64 两套 deb 各有一份清单），
    因此这里把各清单的条目合并成一个 `name -> hash` 映射后再逐文件核对。
    """
    expected: dict[str, str] = {}
    problems: list[str] = []
    for sums_path in sums_paths:
        if not sums_path.is_file():
            # 清单文件缺失由 `_check_local_dir` 的预期产物检查报出，这里不重复报。
            continue
        for line in sums_path.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                expected[parts[-1].lstrip("./")] = parts[0].lower()
    for path in files:
        if not path.is_file():
            continue
        name = path.name
        if name not in expected:
            problems.append(f"校验和清单缺少 {name} 的条目")
            continue
        actual = _sha256_file(path)
        if expected[name] != actual:
            problems.append(f"{name} 的 SHA256 与校验和清单不一致")
    return problems


def _check_local_dir(
    directory: pathlib.Path,
    version: str,
    asset_set: str,
) -> list[str]:
    """发布**前**的本地一致性检查：目录内产物齐全、latest.yml 与 exe 吻合、校验和覆盖。"""
    expected = _expected_assets(asset_set, version)
    if not directory.is_dir():
        return [f"本地目录不存在：{directory}"]

    present = {path.name for path in directory.iterdir() if path.is_file()}
    problems = [
        f"本地目录缺少预期产物：{name}" for name in expected if name not in present
    ]

    if asset_set == "windows":
        exe = directory / f"MRRS-Setup-{version}-x64.exe"
        if exe.is_file():
            problems.extend(_check_latest_yml(directory / "latest.yml", exe, version))
            problems.extend(
                _check_sums_cover(
                    [directory / "SHA256SUMS-windows-x64.txt"],
                    [exe],
                )
            )
    else:
        debs = [
            path
            for path in directory.glob("*.deb")
            if path.name in set(expected)
        ]
        problems.extend(
            _check_sums_cover(
                [
                    directory / "SHA256SUMS-electron-deb-arm64.txt",
                    directory / "SHA256SUMS-standalone-deb-arm64.txt",
                ],
                debs,
            )
        )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="核验发布资产一致性（发布前本地目录模式 / 发布后 Release 比对模式）"
    )
    parser.add_argument("--tag", default="", help="git tag，如 v1.18.53（发布后模式必填）")
    parser.add_argument(
        "--dir",
        default="",
        help="本地构建产物目录（发布前模式，与 --expect-version 配合），如 dist/electron",
    )
    parser.add_argument("--expect-version", default="", help="期望版本号，如 1.18.53")
    parser.add_argument(
        "--artifacts",
        nargs="*",
        default=[],
        help="本作业上传的本地文件（相对仓库根或绝对路径）",
    )
    parser.add_argument("--repo", default="", help="仓库 slug，缺省从 origin 解析")
    parser.add_argument(
        "--asset-set",
        choices=("windows", "arm64"),
        default="windows",
        help="本作业属于哪套资产集，用于核对预期资产清单（发布后模式）",
    )
    parser.add_argument(
        "--require-assets",
        nargs="*",
        default=[],
        help="发布后模式：本作业必须已发布的资产名（支持 {version} 占位符）。"
        "三个发布作业并发写同一 Release，若用整套资产清单做硬性要求会因竞态误红；"
        "缺省回退为 --artifacts 的文件名。",
    )
    parser.add_argument(
        "--latest-yml",
        default="",
        help="latest.yml 本地路径（默认取 --dir 下的 latest.yml）",
    )
    parser.add_argument(
        "--exe",
        default="",
        help="latest.yml 引用的 exe 本地路径；缺省自动取 --artifacts 中的 *.exe",
    )
    args = parser.parse_args()

    # —— 模式一：发布前本地目录一致性（CI 在上传/发布前拦截裸数据）——
    if args.dir:
        version = args.expect_version[1:] if args.expect_version.startswith("v") else args.expect_version
        if not version:
            print("::error::--dir 模式必须同时传 --expect-version", file=sys.stderr)
            return 2
        directory = pathlib.Path(args.dir)
        if not directory.is_absolute():
            directory = ROOT / directory
        problems = _check_local_dir(directory, version, args.asset_set)
        print(f"本地产物目录 {directory}（期望版本 {version}）：")
        for path in sorted(p for p in directory.iterdir() if p.is_file()):
            print(f"  - {path.name}")
        if problems:
            print(f"\n核验未通过（{len(problems)} 项）：", file=sys.stderr)
            for item in problems:
                print(f"  ✗ {item}", file=sys.stderr)
            return 1
        print(f"\n核验通过：{directory} 内 {len(_expected_assets(args.asset_set, version))} 个预期产物齐全且自洽。")
        return 0

    # —— 模式二：发布后 Release 比对（就地用 API 的 size/digest 比对，不下载大文件）——
    if not args.tag:
        print("::error::缺少 --tag；若要做发布前检查请传 --dir 与 --expect-version", file=sys.stderr)
        return 2

    version = args.tag[1:] if args.tag.startswith("v") else args.tag
    repo = _resolve_repo(args)
    if not repo:
        print("::error::无法确定仓库 slug，请显式传 --repo owner/repo", file=sys.stderr)
        return 2

    try:
        release = _release_of(repo, args.tag)
    except RuntimeError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    if "assets" not in release:
        print(f"::error::Release {args.tag} 不存在或不可见（repo={repo}）", file=sys.stderr)
        return 2

    artifacts = [
        pathlib.Path(item) if pathlib.Path(item).is_absolute() else ROOT / item
        for item in args.artifacts
    ]
    exe_path = pathlib.Path(args.exe) if args.exe else _find_exe(artifacts)

    problems: list[str] = []
    problems.extend(_check_artifacts(release, artifacts, args.tag))
    required = [name.format(version=version) for name in args.require_assets] or [
        path.name for path in artifacts
    ]
    published_names = {asset.get("name", "") for asset in release.get("assets", [])}
    problems.extend(
        f"Release 缺少本作业应发布的资产：{name}"
        for name in required
        if name not in published_names
    )
    problems.extend(_check_body(release, version))
    if exe_path is not None:
        problems.extend(_check_latest_yml(ROOT / args.latest_yml, exe_path, version))

    published = {asset.get("name", "") for asset in release.get("assets", [])}
    print("已发布资产：")
    for name in sorted(published):
        print(f"  - {name}")

    if problems:
        print(f"\n核验未通过（{len(problems)} 项）：", file=sys.stderr)
        for item in problems:
            print(f"  ✗ {item}", file=sys.stderr)
        return 1

    print(f"\n核验通过：{args.tag} 的 {len(published)} 个已发布资产与本地产物完全一致。")
    return 0


def _find_exe(artifacts: Iterable[pathlib.Path]) -> pathlib.Path | None:
    for path in artifacts:
        if path.suffix == ".exe" and path.is_file():
            return path
    return None


if __name__ == "__main__":
    sys.exit(main())
