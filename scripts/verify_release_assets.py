#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布资产一致性校验：latest.yml / SHA256SUMS / 实际文件必须互相吻合。

用途：
  * 本地构建后：`python scripts/verify_release_assets.py --dir dist/electron`
  * Release 下载目录：`python scripts/verify_release_assets.py --dir dist/release53`
  * 只校验 Windows 资产时加 `--allow-missing`（ARM 资产未下载）。

校验项：
  1. latest.yml 的 version / path / size / sha512 与实际 exe 一致；
  2. .blockmap 存在（若 latest.yml 指向 NSIS 包）；
  3. 目录内 SHA256SUMS-*.txt 的每一条都与实际文件一致；
  4. 可选 `--expect-version` 校验文件名/元数据版本。
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - CI 已装 PyYAML，本地缺失时给出可读错误
    print("缺少 PyYAML：pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha512_b64(path: Path) -> str:
    h = hashlib.sha512()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode()


def check_sums(path: Path, allow_missing: bool) -> list[str]:
    problems: list[str] = []
    for sum_file in sorted(path.glob("SHA256SUMS-*.txt")):
        if not sum_file.is_file():
            continue
        for line in sum_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                problems.append(f"{sum_file.name}: 无法解析行: {line!r}")
                continue
            expected, name = parts[0], parts[1].lstrip("*")
            target = path / name
            if not target.exists():
                if allow_missing:
                    print(f"[warn] {sum_file.name}: 缺少 {name}（--allow-missing 跳过）")
                    continue
                problems.append(f"{sum_file.name}: 缺少被校验文件 {name}")
                continue
            actual = sha256(target)
            if actual != expected:
                problems.append(f"{sum_file.name}: {name} SHA256 不匹配 ({actual} != {expected})")
            else:
                print(f"[ok] {sum_file.name}: {name}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="dist/electron", help="构建/Release 资产目录")
    ap.add_argument("--expect-version", default="", help="期望版本号（默认读 latest.yml）")
    ap.add_argument("--allow-missing", action="store_true", help="允许未下载的资产缺失")
    args = ap.parse_args()

    root = Path(args.dir)
    latest = root / "latest.yml"
    problems: list[str] = []
    if not latest.is_file():
        problems.append(f"缺少 {latest}")
    else:
        data = yaml.safe_load(latest.read_text(encoding="utf-8")) or {}
        version = str(data.get("version", "")).strip()
        if not version:
            problems.append("latest.yml 缺少 version")
        if args.expect_version and version != args.expect_version:
            problems.append(f"latest.yml version={version}，期望 {args.expect_version}")
        files = data.get("files") or []
        if not isinstance(files, list) or not files:
            problems.append("latest.yml files 为空")
        else:
            for item in files:
                if not isinstance(item, dict):
                    problems.append(f"latest.yml files 条目非法: {item!r}")
                    continue
                name = str(item.get("url") or item.get("path") or "")
                target = root / name
                if not name:
                    problems.append("latest.yml files 条目缺少 url/path")
                    continue
                if not target.is_file():
                    problems.append(f"latest.yml 指向的文件不存在: {name}")
                    continue
                expected_size = item.get("size")
                if isinstance(expected_size, int) and target.stat().st_size != expected_size:
                    problems.append(
                        f"{name} size={target.stat().st_size}，latest.yml size={expected_size}"
                    )
                expected_sha = str(item.get("sha512") or "")
                if expected_sha:
                    actual = sha512_b64(target)
                    if actual != expected_sha:
                        problems.append(f"{name} sha512 与 latest.yml 不一致")
                blockmap = root / f"{name}.blockmap"
                if name.lower().endswith(".exe") and not blockmap.is_file():
                    problems.append(f"缺少 blockmap: {blockmap.name}")
                if not problems:
                    print(f"[ok] latest.yml -> {name}（size={target.stat().st_size}）")

    problems.extend(check_sums(root, args.allow_missing))

    if problems:
        print("\n[release-assets] ✗ 一致性问题：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"[release-assets] OK: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
