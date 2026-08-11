"""版本号同步脚本 — 从 git tag 或 version.txt 同步到所有配置文件

用法: python scripts/sync_version.py [version]
  - 不带参数：从 version.txt 读取
  - 带参数：直接使用该版本号 (如 v1.4.0 -> 1.4.0)

同步目标: 根 package.json、frontend/package.json、config.py、.env.example
版本号权威来源: 根 package.json -> version (CI 中 tag 触发时由本脚本同步)
"""

import json
import os
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_version():
    if len(sys.argv) > 1:
        v = sys.argv[1].lstrip("v")
    else:
        vf = PROJECT_ROOT / "version.txt"
        if vf.exists():
            v = vf.read_text().strip()
        else:
            print("ERROR: 无 version.txt 且未提供参数")
            sys.exit(1)
    return v


def update_config_py(version: str):
    path = PROJECT_ROOT / "backend" / "app" / "core" / "config.py"
    content = path.read_text(encoding="utf-8")
    # 匹配带或不带类型注解（str / Optional[str]）的 PROJECT_VERSION 行
    pattern = r'PROJECT_VERSION\s*:\s*(?:str\s*)?=\s*"[^"]*"'
    new_content, n = re.subn(
        pattern,
        f'PROJECT_VERSION: str = "{version}"',
        content,
    )
    if n == 0:
        print(f"  WARN: {path.relative_to(PROJECT_ROOT)} — PROJECT_VERSION line not matched (format changed?)")
    elif n > 1:
        print(f"  WARN: {path.relative_to(PROJECT_ROOT)} — matched {n} PROJECT_VERSION lines (ambiguous)")
    else:
        path.write_text(new_content, encoding="utf-8")
        print(f"  UPD: {path.relative_to(PROJECT_ROOT)}")


def update_package_json(version: str):
    # 同步根 package.json（版本号权威来源，electron-builder 据此命名安装包）
    # 与 frontend/package.json
    for path in [
        PROJECT_ROOT / "package.json",
        PROJECT_ROOT / "frontend" / "package.json",
    ]:
        if not path.exists():
            continue
        pkg = json.loads(path.read_text(encoding="utf-8"))
        if pkg.get("version") != version:
            pkg["version"] = version
            path.write_text(json.dumps(pkg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"  UPD: {path.relative_to(PROJECT_ROOT)}")


def update_nsis_scripts(version: str):
    for nsi in (PROJECT_ROOT / "build-scripts").glob("*.nsi"):
        content = nsi.read_text(encoding="utf-8")
        new_content = re.sub(
            r'!define PRODUCT_VERSION\s+"[^"]*"',
            f'!define PRODUCT_VERSION "{version}"',
            content,
        )
        if new_content != content:
            nsi.write_text(new_content, encoding="utf-8")
            print(f"  UPD: {nsi.relative_to(PROJECT_ROOT)}")


def update_env_example(version: str):
    # 前端 VITE_APP_VERSION（frontend/.env.example + .env.production）
    for env_path in [
        PROJECT_ROOT / "frontend" / ".env.example",
        PROJECT_ROOT / "frontend" / ".env.production",
    ]:
        if not env_path.exists():
            continue
        content = env_path.read_text(encoding="utf-8")
        new_content = re.sub(
            r'VITE_APP_VERSION=\S+',
            f'VITE_APP_VERSION={version}',
            content,
        )
        if new_content != content:
            env_path.write_text(new_content, encoding="utf-8")
            print(f"  UPD: {env_path.relative_to(PROJECT_ROOT)}")

    # 根 .env.example 的 PROJECT_VERSION（后端运行时读取）
    root_env_example = PROJECT_ROOT / ".env.example"
    if root_env_example.exists():
        content = root_env_example.read_text(encoding="utf-8")
        new_content = re.sub(
            r'PROJECT_VERSION=\S+',
            f'PROJECT_VERSION={version}',
            content,
        )
        if new_content != content:
            root_env_example.write_text(new_content, encoding="utf-8")
            print(f"  UPD: {root_env_example.relative_to(PROJECT_ROOT)}")


def main():
    version = get_version()
    print(f"Syncing version to {version}...")
    update_config_py(version)
    update_package_json(version)
    update_nsis_scripts(version)
    update_env_example(version)
    print("Done.")


if __name__ == "__main__":
    main()
