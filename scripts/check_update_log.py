#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布说明一致性门禁：CHANGELOG.md ↔ 应用内更新日志 ↔ backend/version.json。

背景（真实事故，同一类问题复发多次）
------------------------------------
1. 应用内「更新日志」曾由 `update_log_service.py` 里**硬编码**的列表驱动，与 CHANGELOG.md
   各写各的，长期停在 1.1.1（落后 17 个小版本），用户升级后看到的仍是两年前的说明。
2. `backend/version.json` 的 `description` / `features` / `build` / `release_date` 全靠手工维护，
   而 `sync-version.js` 只改 `version` 字段 —— 已连续 3 次出现"版本号 bump 了、说明还是上个版本"。

修法：CHANGELOG.md 是唯一账本 →
  - `scripts/sync_update_log.py` 生成 `backend/app/services/version_history_data.py`
  - 本门禁校验三处一致：生成文件、version.json、CHANGELOG 最新段

用法
----
    python3 scripts/check_update_log.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from sync_update_log import CHANGELOG, ROOT, TARGET, parse_changelog, render  # noqa: E402

VERSION_JSON = ROOT / "backend" / "version.json"


def _check_generated(data) -> list:
    """应用内更新日志数据模块必须与 CHANGELOG 生成结果逐字节一致。"""
    if not TARGET.exists():
        return ["未找到 %s（修复：python3 scripts/sync_update_log.py）" % TARGET.name]
    if TARGET.read_text(encoding="utf-8") != render(data):
        return [
            "应用内更新日志已过期：CHANGELOG 最新为 %s（共 %d 个版本），但 %s 未同步"
            % (data[-1]["version"], len(data), TARGET.name),
            "  修复：python3 scripts/sync_update_log.py",
        ]
    return []


def _check_version_json(data) -> list:
    """version.json 的版本/日期/说明必须来自最新版本段，features 不得为空。"""
    if not VERSION_JSON.exists():
        return ["未找到 backend/version.json"]

    try:
        payload = json.loads(VERSION_JSON.read_text(encoding="utf-8"))
    except ValueError as exc:
        return ["backend/version.json 不是合法 JSON：%s" % exc]

    latest = data[-1]
    problems = []

    if payload.get("version") != latest["version"]:
        problems.append(
            "version.json version=%r，CHANGELOG 最新为 %r（修复：node scripts/sync-version.js --write --version %s）"
            % (payload.get("version"), latest["version"], latest["version"])
        )

    if str(payload.get("release_date", "")).strip() != latest["date"]:
        problems.append(
            "version.json release_date=%r，CHANGELOG 最新为 %r"
            % (payload.get("release_date"), latest["date"])
        )

    expected_build = latest["date"].replace("-", "")
    if str(payload.get("build", "")).strip() != expected_build:
        problems.append(
            "version.json build=%r，应为 %r（release_date 去掉连字符）"
            % (payload.get("build"), expected_build)
        )

    if str(payload.get("description", "")).strip() != latest["description"].strip():
        problems.append(
            "version.json description 与 CHANGELOG 最新标题不一致：\n"
            "    version.json : %r\n    CHANGELOG    : %r"
            % (payload.get("description"), latest["description"])
        )

    features = payload.get("features")
    if not isinstance(features, list) or not features:
        problems.append("version.json features 为空——必须写明本次发布实际改了什么")

    return problems


def main() -> int:
    if not CHANGELOG.exists():
        print("[check-update-log] 未找到 CHANGELOG.md")
        return 1

    data = parse_changelog(CHANGELOG.read_text(encoding="utf-8"))
    if not data:
        print("[check-update-log] CHANGELOG.md 未解析出任何版本段")
        return 1

    problems = _check_generated(data) + _check_version_json(data)
    if problems:
        print("[check-update-log] 发布说明不一致（共 %d 处）：" % len(problems))
        for item in problems:
            print("  - %s" % item)
        return 1

    print("[check-update-log] OK：%d 个版本，最新 %s；应用内更新日志与 version.json 均与 CHANGELOG 一致"
          % (len(data), data[-1]["version"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
