#!/usr/bin/env python
"""只读盘点「data_scope=all 的非超管账号」（T06 迁移前清单）。

T06 规则：只有 superuser 可跨组织；非超管的 ``data_scope='all'`` 在运行期
会被收敛为本组织/仅本人。迁移前应先盘点存量，不能无提示改库。

本脚本只读，不修改数据；``--json`` 便于接入发布检查单。
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
                SELECT id, username, role, organization_id, data_scope
                  FROM users
                 WHERE data_scope = 'all'
                   AND COALESCE(is_superuser, 0) = 0
                 ORDER BY id
                """
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc):
                return []
            raise
        return [dict(r) for r in rows]
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

    rows = check(args.database)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0 if not rows else 2
    if not rows:
        print("[OK] 未发现 data_scope=all 的非超管账号。")
        return 0
    print(f"[WARN] 发现 {len(rows)} 个 data_scope=all 的非超管账号（运行期将按本组织收敛）：")
    for row in rows:
        print(
            f"  id={row['id']} username={row['username']} role={row['role']} "
            f"org={row['organization_id']} scope={row['data_scope']}"
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
