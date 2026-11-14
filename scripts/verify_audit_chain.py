#!/usr/bin/env python3
"""校验 audit_logs 哈希链（AUDIT_CHAIN_ENABLED 开启后使用）。

用法:
    python scripts/verify_audit_chain.py [--db sqlite:///...]
退出码 0=完整，1=断链/篡改，2=数据库不可用。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="", help="覆盖 DATABASE_URL（默认读配置）")
    args = parser.parse_args()
    if args.db:
        import os

        os.environ["DATABASE_URL"] = args.db
    try:
        from app.core.audit_chain import verify_chain
        from app.core.database import SessionLocal
        from app.models.audit import AuditLog
    except Exception as exc:  # noqa: BLE001
        print(f"[audit-chain] 初始化失败: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    db = SessionLocal()
    try:
        rows = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    finally:
        db.close()
    ok, broken_id = verify_chain(rows)
    if not ok:
        print(f"[audit-chain] FAIL：首个断链记录 id={broken_id}", file=sys.stderr)
        return 1
    print(f"[audit-chain] OK：{len(rows)} 条记录链完整")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
