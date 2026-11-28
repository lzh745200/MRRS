#!/usr/bin/env python
"""只读核查旧版账号包导入现场（T08）。

背景：v1.18.64 之前，账号包导入会把「空授权」写成显式的空菜单并置
``organizations.grant_version = 1``；导入后的普通用户因此只能看到工作台。
新版代码已修复，但既有库不会自动恢复。

本脚本只读，不改任何数据。命中条件（三者同时成立）：
1. 存在 ``account_package_receipts`` 回执；
2. 回执的 ``activated_org_id`` 对应组织 ``grant_version >= 1``；
3. 该组织在 ``org_grants`` 中没有任何授权行，且该组织下有用户
   ``allowed_menus`` 为空数组 ``"[]"``。

若命中，只输出组织/账号清单，供人工备份后按
``deliverables/未完成项与风险闭环处理方案.md`` T08 一次性修复。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def check(db_path: Path) -> list[dict]:
    if not db_path.exists():
        raise SystemExit(f"数据库不存在: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(
                """
                SELECT r.package_id,
                       r.activated_org_id AS org_id,
                       o.name AS org_name,
                       o.grant_version,
                       (SELECT COUNT(*) FROM org_grants g
                         WHERE g.organization_id = r.activated_org_id) AS grant_rows,
                       u.id AS user_id,
                       u.username,
                       u.allowed_menus
                  FROM account_package_receipts r
                  JOIN organizations o ON o.id = r.activated_org_id
                  JOIN users u ON u.organization_id = r.activated_org_id
                 WHERE r.activated_org_id IS NOT NULL
                   AND o.grant_version >= 1
                   AND u.allowed_menus = '[]'
                 ORDER BY r.activated_org_id, u.id
                """
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc):
                # 该库版本从未创建账号包回执表，等价于「从未导入旧包」。
                return []
            raise
        affected: dict[int, dict] = {}
        for row in rows:
            if row["grant_rows"] > 0:
                continue
            entry = affected.setdefault(
                row["org_id"],
                {
                    "org_id": row["org_id"],
                    "org_name": row["org_name"],
                    "grant_version": row["grant_version"],
                    "packages": [],
                    "users": [],
                },
            )
            if row["package_id"] not in entry["packages"]:
                entry["packages"].append(row["package_id"])
            entry["users"].append({"id": row["user_id"], "username": row["username"]})
        return list(affected.values())
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "rural_revitalization.db",
        help="SQLite 数据库路径（默认 backend/data/rural_revitalization.db）",
    )
    parser.add_argument("--json", action="store_true", help="仅输出 JSON")
    args = parser.parse_args()

    affected = check(args.database)
    if args.json:
        print(json.dumps(affected, ensure_ascii=False, indent=2))
        return 0 if not affected else 2

    if not affected:
        print("[OK] 未发现受旧版账号包影响的组织/账号（无回执命中）。")
        return 0
    print(f"[WARN] 命中 {len(affected)} 个组织，需备份后人工修复：")
    for item in affected:
        print(f"  组织 {item['org_id']} {item['org_name']} grant_version={item['grant_version']}")
        print(f"    回执: {', '.join(item['packages'])}")
        print(f"    受影响账号: {', '.join(u['username'] for u in item['users'])}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
