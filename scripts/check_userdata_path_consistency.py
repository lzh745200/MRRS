#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""门禁：校验卸载/数据目录口径三处一致（W18 P1-5 防漂移）。

三个地方各自描述"用户数据在哪"，任何一处单独改动都会静默漂移：
  1. electron/main.js        —— getUserDataPath() 返回 app.getPath(userData)
  2. build-scripts/electron-builder-nsis-hook.nsh —— 安装期写注册表、卸载期删除
  3. backend/app/utils/paths.py —— 未注入 env 时的兜底目录（LOCALAPPDATA/bumofu-assistance）

漂移后果：卸载删错目录 —— 要么残留隐私数据，要么删空用户数据，且**只有卸载时**才暴露。
本门禁把"人工保持一致"换成 CI 断言。

用法：python scripts/check_userdata_path_consistency.py
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel_path):
    return io.open(os.path.join(ROOT, rel_path), encoding="utf-8").read()


def main():
    errors = []

    # ── 1. Electron 侧：userData 必须是默认值，不得被 setPath 改写 ──
    main_js = _read("electron/main.js")
    if "setPath(" in main_js and "userData" in main_js:
        # 允许注释里提到，但不允许真实调用 setPath('userData', ...)
        if re.search(r"setPath\(\s*['\"]userData['\"]", main_js):
            errors.append("electron/main.js 用了 setPath(userData)：与 NSIS 注册表口径不再同源")

    # ── 2. productName 决定真实 userData 目录名 ──
    pkg = json.loads(_read("package.json"))
    build = pkg.get("build", {})
    product_name = build.get("productName") or pkg.get("productName") or pkg.get("name")
    if not product_name:
        errors.append("package.json 缺少 productName/name，无法确定 userData 目录名")
        product_name = "<unknown>"

    # ── 3. NSIS 钩子：安装期写入的路径必须等于 %APPDATA%\\<productName> ──
    hook = _read("build-scripts/electron-builder-nsis-hook.nsh")
    # NSIS 源码里反斜杠要写成 \\（C 风格转义），因此匹配两个反斜杠的源文本形式
    expected_literal = "$APPDATA\\\\" + product_name
    if expected_literal not in hook:
        errors.append(
            "NSIS 钩子未出现期望的 userData 字面量 " + expected_literal +
            "（package.json productName=" + product_name + "）——安装期注册表/卸载期删除会与真实目录漂移"
        )

    # 卸载段必须同时覆盖 APPDATA 真实目录与 LOCALAPPDATA 兜底目录
    if "customUnInstall" not in hook:
        errors.append("NSIS 钩子缺少 customUnInstall 段")
    if "LOCALAPPDATA" not in hook:
        errors.append("NSIS 卸载段未清理 LOCALAPPDATA 兜底目录（后端未注入 env 时会写这里）")

    # ── 4. backend paths.py 兜底目录名必须与钩子一致 ──
    paths_py = _read("backend/app/utils/paths.py")
    m = re.search(r'Path\(base_dir\)\s*/\s*"([^"]+)"', paths_py)
    if not m:
        errors.append("paths.py 未找到 Windows 兜底目录定义（Path(base_dir) / \"dir\"）")
    else:
        fallback_dir = m.group(1)
        if fallback_dir not in hook:
            errors.append(
                "paths.py 兜底目录 " + fallback_dir + " 未被 NSIS 卸载段清理 —— 卸载会残留该目录"
            )

    if errors:
        print("[gate:userdata_path] FAIL: 数据目录口径不一致", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        return 1

    print(
        "[gate:userdata_path] OK: productName=" + product_name +
        " | NSIS 注册表/兜底目录/卸载清理 三处一致"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())