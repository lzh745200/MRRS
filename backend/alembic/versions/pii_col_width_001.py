"""pii_col_width_001: PII 加密列的列宽统一到 256

背景（2026-10-29 全库审计，Critical）：

PII 列用 `EncryptedText` 透明加密，落库是 `enc.v1:` + base64(AES-SIV 密文)。
实测密文长度：

    id_card(18)  -> 55 字符
    id_card(64)  -> 115 字符
    phone(11)    -> 43 字符
    phone(20)    -> 55 字符
    phone(50)    -> 95 字符

而**实际库里的列宽只有 VARCHAR(20)**（旧迁移 Historically 生成），模型侧虽写
`EncryptedText(64)` 也放不下最长密文。SQLite 不强制 VARCHAR 长度，所以现在"能存"；
换成 MySQL / PostgreSQL 会直接 `Data too long for column` 写入失败。

本迁移把 9 个 PII 列统一到 VARCHAR(256)，与模型侧 `EncryptedText(256)` 对齐。

注意：SQLite 不支持 ALTER COLUMN，用 batch_alter_table 走"建新表-拷数据-换名"。
每列都先判存在性 —— 历史库可能已缺表/缺列（r36 删过 rural_tasks）。

Revision ID: pii_col_width_001
revises: r43_prune_dead_columns_001
"""

from alembic import op
import sqlalchemy as sa

revision = "pii_col_width_001"
down_revision = "r43_prune_dead_columns_001"
branch_labels = None
depends_on = None

TARGET_LENGTH = 256

# (表, 列)：ADR-0005 的 9 列中仍在的 8 列（rural_tasks.contact_phone 随 r36 表删除）
PII_COLUMNS = [
    ("households", "helper_phone"),
    ("household_members", "id_card"),
    ("village_committee_members", "phone"),
    ("users", "phone"),
    ("organizations", "contact_phone"),
    ("projects", "contact_phone"),
    ("rural_works", "contact_phone"),
    ("schools", "contact_phone"),
]


def _columns_of(bind, table: str):
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return {}
    return {c["name"]: c for c in insp.get_columns(table)}


def _widen(bind, table: str, column: str, length: int) -> bool:
    cols = _columns_of(bind, table)
    if column not in cols:
        return False
    current = cols[column].get("type")
    current_len = getattr(current, "length", None)
    if current_len is not None and current_len >= length:
        return False  # 已经够宽，跳过（幂等）
    with op.batch_alter_table(table) as batch:
        batch.alter_column(
            column,
            existing_type=current,
            type_=sa.String(length=length),
            existing_nullable=cols[column].get("nullable", True),
        )
    return True


def upgrade() -> None:
    bind = op.get_bind()
    changed = []
    for table, column in PII_COLUMNS:
        if _widen(bind, table, column, TARGET_LENGTH):
            changed.append(f"{table}.{column}")
    print(f"pii_col_width_001: widened {len(changed)} column(s): {changed}")


def downgrade() -> None:
    """回退到与模型旧声明一致的 64。

    注意：**有损**——若库里已存着长度 >64 的密文，缩窄会导致截断（严格引擎报错、
    SQLite 静默截断破坏可解密性）。因此降级前应确认无超长密文，本函数只做类型回退，
    不负责数据保全。
    """
    bind = op.get_bind()
    for table, column in PII_COLUMNS:
        cols = _columns_of(bind, table)
        if column not in cols:
            continue
        current = cols[column].get("type")
        if getattr(current, "length", None) == 64:
            continue
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                column,
                existing_type=current,
                type_=sa.String(length=64),
                existing_nullable=cols[column].get("nullable", True),
            )