"""W22（v1.14.0）：一户一档 / 影像库 / 消费帮扶 建表 + 删除 Village 遗留表

Revision ID: w22_household_media_consumption_001
Revises: visit_attach_001
Create Date: 2026-10-18

背景（用户 W22 需求）：
- 新增「一户一档」（households / household_members / household_risk_records）与
  「影像库」（photo_archives）、「消费帮扶」（consumption_records，替换已下线的舆情采集）；
- 走访记录挂户：``visit_records.household_id``；
- 删除遗留的 ``villages`` / ``villagers`` / ``industries`` / ``sentiment_news`` 表；
- 原引用 ``villages.id`` 的四张表（``rural_works`` / ``rural_tasks`` /
  ``tea_plantations`` / ``cactus_fruit_plots``）改为引用 ``supported_villages.id``。

两路径兼容（与项目既有迁移同一模式）：
- 空库初始化：001_baseline 按当前 metadata ``create_all`` 已建新表 → 本迁移检测到即跳过；
- 老库升级：逐项补齐列/表，并在删除 villages 之前按村名 + 组织回填
  ``supported_village_id``（无法匹配的保持 NULL，不阻断升级）。
"""

from alembic import op
import sqlalchemy as sa

revision = "w22_household_media_consumption_001"
down_revision = "visit_attach_001"
branch_labels = None
depends_on = None


# ── 幂等辅助 ──────────────────────────────────────────────
def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))


def _create_table_if_absent(name: str, *columns, **kwargs) -> None:
    if not _table_exists(name):
        op.create_table(name, *columns, **kwargs)


# ── 建表辅助：审计列（与全库一致）──────────────────────────
def _audit_columns() -> list:
    return [
        sa.Column("organization_id", sa.Integer(), nullable=True, comment="所属组织ID"),
        sa.Column("created_by", sa.Integer(), nullable=True, comment="创建者ID"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true(), comment="是否有效(软删)"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="软删时间"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    ]


# ── 升级 ──────────────────────────────────────────────────
def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. households（一户一档）──
    _create_table_if_absent(
        "households",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("supported_village_id", sa.Integer(), sa.ForeignKey("supported_villages.id", ondelete="CASCADE"), nullable=False, comment="帮扶村ID"),
        sa.Column("household_code", sa.String(64), nullable=True, comment="户编号(村内唯一)"),
        sa.Column("household_name", sa.String(64), nullable=False, comment="户主姓名"),
        sa.Column("address", sa.String(255), nullable=True, comment="家庭住址"),
        sa.Column("household_type", sa.String(20), nullable=False, server_default="general", comment="户类型: general/poverty/monitor"),
        sa.Column("risk_type", sa.String(32), nullable=False, server_default="none", comment="风险类型: none/income_drop/illness/housing/sudden/multiple"),
        sa.Column("risk_level", sa.String(10), nullable=False, server_default="low", comment="风险等级: low/medium/high"),
        sa.Column("helper_name", sa.String(64), nullable=True, comment="帮扶责任人"),
        sa.Column("helper_phone", sa.String(255), nullable=True, comment="帮扶责任人电话(透明加密)"),
        sa.Column("annual_income", sa.Numeric(14, 2), nullable=True, comment="家庭年收入(元)"),
        sa.Column("migrant_workers", sa.Integer(), nullable=True, comment="务工人数"),
        sa.Column("has_serious_illness", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否存在大病"),
        sa.Column("housing_safe", sa.Boolean(), nullable=False, server_default=sa.true(), comment="住房是否安全"),
        sa.Column("last_visit_date", sa.Date(), nullable=True, comment="最近走访日期"),
        sa.Column("monitoring_note", sa.Text(), nullable=True, comment="监测说明"),
        *_audit_columns(),
    )
    op.create_index("ix_households_village_id", "households", ["supported_village_id"], if_not_exists=True) if _table_exists("households") else None
    if _table_exists("households") and not any(
        ix["name"] == "ix_households_village_id" for ix in sa.inspect(bind).get_indexes("households")
    ):
        op.create_index("ix_households_village_id", "households", ["supported_village_id"])
    if _table_exists("households") and not any(
        ix["name"] == "ix_households_risk_level" for ix in sa.inspect(bind).get_indexes("households")
    ):
        op.create_index("ix_households_risk_level", "households", ["risk_level"])
    if _table_exists("households") and not any(
        ix["name"] == "ix_households_type" for ix in sa.inspect(bind).get_indexes("households")
    ):
        op.create_index("ix_households_type", "households", ["household_type"])

    # ── 2. household_members（家庭成员）──
    _create_table_if_absent(
        "household_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False, comment="所属户ID"),
        sa.Column("name", sa.String(64), nullable=False, comment="姓名"),
        sa.Column("relation", sa.String(32), nullable=True, comment="与户主关系"),
        sa.Column("id_card", sa.String(255), nullable=True, comment="身份证号(透明加密)"),
        sa.Column("gender", sa.String(10), nullable=True, comment="性别"),
        sa.Column("birth_year", sa.Integer(), nullable=True, comment="出生年份"),
        sa.Column("education", sa.String(32), nullable=True, comment="文化程度"),
        sa.Column("health_status", sa.String(32), nullable=True, comment="健康状况"),
        sa.Column("employment_status", sa.String(32), nullable=True, comment="就业状态"),
        sa.Column("income", sa.Numeric(14, 2), nullable=True, comment="个人年收入(元)"),
        sa.Column("is_special_support", sa.Boolean(), nullable=False, server_default=sa.false(), comment="是否兜底保障对象"),
        sa.Column("remarks", sa.String(500), nullable=True, comment="备注"),
        *_audit_columns(),
    )
    if _table_exists("household_members") and not any(
        ix["name"] == "ix_household_members_household_id" for ix in sa.inspect(bind).get_indexes("household_members")
    ):
        op.create_index("ix_household_members_household_id", "household_members", ["household_id"])

    # ── 3. household_risk_records（风险/预警记录）──
    _create_table_if_absent(
        "household_risk_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False, comment="所属户ID"),
        sa.Column("risk_type", sa.String(32), nullable=False, comment="风险类型"),
        sa.Column("risk_level", sa.String(10), nullable=False, server_default="medium", comment="风险等级"),
        sa.Column("reason", sa.String(500), nullable=True, comment="风险原因"),
        sa.Column("detected_at", sa.DateTime(), nullable=False, comment="发现时间"),
        sa.Column("status", sa.String(10), nullable=False, server_default="open", comment="状态: open/closed"),
        sa.Column("closed_at", sa.DateTime(), nullable=True, comment="关闭时间"),
        sa.Column("closed_note", sa.String(500), nullable=True, comment="关闭说明"),
        *_audit_columns(),
    )
    if _table_exists("household_risk_records") and not any(
        ix["name"] == "ix_household_risk_records_household_id" for ix in sa.inspect(bind).get_indexes("household_risk_records")
    ):
        op.create_index(
            "ix_household_risk_records_household_id", "household_risk_records", ["household_id"]
        )

    # ── 4. photo_archives（影像库）──
    _create_table_if_absent(
        "photo_archives",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("file_url", sa.String(500), nullable=False, comment="文件访问URL"),
        sa.Column("file_name", sa.String(255), nullable=True, comment="原始文件名"),
        sa.Column("file_size", sa.Integer(), nullable=True, comment="文件大小(字节)"),
        sa.Column("mime_type", sa.String(100), nullable=True, comment="MIME类型"),
        sa.Column("village_id", sa.Integer(), sa.ForeignKey("supported_villages.id", ondelete="SET NULL"), nullable=True, comment="所属帮扶村"),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True, comment="所属学校"),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, comment="所属项目"),
        sa.Column("tag", sa.String(50), nullable=True, comment="标签"),
        sa.Column("spot_key", sa.String(100), nullable=True, comment="拍摄点标识(多期对比)"),
        sa.Column("taken_at", sa.DateTime(), nullable=True, comment="拍摄时间(优先EXIF)"),
        sa.Column("gps_lat", sa.Numeric(10, 6), nullable=True, comment="GPS纬度"),
        sa.Column("gps_lng", sa.Numeric(10, 6), nullable=True, comment="GPS经度"),
        sa.Column("uploader_id", sa.Integer(), nullable=True, comment="上传者ID"),
        sa.Column("shot_source", sa.String(20), nullable=False, server_default="manual", comment="时间来源: exif/manual"),
        *_audit_columns(),
    )
    if _table_exists("photo_archives"):
        _insp = sa.inspect(bind)
        _idx = {ix["name"] for ix in _insp.get_indexes("photo_archives")}
        for _name, _cols in (
            ("ix_photo_archives_village_id", ["village_id"]),
            ("ix_photo_archives_spot_key", ["spot_key"]),
            ("ix_photo_archives_taken_at", ["taken_at"]),
        ):
            if _name not in _idx:
                op.create_index(_name, "photo_archives", _cols)

    # ── 5. consumption_records（消费帮扶）──
    _create_table_if_absent(
        "consumption_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("supported_village_id", sa.Integer(), sa.ForeignKey("supported_villages.id", ondelete="SET NULL"), nullable=True, comment="所属帮扶村"),
        sa.Column("category", sa.String(32), nullable=False, server_default="agriculture", comment="品类: agriculture/livestock/handicraft/other"),
        sa.Column("item_name", sa.String(200), nullable=False, comment="采购品名"),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=True, comment="数量"),
        sa.Column("unit", sa.String(20), nullable=True, comment="单位"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, comment="金额(元)"),
        sa.Column("buyer", sa.String(200), nullable=True, comment="采购方"),
        sa.Column("seller", sa.String(200), nullable=True, comment="供货方"),
        sa.Column("seller_type", sa.String(20), nullable=True, comment="供货方类型: farmer/cooperative/enterprise"),
        sa.Column("year", sa.Integer(), nullable=False, comment="年度"),
        sa.Column("record_date", sa.Date(), nullable=True, comment="发生日期"),
        sa.Column("voucher_url", sa.String(500), nullable=True, comment="凭证URL"),
        sa.Column("remarks", sa.Text(), nullable=True, comment="备注"),
        *_audit_columns(),
    )
    if _table_exists("consumption_records"):
        _insp = sa.inspect(bind)
        _idx = {ix["name"] for ix in _insp.get_indexes("consumption_records")}
        for _name, _cols in (
            ("ix_consumption_records_village_id", ["supported_village_id"]),
            ("ix_consumption_records_year", ["year"]),
            ("ix_consumption_records_category", ["category"]),
        ):
            if _name not in _idx:
                op.create_index(_name, "consumption_records", _cols)

    # ── 6. 走访记录挂户 ──
    if _table_exists("visit_records") and not _has_column("visit_records", "household_id"):
        with op.batch_alter_table("visit_records") as batch:
            batch.add_column(
                sa.Column(
                    "household_id",
                    sa.Integer(),
                    sa.ForeignKey(
                        "households.id",
                        ondelete="SET NULL",
                        name="fk_visit_records_household_id",
                    ),
                    nullable=True,
                    comment="关联一户一档ID",
                )
            )

    # ── 7. 四张表 village_id → supported_village_id（先回填后删旧列）──
    _migrate_village_columns(bind)

    # ── 8. 删除遗留表（先子后父；存在才删）──
    for _table in ("sentiment_news", "villagers", "industries", "villages"):
        if _table_exists(_table):
            op.drop_table(_table)


def _drop_indexes_for_column(bind, table: str, column: str) -> None:
    """删除以该列为键的索引（batch 重建表前必须，否则旧索引重建时列已不存在 → 报错）。"""
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return
    for ix in insp.get_indexes(table):
        cols = ix.get("column_names") or []
        if column in cols:
            op.drop_index(ix["name"], table_name=table)


def _migrate_village_columns(bind) -> None:
    """rural_works / rural_tasks / tea_plantations / cactus_fruit_plots：加新列、回填、删旧列。"""
    tables = ("rural_works", "rural_tasks", "tea_plantations", "cactus_fruit_plots")
    villages_exists = _table_exists("villages")
    for table in tables:
        if not _table_exists(table):
            continue
        if not _has_column(table, "supported_village_id"):
            with op.batch_alter_table(table) as batch:
                batch.add_column(
                    sa.Column(
                        "supported_village_id",
                        sa.Integer(),
                        sa.ForeignKey(
                            "supported_villages.id",
                            ondelete="SET NULL",
                            name=f"fk_{table}_supported_village_id",
                        ),
                        nullable=True,
                        comment="帮扶村ID（原 villages.id 迁移）",
                    )
                )
        if villages_exists and _has_column(table, "village_id"):
            bind.execute(
                sa.text(
                    f"""
                    UPDATE {table}
                       SET supported_village_id = (
                           SELECT MIN(sv.id)
                             FROM supported_villages sv
                             JOIN villages v ON v.name = sv.village_name
                            WHERE v.id = {table}.village_id
                              AND (
                                  sv.organization_id = v.organization_id
                                  OR sv.organization_id IS NULL
                                  OR v.organization_id IS NULL
                              )
                       )
                     WHERE village_id IS NOT NULL
                       AND supported_village_id IS NULL
                    """
                )
            )
        if _has_column(table, "village_id"):
            _drop_indexes_for_column(bind, table, "village_id")
            with op.batch_alter_table(table) as batch:
                batch.drop_column("village_id")


def downgrade() -> None:
    """回退：删除新表/新列，恢复旧列与遗留表（结构级回退；不恢复已删数据）。"""
    bind = op.get_bind()

    # 恢复遗留表（最小结构，保证旧代码可启动；数据不可恢复）
    _create_table_if_absent(
        "villages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("province", sa.String(50), nullable=True),
        sa.Column("city", sa.String(50), nullable=True),
        sa.Column("county", sa.String(50), nullable=True),
        sa.Column("township", sa.String(100), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    _create_table_if_absent(
        "villagers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("village_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    _create_table_if_absent(
        "industries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("village_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    _create_table_if_absent(
        "sentiment_news",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 恢复四张表的 village_id 列（可空）
    for table in ("rural_works", "rural_tasks", "tea_plantations", "cactus_fruit_plots"):
        if _table_exists(table) and not _has_column(table, "village_id"):
            with op.batch_alter_table(table) as batch:
                batch.add_column(
                    sa.Column(
                        "village_id",
                        sa.Integer(),
                        sa.ForeignKey(
                            "villages.id",
                            ondelete="CASCADE",
                            name=f"fk_{table}_village_id",
                        ),
                        nullable=True,
                    )
                )
        if _table_exists(table) and _has_column(table, "supported_village_id"):
            _drop_indexes_for_column(bind, table, "supported_village_id")
            with op.batch_alter_table(table) as batch:
                batch.drop_column("supported_village_id")

    # 删除新表
    if _has_column("visit_records", "household_id"):
        with op.batch_alter_table("visit_records") as batch:
            batch.drop_column("household_id")
    for _table in ("consumption_records", "photo_archives", "household_risk_records", "household_members", "households"):
        if _table_exists(_table):
            op.drop_table(_table)
