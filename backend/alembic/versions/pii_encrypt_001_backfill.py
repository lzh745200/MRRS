"""PII 字段加密存量回填（W5-T7 / ADR-0005）

模型列已切换为 EncryptedText（确定性 AES-SIV 透明加解密）。本迁移把存量明文
就地加密为 `enc.v1:` 标记密文；幂等（已加密值跳过），可断点重跑。
SQLite 不强制 VARCHAR 长度，密文长度（≤55 字符）无需改列宽。

降级说明：如需回退，先移除模型上的 EncryptedText，再执行 downgrade 将
密文解密回明文（需持同一密钥，downgrade 失败时保留密文原值不破坏数据）。

Revision ID: pii_encrypt_001
Revises: dead_models_001
Create Date: 2026-08-30
"""
import logging

from alembic import op

revision = "pii_encrypt_001"
down_revision = "dead_models_001"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime")


def _iter_pii_columns():
    """(table, column) 清单，与模型 EncryptedText 列保持一致"""
    return [
        ("villagers", "id_card"),
        ("villagers", "phone"),
        ("village_committee_members", "phone"),
        ("users", "phone"),
        ("organizations", "contact_phone"),
        ("projects", "contact_phone"),
        ("rural_works", "contact_phone"),
        ("rural_tasks", "contact_phone"),
        ("schools", "contact_phone"),
    ]


def upgrade() -> None:
    from app.core.pii_crypto import encrypt_pii, is_encrypted

    conn = op.get_bind()
    for table, column in _iter_pii_columns():
        rows = conn.exec_driver_sql(
            f'SELECT id, "{column}" FROM "{table}" '
            f'WHERE "{column}" IS NOT NULL AND "{column}" NOT LIKE \'enc.v1:%\''
        ).fetchall()
        for row_id, plaintext in rows:
            if is_encrypted(plaintext):
                continue
            conn.exec_driver_sql(
                f'UPDATE "{table}" SET "{column}" = ? WHERE id = ?',
                (encrypt_pii(plaintext), row_id),
            )
        logger.info("PII 回填 %s.%s: %d 行", table, column, len(rows))


def downgrade() -> None:
    from app.core.pii_crypto import decrypt_pii

    conn = op.get_bind()
    for table, column in _iter_pii_columns():
        rows = conn.exec_driver_sql(
            f'SELECT id, "{column}" FROM "{table}" WHERE "{column}" LIKE \'enc.v1:%\''
        ).fetchall()
        for row_id, ciphertext in rows:
            conn.exec_driver_sql(
                f'UPDATE "{table}" SET "{column}" = ? WHERE id = ?',
                (decrypt_pii(ciphertext), row_id),
            )
        logger.info("PII 回退 %s.%s: %d 行", table, column, len(rows))
