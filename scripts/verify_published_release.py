# -*- coding: utf-8 -*-
r"""发布后资产完整性校验 —— 确认 GitHub Release 上的安装包「齐全、非空、与清单一致」。

## 为什么需要

构建期已有 `scripts/verify_release_assets.py` 校验「本地产物 vs latest.yml/SHA256SUMS」，
但它跑在**上传之前**。上传阶段仍可能出问题：

- v1.18.15 实测：electron-builder 与 softprops 的 publish 竞态让 `latest.yml` /
  `.exe.blockmap` 被 skipped，Release 只剩 6 个资产 —— 构建是绿的，发布是残的；
- softprops 单文件超时/失败会留下「部分资产」，同样不会让构建红。

本脚本在**发布之后**从 GitHub API 侧核对，是唯一能证明「用户真的能下到完整包」的检查。

## 校验项

1. Release 存在且非 draft / 非 prerelease；
2. 期望资产集合齐全（按 tag 版本推导，见 `expected_assets()`）；
3. 每个资产 size > 0（防 0 字节半成品）；
4. `latest.yml` 的 version / path / size 与真实资产一致；
5. 三份 `SHA256SUMS-*.txt` 里列出的每个文件名与 sha256，都与 GitHub 记录的
   asset digest 一致 —— **不需要下载 380MB 安装包**，GitHub 的 digest 就是存储层
   字节的 sha256，等价于下载后自算。

## 用法

    python scripts/verify_published_release.py --tag v1.18.53
    python scripts/verify_published_release.py --tag v1.18.53 --wait 1800
    python scripts/verify_published_release.py --tag v1.18.53 --json

`--wait N`：最多等 N 秒，直到期望资产全部出现（Release 由多个作业分别上传，
`release: published` 事件触发时其它作业可能仍在传）。

退出码：0 全部通过；1 有问题；2 参数/环境错误。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Windows 控制台中文兜底
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run_gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """调用 gh CLI（CI 里由 GH_TOKEN 授权）。"""
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} 失败: {proc.stderr.strip()[:500]}")
    return proc


def repo_slug() -> str:
    """OWNER/REPO，优先环境变量（CI），否则问 gh。"""
    env = os.environ.get("GITHUB_REPOSITORY")
    if env:
        return env
    proc = run_gh(["repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
    return proc.stdout.strip()


def expected_assets(version: str) -> list[str]:
    """按版本推导「一次完整发布」应有的资产清单。

    与本仓两条构建流水线的实际产物一致（见 .github/workflows/build-*.yml）：
    Windows NSIS 包 + blockmap + latest.yml + 校验和，ARM64 两个 DEB + 各自校验和。
    """
    return [
        f"MRRS-Setup-{version}-x64.exe",
        f"MRRS-Setup-{version}-x64.exe.blockmap",
        "latest.yml",
        "SHA256SUMS-windows-x64.txt",
        f"MRRS-Setup-{version}-arm64.deb",
        f"assistance-management-system_{version}_arm64.deb",
        "SHA256SUMS-electron-deb-arm64.txt",
        "SHA256SUMS-standalone-deb-arm64.txt",
    ]


def fetch_release(tag: str) -> dict:
    proc = run_gh(
        [
            "api",
            f"repos/{repo_slug()}/releases/tags/{tag}",
        ]
    )
    return json.loads(proc.stdout)


def download_metadata(tag: str, names: list[str], dest: Path) -> dict[str, str]:
    """下载小体积元数据文件（latest.yml / SHA256SUMS），返回 {文件名: 内容}。"""
    out: dict[str, str] = {}
    for name in names:
        pattern = name
        proc = run_gh(
            ["release", "download", tag, "-p", pattern, "-D", str(dest), "--clobber"],
            check=False,
        )
        path = dest / name
        if path.is_file():
            out[name] = path.read_text(encoding="utf-8", errors="replace")
        else:
            # gh 在资产缺失时返回非 0；此处不抛，交由调用方按「缺失」处理
            _ = proc
    return out


def parse_sums(text: str) -> dict[str, str]:
    """解析 sha256sum 格式：`<hash>  <name>`（容忍 * 前缀与多余空格）。"""
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, name = parts[0].lower(), parts[1].strip().lstrip("*").strip()
        if len(digest) == 64:
            result[name] = digest
    return result


def check_once(tag: str, version: str) -> tuple[list[str], dict]:
    """跑一次校验，返回 (问题列表, 报告)。

    报告里的 `missing` 是「期望但尚未出现」的资产名单。调用方用它判断是否值得重试——
    **不能**靠问题文案反推：资产正在上传时，API 的资产清单与下载到的清单文件之间
    存在竞态（清单先到、它引用的包后到），会同时出现「缺少资产」与
    「清单引用了不存在的资产」两种文案，见 `_should_retry`。
    """
    problems: list[str] = []
    report: dict = {"tag": tag, "version": version, "assets": [], "checks": [], "missing": []}

    release = fetch_release(tag)
    if release.get("draft"):
        problems.append("Release 仍是 draft（用户看不到、也下不到）")
    if release.get("prerelease"):
        problems.append("Release 被标记为 prerelease")

    assets = {a["name"]: a for a in release.get("assets", [])}
    report["assets"] = sorted(assets)

    expected = expected_assets(version)
    missing = [n for n in expected if n not in assets]
    report["missing"] = missing
    if missing:
        problems.append("缺少资产: " + ", ".join(missing))

    for name, asset in sorted(assets.items()):
        size = int(asset.get("size") or 0)
        if size <= 0:
            problems.append(f"资产为空（0 字节）: {name}")

    # latest.yml 与实际 exe 的 size/path 一致性
    meta = download_metadata(tag, ["latest.yml"], Path(tempfile.mkdtemp(prefix="relverify-")))
    yml = meta.get("latest.yml")
    exe_name = f"MRRS-Setup-{version}-x64.exe"
    if yml:
        try:
            # latest.yml 是简单 YAML；只取需要的三行，避免引入 PyYAML 依赖差异
            y_ver = y_path = None
            y_size = None
            for line in yml.splitlines():
                s = line.strip()
                if s.startswith("version:"):
                    y_ver = s.split(":", 1)[1].strip().strip("'\"")
                elif s.startswith("path:"):
                    y_path = s.split(":", 1)[1].strip().strip("'\"")
                elif s.startswith("size:"):
                    y_size = int(s.split(":", 1)[1].strip())
            if y_ver != version:
                problems.append(f"latest.yml version={y_ver}，与 tag 版本 {version} 不一致")
            if y_path != exe_name:
                problems.append(f"latest.yml path={y_path}，期望 {exe_name}")
            elif exe_name in assets:
                real = int(assets[exe_name].get("size") or 0)
                if y_size is not None and y_size != real:
                    problems.append(f"latest.yml size={y_size}，实际资产 size={real}")
        except Exception as exc:  # noqa: BLE001 - 解析失败要显式报出而不是跳过
            problems.append(f"latest.yml 解析失败: {exc}")
    elif "latest.yml" not in missing:
        problems.append("latest.yml 无法读取")

    # SHA256SUMS ↔ GitHub asset digest
    sums_names = [n for n in expected if n.startswith("SHA256SUMS-")]
    meta.update(download_metadata(tag, sums_names, Path(tempfile.mkdtemp(prefix="relsums-"))))
    for sums_name in sums_names:
        text = meta.get(sums_name)
        if not text:
            if sums_name not in missing:
                problems.append(f"{sums_name} 无法读取")
            continue
        entries = parse_sums(text)
        if not entries:
            problems.append(f"{sums_name} 内容为空或格式无法解析")
            continue
        for fname, digest in entries.items():
            asset = assets.get(fname)
            if asset is None:
                # 该包还没上传完：已在「缺少资产」里报过，这里不重复报，
                # 否则会因文案不同被判成「不可自愈」而提前结束等待（v1.18.55 实测）。
                if fname not in missing:
                    problems.append(f"{sums_name} 引用了不存在的资产: {fname}")
                continue
            api_digest = str(asset.get("digest") or "")
            if not api_digest:
                # 老版本 GitHub API 无 digest 字段：退化为只校验存在性
                continue
            if api_digest.lower() != f"sha256:{digest}":
                problems.append(
                    f"{fname} 校验和不一致：清单 {digest}，GitHub 记录 {api_digest}"
                )
            else:
                report["checks"].append(f"{fname} sha256 与清单一致")

    return problems, report


def _should_retry(report: dict, deadline: float, now: float) -> bool:
    """是否值得再等一轮。

    判据是「期望资产还没齐」（report["missing"] 非空），**不是**问题文案里有没有
    「缺少资产」。原因：资产分批上传时存在竞态——某个 `SHA256SUMS-*.txt` 先到、
    它引用的包后到，于是同一轮里既报「缺少资产」又报「清单引用了不存在的资产」；
    按文案白名单判断会把后者当成「等也不会自愈」而提前退出（v1.18.55 实测：
    1800s 预算只用了 973s 就判失败，随后 24s 后另一个触发重跑即通过）。
    """
    return bool(report.get("missing")) and now < deadline


def main() -> int:
    ap = argparse.ArgumentParser(description="校验已发布 Release 的资产完整性")
    ap.add_argument("--tag", required=True, help="发布标签，如 v1.18.53")
    ap.add_argument("--wait", type=int, default=0, help="最多等待多少秒直到资产齐全")
    ap.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = ap.parse_args()

    tag = args.tag.strip()
    version = tag[1:] if tag.startswith("v") else tag

    deadline = time.time() + max(0, args.wait)
    attempt = 0
    while True:
        attempt += 1
        try:
            problems, report = check_once(tag, version)
        except Exception as exc:  # noqa: BLE001 - 取不到 Release 也要给出可读结论
            print(f"[ERROR] 读取 Release {tag} 失败: {exc}", file=sys.stderr)
            return 2

        if not problems:
            break
        # 只在「期望资产还没齐」时等待；draft / 哈希不符 / 正文问题等不会自愈。
        if args.wait and _should_retry(report, deadline, time.time()):
            print(f"[wait] 第 {attempt} 次：资产未齐全，30 秒后重试（剩余 {int(deadline - time.time())}s）")
            time.sleep(min(30, max(1, int(deadline - time.time()))))
            continue
        break

    if args.json:
        report["problems"] = problems
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"发布校验: {tag}（版本 {version}）")
        print(f"资产数: {len(report['assets'])}")
        for name in report["assets"]:
            print(f"  - {name}")
        if problems:
            print("\n[FAIL] 发现以下问题：")
            for p in problems:
                print(f"  - {p}")
        else:
            print("\n[OK] 资产齐全、非空，latest.yml 与 SHA256SUMS 均与 GitHub 记录一致")

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
