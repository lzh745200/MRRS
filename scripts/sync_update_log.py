#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 CHANGELOG.md 生成应用内「更新日志」数据模块（单一账本）。

背景
----
应用内「更新日志」原先由 `app/services/update_log_service.py` 里的硬编码
`VERSION_HISTORY_DATA` 驱动，而 `CHANGELOG.md` 才是项目对外对内的唯一账本。
两份账本各写各的 → 应用内更新日志长期停在 1.1.1（实测落后 17 个小版本）。

本脚本把 CHANGELOG.md 解析成 `app/services/version_history_data.py`，
让运行时数据由唯一账本派生；`--check` 模式供 CI 门禁使用，二者不一致即失败。

用法
----
    python3 scripts/sync_update_log.py            # 重新生成
    python3 scripts/sync_update_log.py --check    # 只校验是否同步（CI）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
TARGET = ROOT / "backend" / "app" / "services" / "version_history_data.py"

HEADING_RE = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]\s*-\s*(\d{4}-\d{2}-\d{2})\s*(?:[—–-]\s*(.*))?$")
BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
MAX_FEATURES = 12
MAX_FEATURE_LEN = 220

HEADER = '''# -*- coding: utf-8 -*-
"""应用内「更新日志」数据（自动生成，请勿手工编辑）。

来源：仓库根目录 ``CHANGELOG.md``（唯一账本）。
生成：``python3 scripts/sync_update_log.py``
校验：``python3 scripts/sync_update_log.py --check``（CI 门禁，不一致即失败）

改版本说明请改 CHANGELOG.md，然后重跑生成脚本；直接改本文件会被门禁拦下。
"""

VERSION_HISTORY_DATA = '''


def _clean(text: str) -> str:
    """去掉 Markdown 装饰，保留可读纯文本。"""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)   # [文字](链接) → 文字
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_FEATURE_LEN:
        text = text[: MAX_FEATURE_LEN - 1].rstrip() + "…"
    return text


def parse_changelog(text: str) -> List[Dict]:
    """把 CHANGELOG 文本解析为 [{version, date, description, features}, ...]（升序）。"""
    entries: Dict[str, Dict] = {}
    order: List[str] = []
    cur = None
    in_fence = False

    for raw in text.splitlines():
        line = raw.rstrip()

        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        m = HEADING_RE.match(line)
        if m:
            version, date, title = m.group(1), m.group(2), (m.group(3) or "").strip()
            if version in entries:      # 历史重复段（如 1.1.0 出现两次）保留首段
                cur = None
                continue
            cur = {"version": version, "date": date, "description": _clean(title), "features": []}
            entries[version] = cur
            order.append(version)
            continue

        if line.startswith("## "):      # 其他二级标题结束当前段
            cur = None
            continue
        if cur is None:
            continue

        bm = BULLET_RE.match(line)
        if bm:
            item = _clean(bm.group(1))
            if not item or item.startswith("|"):
                continue
            if len(cur["features"]) < MAX_FEATURES:
                cur["features"].append(item)

    result = []
    for version in order:
        item = entries[version]
        if not item["features"]:
            item["features"] = [item["description"] or "本次更新"]
        if not item["description"]:
            item["description"] = item["features"][0]
        result.append(item)

    def key(v: str):
        return tuple(int(x) for x in v.split("."))

    result.sort(key=lambda d: key(d["version"]))
    return result


def _literal(text: str, indent: str, budget: int = 96) -> str:
    """生成 Python 字符串字面量；超长内容用相邻字面量隐式拼接，满足 flake8 E501。

    `budget` 是**转义后**单段的最大长度：json.dumps 会把引号、反斜杠转义成两字符，
    按原文长度切分仍可能超行宽，因此这里按转义结果贪心切分。
    """
    if len(json.dumps(text, ensure_ascii=False)) <= budget:
        return json.dumps(text, ensure_ascii=False)

    chunks: List[str] = []
    cur = ""
    for ch in text:
        if cur and len(json.dumps(cur + ch, ensure_ascii=False)) > budget:
            chunks.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        chunks.append(cur)

    inner = "\n".join('%s    %s' % (indent, json.dumps(c, ensure_ascii=False)) for c in chunks)
    return "(\n%s\n%s)" % (inner, indent)


def render(data: List[Dict]) -> str:
    out = [HEADER.rstrip() + " ["]
    for item in data:
        out.append("    {")
        out.append('        "version": %s,' % json.dumps(item["version"]))
        out.append('        "date": %s,' % json.dumps(item["date"]))
        out.append('        "description": %s,' % _literal(item["description"], "        "))
        out.append('        "features": [')
        for feat in item["features"]:
            out.append("            %s," % _literal(feat, "            "))
        out.append("        ],")
        out.append("    },")
    out.append("]")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="从 CHANGELOG.md 生成应用内更新日志数据")
    ap.add_argument("--check", action="store_true", help="只校验，不写文件；不一致返回 1")
    args = ap.parse_args()

    if not CHANGELOG.exists():
        print("[update-log] 未找到 CHANGELOG.md：%s" % CHANGELOG)
        return 1

    data = parse_changelog(CHANGELOG.read_text(encoding="utf-8"))
    if not data:
        print("[update-log] CHANGELOG.md 未解析出任何版本段")
        return 1

    expected = render(data)
    actual = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""

    if args.check:
        if actual != expected:
            print("[update-log] 应用内更新日志与 CHANGELOG.md 不一致")
            print("  CHANGELOG 版本数: %d，最新: %s" % (len(data), data[-1]["version"]))
            print("  修复：python3 scripts/sync_update_log.py")
            return 1
        print("[update-log] OK：%d 个版本，最新 %s" % (len(data), data[-1]["version"]))
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(expected, encoding="utf-8", newline="\n")
    print("[update-log] 已生成 %s" % TARGET.relative_to(ROOT))
    print("  版本数: %d，范围: %s → %s" % (len(data), data[0]["version"], data[-1]["version"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
