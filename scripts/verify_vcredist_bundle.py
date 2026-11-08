"""Build-time integrity check for bundled VC++ redistributables.

The installer no longer runs a PowerShell SHA256 check on the target machine
(that produced false positives on Chinese paths / locked-down PowerShell).
Supply-chain integrity must therefore be enforced before packaging.

Usage:
    python scripts/verify_vcredist_bundle.py
    python scripts/verify_vcredist_bundle.py --dir dist/electron/win-unpacked/resources/vcredist
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "build-scripts" / "electron-builder-nsis-hook.nsh"
DEFAULT_DIRS = [
    ROOT / "resources" / "vcredist",
    ROOT / "dist" / "electron" / "win-unpacked" / "resources" / "vcredist",
]


def pinned_hashes() -> dict[str, str]:
    text = HOOK.read_text(encoding="utf-8")
    result: dict[str, str] = {}
    for arch in ("X64", "X86"):
        match = re.search(
            rf'!define\s+VCREDIST_{arch}_SHA256\s+"([0-9A-Fa-f]{{64}})"', text
        )
        if not match:
            raise SystemExit(f"缺少 VCREDIST_{arch}_SHA256 钉扎常量")
        result[arch.lower()] = match.group(1).upper()
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def check(dir_: Path, expected: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for arch, pinned in expected.items():
        path = dir_ / f"vc_redist.{arch}.exe"
        if not path.is_file():
            errors.append(f"{path}: 文件缺失")
            continue
        actual = sha256(path)
        if actual != pinned:
            errors.append(f"{path}: SHA256 不匹配（实际 {actual}，钉扎 {pinned}）")
        else:
            print(f"[OK] {path} ({path.stat().st_size} B, SHA256 {actual[:12]}…)")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", action="append", help="额外校验目录（可重复）")
    parser.add_argument("--allow-missing", action="store_true", help="目录不存在时跳过")
    args = parser.parse_args()

    expected = pinned_hashes()
    dirs = [Path(p).resolve() for p in (args.dir or [])] or DEFAULT_DIRS
    errors: list[str] = []
    checked = 0
    for dir_ in dirs:
        if not dir_.is_dir():
            if args.allow_missing:
                continue
            # Default staging dir may not exist before packaging; only fail if
            # *all* candidate dirs are missing.
            continue
        checked += 1
        errors.extend(check(dir_, expected))

    if checked == 0:
        errors.append("未找到任何 vcredist 目录（resources/vcredist 或打包目录）")
    if errors:
        print("[FAIL] VC++ 供应链校验失败：", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"[OK] VC++ Redistributable 校验通过（{checked} 个目录）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
