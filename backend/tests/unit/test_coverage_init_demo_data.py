# -*- coding: utf-8 -*-
"""
演示数据初始化测试（app/utils/init_demo_data.py）

覆盖 seed() 的实体创建 / 幂等 / 组织关联路径，以及 main() 的
--db 与无参数两条分支。使用真实内存 SQLite 会话，确保 seed() 内部的
flush()/query()/safe_commit() 链路可被真实执行（而非 mock 空转）。
"""
import sys
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.utils.init_demo_data import main, seed

# 显式导入 seed() 依赖的全部模型，确保 mapper 注册完整后再 create_all
from app.models.supported_village import (  # noqa: F401
    SupportedVillage,
    VillageIncome,
    VillagePopulation,
    ForceInvestment,
    IndustrySupport,
    InfrastructureImprovement,
    ConsumptionSupport,
)
from app.models.project import Project  # noqa: F401
from app.models.fund import Fund  # noqa: F401
from app.models.fund_budget import FundBudget  # noqa: F401
from app.models.fund_lifecycle import FundContract  # noqa: F401
from app.models.policy import Policy  # noqa: F401
from app.models.rural_work import RuralWork  # noqa: F401
from app.models.approval import (  # noqa: F401
    ApprovalTask,
    ApprovalWorkflow,
    ApprovalStatus,
    ApprovalRecord,
    ApprovalNode,
)
from app.models.organization import Organization  # noqa: F401
from app.models.village import Village  # noqa: F401
from app.models.base import Base


@pytest.fixture
def demo_db():
    """独立的内存 SQLite 会话（StaticPool 保证跨会话共享同一内存库）。"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_cls = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = session_cls()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
        engine.dispose()


class TestSeed:
    def test_seed_creates_all_entities(self, demo_db):
        seed(demo_db)

        assert demo_db.query(SupportedVillage).count() == 6
        assert demo_db.query(VillagePopulation).count() == 30
        assert demo_db.query(VillageIncome).count() == 30
        assert demo_db.query(ForceInvestment).count() == 6
        assert demo_db.query(IndustrySupport).count() == 6
        assert demo_db.query(InfrastructureImprovement).count() == 6
        assert demo_db.query(ConsumptionSupport).count() == 6
        assert demo_db.query(Project).count() == 6
        assert demo_db.query(Fund).count() == 12
        assert demo_db.query(FundBudget).count() == 5
        assert demo_db.query(FundContract).count() == 6
        assert demo_db.query(Policy).count() == 6
        assert demo_db.query(Village).count() == 6
        assert demo_db.query(RuralWork).count() == 6
        assert demo_db.query(ApprovalWorkflow).count() == 1
        assert demo_db.query(ApprovalNode).count() == 1
        assert demo_db.query(ApprovalTask).count() == 4
        assert demo_db.query(ApprovalRecord).count() == 3

    def test_seed_is_idempotent(self, demo_db):
        seed(demo_db)
        seed(demo_db)  # 第二次调用应命中「已存在」分支并提前返回

        assert demo_db.query(SupportedVillage).count() == 6
        assert demo_db.query(Project).count() == 6
        assert demo_db.query(Fund).count() == 12

    def test_seed_with_existing_organization(self, demo_db):
        org = Organization(name="测试组织", code="TEST-ORG")
        demo_db.add(org)
        demo_db.commit()
        demo_db.refresh(org)

        seed(demo_db)

        villages = demo_db.query(SupportedVillage).all()
        assert all(v.organization_id == org.id for v in villages)


class TestMain:
    def test_main_with_db_argument(self, tmp_path):
        db_path = tmp_path / "demo.db"

        with patch.object(sys, "argv", ["init_demo_data.py", "--db", str(db_path)]):
            main()

        assert db_path.exists()
        # 通过独立会话验证数据已落盘
        engine = create_engine(f"sqlite:///{db_path}")
        session_cls = sessionmaker(bind=engine)
        db = session_cls()
        try:
            assert db.query(SupportedVillage).count() == 6
        finally:
            db.close()
            engine.dispose()

    def test_main_without_db_argument(self, tmp_path):
        db_path = tmp_path / "demo2.db"
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(bind=engine)
        session_cls = sessionmaker(bind=engine)

        import app.utils.init_demo_data as idm

        with patch.object(idm, "SessionLocal", session_cls):
            with patch.object(sys, "argv", ["init_demo_data.py"]):
                main()

        db = session_cls()
        try:
            assert db.query(SupportedVillage).count() == 6
        finally:
            db.close()
            engine.dispose()
