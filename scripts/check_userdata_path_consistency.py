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

    # ── 2. Electron app.name 决定真实 userData 目录名 ──
    # Electron 语义：app.name = 根 package.json 的 productName（有则用），否则 name。
    # 注意 build.productName 只影响安装包/exe 命名，**不**影响 userData ——
    # 历史门禁把它排在前面，于是"门禁通过但卸载删错目录"（W19 实测踩中）。
    pkg = json.loads(_read("package.json"))
    app_name = pkg.get("productName") or pkg.get("name")
    if not app_name:
        errors.append("package.json 缺少 productName/name，无法确定 userData 目录名")
        app_name = "<unknown>"

    # ── 3. NSIS 钩子：安装期写入的路径必须指向**当前用户**的真实 userData ──
    hook = _read("build-scripts/electron-builder-nsis-hook.nsh")
    # 两个实测约束（W19）：
    #  a) perMachine 安装/卸载处于 all-users 上下文，$APPDATA 指向 C:\ProgramData，
    #     用户目录必须用 $PROFILE 拼；
    #  b) NSIS 反斜杠是字面量（makensis 实测 "C:\\A" → 两个反斜杠），
    #     所以源码里应为单反斜杠，写成双反斜杠会得到错误路径。
    expected_literal = "$PROFILE\\AppData\\Roaming\\" + app_name
    if expected_literal not in hook:
        errors.append(
            "NSIS 钩子未出现期望的 userData 字面量 "
            + expected_literal
            + "（Electron app.name=" + app_name + "）——安装期注册表/卸载期删除会与真实目录漂移"
        )
    if re.search(r"WriteRegStr[^\n]*UserDataPath[^\n]*\$APPDATA", hook):
        errors.append(
            "安装期注册表用 $APPDATA 拼用户目录：perMachine 下它指向 C:\\ProgramData，"
            "卸载会删错目录（应使用 $PROFILE）"
        )

    # 卸载段必须覆盖：真实 userData（多用户枚举）、LOCALAPPDATA 兜底目录、历史误判目录
    if "customUnInstall" not in hook:
        errors.append("NSIS 钩子缺少 customUnInstall 段")
    if "FindFirst" not in hook:
        errors.append("卸载段未枚举多用户 profile（$PROFILE\\..\\*）——多账号机器会残留用户数据")
    if "bumofu-assistance" not in hook:
        errors.append("卸载段未清理 bumofu-assistance 兜底数据目录（后端未注入 env 时会写这里）")

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
        "[gate:userdata_path] OK: app.name="
        + app_name
        + " | NSIS 注册表/兜底目录/卸载清理 三处一致"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
