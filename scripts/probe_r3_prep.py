# -*- coding: utf-8 -*-
"""Round-3 prep: clone dev DB + reset admin pw (probe_r3)."""
import os
import sqlite3
import sys

sys.path.insert(0, r"C:\military-Rural Revitalization-system\backend")

SRC = r"C:\military-Rural Revitalization-system\backend\data\rural_revitalization.db"
DST = r"C:\military-Rural Revitalization-system\backend\data\probe_r3.db"
for suf in ("", "-wal", "-shm"):
    p = DST + suf
    if os.path.exists(p):
        os.remove(p)
con = sqlite3.connect(SRC)
con.execute("VACUUM INTO ?", (DST,))
con.close()

from app.core.security import get_password_hash  # noqa: E402

c = sqlite3.connect(DST)
c.execute(
    "UPDATE users SET hashed_password=?, failed_login_count=0, locked_until=NULL, "
    "must_change_password=0 WHERE username='admin'",
    (get_password_hash("Admin@12345"),),
)
c.commit()
c.close()
print("DST ok")
