"""create reminder_dispositions table

Revision ID: reminder_disp_001
Revises: user_session_001
Create Date: 2026-10-17 10:00:00

提醒中心处置闭环（.scratch/w17-feature-completion/001）：
提醒从"只能看"升级为"可处置"——处理 / 忽略（含理由）/ 延期 / 重新打开。
处置状态按"每人每条提醒一行"落在本表，与消息中心（messages）解耦。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "reminder_disp_001"
down_revision = "user_session_001"
branch_labels = None
depends_on = None


def upgrade():
    """Create reminder_dispositions table（幂等：已存在则跳过）."""
    insp = sa.inspect(op.get_bind())
    if insp.has_table("reminder_dispositions"):
        return
    op.create_table(
        "reminder_dispositions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True, comment="主键ID"),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            comment="提醒消息ID（唯一）",
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="处置人（提醒接收人）",
        ),
        sa.Column(
            "state",
            sa.String(16),
            nullable=False,
            server_default="open",
            comment="处置状态: open / handled / ignored",
        ),
        sa.Column("note", sa.String(500), nullable=True, comment="处置说明或忽略原因"),
        sa.Column("snooze_until", sa.DateTime(), nullable=True, comment="延期至（UTC，空=未延期）"),
        sa.Column("acted_at", sa.DateTime(), nullable=True, comment="最近一次处置动作时间（UTC）"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
            comment="更新时间",
        ),
    )
    # 与模型 metadata 等价：message_id 唯一（inline UNIQUE，SQLite 自动索引），
    # user_id+state 组合索引。注意 001_baseline 在空库上会按模型 metadata 建全表，
    # 该迁移只作用于"老库升级"路径——两条路径 schema 必须一致。
    op.create_index("ix_reminder_dispositions_user_state", "reminder_dispositions", ["user_id", "state"])


def downgrade():
    """Drop reminder_dispositions table."""
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("reminder_dispositions"):
        return
    op.drop_index("ix_reminder_dispositions_user_state", table_name="reminder_dispositions")
    op.drop_table("reminder_dispositions")
