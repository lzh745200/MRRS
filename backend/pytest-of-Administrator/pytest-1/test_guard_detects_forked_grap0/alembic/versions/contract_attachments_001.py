"""add attachments_json to fund_contracts (contract attachments out of remarks)

Revision ID: contract_attachments_001
Revises: subscription_last_sent_001
Create Date: 2026-09-06

R21 深探修复：合同附件此前被写进 `fund_contracts.remarks`（用户可见的「备注」列）。

- 现象 1：用户创建合同时填写的备注，在上传第一个附件后被附件 JSON 整体覆盖（静默丢数据）；
- 现象 2：编辑备注会反过来清空全部附件；
- 现象 3：合同列表/详情把这段 JSON 当「备注」出站。

修复：附件改存 `attachments_json`。本迁移除加列外，还把老库中「remarks 整体就是
附件数组」的脏数据搬迁到新列并把 remarks 清空（用户原文已被历史缺陷覆盖，不可恢复，
但至少不再冒充备注）。

注：`main.py` 启动时会先跑 `alembic upgrade head`，失败再回退到
`migrate_missing_columns` 自动补列；两者对本次新增的可空列结果一致，故安装实例
无论走哪条路径都能到位。
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "contract_attachments_001"
down_revision = "subscription_last_sent_001"
branch_labels = None
depends_on = None


def upgrade():
    """Add attachments_json to fund_contracts, then migrate legacy remarks payloads."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("fund_contracts"):
        return
    cols = {c["name"] for c in insp.get_columns("fund_contracts")}
    if "attachments_json" not in cols:
        op.add_column(
            "fund_contracts",
            sa.Column(
                "attachments_json",
                sa.Text(),
                nullable=True,
                comment="合同附件记录(JSON 数组)",
            ),
        )

    # 数据搬迁：remarks 整体是「含 url 的对象数组」→ 搬到新列并清空 remarks
    import json

    rows = bind.execute(
        sa.text("SELECT id, remarks FROM fund_contracts WHERE remarks IS NOT NULL")
    ).fetchall()
    for row in rows:
        raw = row[1]
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(parsed, list):
            continue
        items = [a for a in parsed if isinstance(a, dict) and "url" in a]
        if not items:
            continue
        bind.execute(
            sa.text(
                "UPDATE fund_contracts SET attachments_json = :payload, remarks = NULL "
                "WHERE id = :cid"
            ),
            {"payload": json.dumps(items, ensure_ascii=False), "cid": row[0]},
        )


def downgrade():
    """Remove attachments_json from fund_contracts (attachment records are dropped)."""
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("fund_contracts"):
        return
    cols = {c["name"] for c in insp.get_columns("fund_contracts")}
    if "attachments_json" in cols:
        with op.batch_alter_table("fund_contracts") as batch_op:
            batch_op.drop_column("attachments_json")
