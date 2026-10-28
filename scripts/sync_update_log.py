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
VERSION_JSON = ROOT / "backend" / "version.json"

HEADING_RE = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]\s*-\s*(\d{4}-\d{2}-\d{2})\s*(?:[—–-]\s*(.*))?$")
BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
MAX_FEATURES = 12
MAX_FEATURE_LEN = 220
# 只写给维护者的内部小节：不进用户可见的更新日志
META_SECTIONS = ("验证", "自测", "备注", "Verification", "Notes")

HEADER = '''# -*- coding: utf-8 -*-
"""应用内「更新日志」数据（自动生成，请勿手工编辑）。

来源：仓库根目录 ``CHANGELOG.md``（唯一账本）。
生成：``python3 scripts/sync_update_log.py``
校验：``python3 scripts/sync_update_log.py --check``（CI 门禁，不一致即失败）

改版本说明请改 CHANGELOG.md，然后重跑生成脚本；直接改本文件会被门禁拦下。
"""

VERSION_HISTORY_DATA = '''


def _clean(text: str) -> str:
    """去掉 Markdown 装饰，保留可读纯文本；超长时在标点处收尾，避免半句截断。"""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)   # [文字](链接) → 文字
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"\s+", " ", text).strip().rstrip("：:").strip()
    if len(text) <= MAX_FEATURE_LEN:
        return text

    head = text[:MAX_FEATURE_LEN]
    for mark in ("。", "；", "！", "？"):
        pos = head.rfind(mark)
        if pos >= MAX_FEATURE_LEN * 0.5:
            return head[: pos + 1]
    pos = head.rfind("，")
    if pos >= MAX_FEATURE_LEN * 0.5:
        return head[:pos] + "…"
    return head.rstrip() + "…"


def parse_changelog(text: str) -> List[Dict]:  # noqa: C901 - 逐行状态机，分支天然多，拆开反而更难读
    """把 CHANGELOG 文本解析为 [{version, date, description, features}, ...]（升序）。

    跳过 `[Unreleased]` / `[未发布]` 等非语义化版本段（无发布号，不属于版本历史），
    并跳过 `### 验证` 这类内部小节 —— 它们写给维护者看，不适合出现在用户可见的更新日志里。
    """
    entries: Dict[str, Dict] = {}
    order: List[str] = []
    cur = None
    in_fence = False
    skip_section = False
    skip_nested = False

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
            skip_section = False
            skip_nested = False
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

        if line.startswith("### "):
            # 内部小节（验证/自测/备注）不进用户可见日志
            skip_section = any(k in line for k in META_SECTIONS)
            continue

        if cur is None or skip_section:
            continue

        bm = BULLET_RE.match(line)
        if bm:
            raw_item = bm.group(1).strip()
            if raw_item.startswith("|"):
                continue
            skip_nested = False
            if len(cur["features"]) < MAX_FEATURES:
                cur["features"].append(raw_item)
            continue

        # 子条目（缩进的 - / * / 1. / 1)）属于细节，不进用户可见日志；
        # 它们的折行续行也必须一起跳过，否则会被拼到父条目上变成串行。
        if re.match(r"^\s+(?:[-*]|\d+[.)])\s", line):
            skip_nested = True
            continue

        # CHANGELOG 的要点常折行书写（续行缩进、不以列表符号开头）：拼回上一条，
        # 否则用户看到的每条要点都是被截断的半句话。
        if cur["features"] and not skip_nested and line.startswith("  "):
            cur["features"][-1] = cur["features"][-1] + line.strip()

    result = []
    for version in order:
        item = entries[version]
        cleaned = [_clean(feat) for feat in item["features"]]
        item["features"] = [feat for feat in cleaned if feat] or [item["description"] or "本次更新"]
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


def sync_version_json(data: List[Dict], path: Path = VERSION_JSON) -> List[str]:
    """把最新版本的 description / release_date / build 写进 backend/version.json。

    为什么由本脚本负责：这三项与 CHANGELOG 最新标题是同一事实，却一直靠手工抄 ——
    每次发版忘改就会被 check_update_log.py 拦下（实测 2026-10-28 又踩一次）。
    features 是人工撰写的发布要点，**不在此自动覆盖**。

    Returns:
        发生变更的字段说明列表；文件缺失 / 非法 JSON / 已一致时返回空列表。
    """
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    latest = data[-1]
    expected = {
        "description": latest["description"],
        "release_date": latest["date"],
        "build": latest["date"].replace("-", ""),
    }
    changed = [key for key, value in expected.items() if payload.get(key) != value]
    if not changed:
        return []

    payload.update(expected)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return ["%s -> %r" % (key, expected[key]) for key in changed]


def check_version_json(data: List[Dict], path: Path = VERSION_JSON) -> List[str]:
    """--check 用：version.json 的三项是否仍与 CHANGELOG 最新段一致。"""
    if not path.exists():
        return ["未找到 backend/version.json"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ["backend/version.json 不是合法 JSON：%s" % exc]

    latest = data[-1]
    expected = {
        "description": latest["description"],
        "release_date": latest["date"],
        "build": latest["date"].replace("-", ""),
    }
    return [
        "version.json %s=%r，CHANGELOG 最新为 %r" % (key, payload.get(key), value)
        for key, value in expected.items()
        if payload.get(key) != value
    ]


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
        problems = []
        if actual != expected:
            problems.append("应用内更新日志与 CHANGELOG.md 不一致")
        problems.extend(check_version_json(data))
        if problems:
            print("[update-log] 发现 %d 处不一致" % len(problems))
            for problem in problems:
                print("  - " + problem)
            print("  CHANGELOG 版本数: %d，最新: %s" % (len(data), data[-1]["version"]))
            print("  修复：python3 scripts/sync_update_log.py")
            return 1
        print("[update-log] OK：%d 个版本，最新 %s" % (len(data), data[-1]["version"]))
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(expected, encoding="utf-8", newline="\n")
    print("[update-log] 已生成 %s" % TARGET.relative_to(ROOT))
    print("  版本数: %d，范围: %s → %s" % (len(data), data[0]["version"], data[-1]["version"]))
    synced = sync_version_json(data)
    if synced:
        print("[update-log] 已同步 %s：" % VERSION_JSON.relative_to(ROOT))
        for line in synced:
            print("  - " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
