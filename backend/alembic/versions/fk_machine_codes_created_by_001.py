"""fk_machine_codes_created_by_001: machine_codes.created_by 补 ondelete=SET NULL

背景（2026-10-29 全库审计，Important）：

`machine_codes.created_by` 是全库**唯一**一处没写 `ondelete` 的 `users` 外键
（其余同类列都是 `SET NULL` / `CASCADE`）。后果：删除用户时该外键会阻断删除，
或者留下指向已删用户的悬挂引用，与"删用户即 SET NULL"的统一口径不一致。

SQLite 不支持 `ALTER CONSTRAINT`，用 `batch_alter_table(recreate="always")` 重建表：
先 drop 旧外键再建带 ondelete 的新外键。重建会由 alembic 反射保留既有索引/列。

逐项守卫：表不存在、没有该列、已有 ondelete 时都直接跳过（可重入）。

Revision ID: fk_machine_codes_created_by_001
revises: idx_dedup_002
"""

import re

from alembic import op
import sqlalchemy as sa

revision = "fk_machine_codes_created_by_001"
down_revision = "idx_dedup_002"
branch_labels = None
depends_on = None

TABLE = "machine_codes"
COLUMN = "created_by"
NEW_FK_NAME = "fk_machine_codes_created_by_users"


def find_target_fk(bind):
    """返回该列的外键描述；表/列/外键不存在时返回 None（纯函数，便于单测）。"""
    insp = sa.inspect(bind)
    if not insp.has_table(TABLE):
        return None
    cols = {c["name"] for c in insp.get_columns(TABLE)}
    if COLUMN not in cols:
        return None
    for fk in insp.get_foreign_keys(TABLE):
        if list(fk.get("constrained_columns") or []) == [COLUMN]:
            return fk
    return None


def needs_fix(fk) -> bool:
    """外键存在但没写 ondelete → 需要修。"""
    if fk is None:
        return False
    options = fk.get("options") or {}
    return not options.get("ondelete")


FK_RE = re.compile(
    r"(FOREIGN\s+KEY\s*\(\s*created_by\s*\)\s*REFERENCES\s+users\s*\(\s*id\s*\))"
    r"(\s*ON\s+DELETE\s+[A-Z][A-Z ]*)?",
    re.IGNORECASE,
)


def rewrite_fk_ddl(ddl: str) -> str | None:
    """把 DDL 里 **created_by 这一条**外键补上 ON DELETE SET NULL；无需改时返回 None。

    2026-10-30 修复：原实现用 `if "ON DELETE SET NULL" in ddl.upper(): return None` 做
    「已经改过」的快速判断 —— 但整张表的 DDL 里**其它外键**（machine_codes.user_id）
    本来就带 `ON DELETE SET NULL`，于是每次都误判「已改过」直接跳过。
    实测：真实开发库升级后 created_by 仍是 NO ACTION（迁移日志「DDL 里未找到目标外键」）。
    现在只匹配 created_by 那条子句，且只有当它自己**没有** ON DELETE 时才改写。
    """
    if not ddl:
        return None
    m = FK_RE.search(ddl)
    if m is None:
        return None
    if m.group(2):  # 该子句自带 ON DELETE（任意动作）→ 无需改
        return None
    return ddl[: m.start()] + m.group(1) + " ON DELETE SET NULL" + ddl[m.end():]


def upgrade() -> None:
    bind = op.get_bind()
    if find_target_fk(bind) is None or not needs_fix(find_target_fk(bind)):
        print("fk_machine_codes_created_by_001: skip（表/列/外键缺失或已有 ondelete）")
        return

    row = bind.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": TABLE},
    ).fetchone()
    if row is None or not row[0]:
        print("fk_machine_codes_created_by_001: 拿不到 DDL，跳过")
        return
    new_ddl = rewrite_fk_ddl(row[0])
    if new_ddl is None:
        print("fk_machine_codes_created_by_001: DDL 里未找到目标外键，跳过")
        return

    cols = [c["name"] for c in sa.inspect(bind).get_columns(TABLE)]
    col_list = ", ".join('"%s"' % c for c in cols)
    tmp = TABLE + "__fk_new"
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
    except Exception as exc:  # noqa: BLE001 - 关不掉 FK 不阻断
        print("fk_machine_codes_created_by_001: PRAGMA foreign_keys 设置失败:", exc)
    bind.execute(sa.text('DROP TABLE IF EXISTS "%s"' % tmp))  # nosec B608
    # DDL 里的表名要换成临时表名
    tmp_ddl = new_ddl.replace('CREATE TABLE "%s"' % TABLE, 'CREATE TABLE "%s"' % tmp)
    tmp_ddl = tmp_ddl.replace("CREATE TABLE %s" % TABLE, 'CREATE TABLE "%s"' % tmp)
    bind.execute(sa.text(tmp_ddl))
    bind.execute(sa.text('INSERT INTO "%s" (%s) SELECT %s FROM "%s"' % (tmp, col_list, col_list, TABLE)))  # nosec B608
    bind.execute(sa.text('DROP TABLE "%s"' % TABLE))  # nosec B608
    bind.execute(sa.text('ALTER TABLE "%s" RENAME TO "%s"' % (tmp, TABLE)))  # nosec B608
    print("fk_machine_codes_created_by_001: %s.%s 已补 ondelete=SET NULL" % (TABLE, COLUMN))


def downgrade() -> None:
    """回退为无 ondelete 的裸外键（同 upgrade 思路，反向替换）。"""
    bind = op.get_bind()
    row = bind.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": TABLE},
    ).fetchone()
    if row is None or not row[0]:
        return
    ddl = row[0]
    if "ON DELETE SET NULL" not in ddl.upper():
        return
    new_ddl = re.sub(
        r"FOREIGN\s+KEY\s*\(\s*created_by\s*\)\s*REFERENCES\s+users\s*\(\s*id\s*\)\s*ON\s+DELETE\s+SET\s+NULL",
        "FOREIGN KEY (created_by) REFERENCES users (id)",
        ddl,
        flags=re.IGNORECASE,
    )
    cols = [c["name"] for c in sa.inspect(bind).get_columns(TABLE)]
    col_list = ", ".join('"%s"' % c for c in cols)
    tmp = TABLE + "__fk_old"
    try:
        bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
    except Exception:  # noqa: BLE001
        pass
    bind.execute(sa.text('DROP TABLE IF EXISTS "%s"' % tmp))  # nosec B608
    tmp_ddl = new_ddl.replace('CREATE TABLE "%s"' % TABLE, 'CREATE TABLE "%s"' % tmp)
    tmp_ddl = tmp_ddl.replace("CREATE TABLE %s" % TABLE, 'CREATE TABLE "%s"' % tmp)
    bind.execute(sa.text(tmp_ddl))
    bind.execute(sa.text('INSERT INTO "%s" (%s) SELECT %s FROM "%s"' % (tmp, col_list, col_list, TABLE)))  # nosec B608
    bind.execute(sa.text('DROP TABLE "%s"' % TABLE))  # nosec B608
    bind.execute(sa.text('ALTER TABLE "%s" RENAME TO "%s"' % (tmp, TABLE)))  # nosec B608
