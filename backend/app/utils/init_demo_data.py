# -*- coding: utf-8 -*-
"""
演示数据初始化脚本（字段与模型对齐）
用法: python -m app.utils.init_demo_data [--db PATH]
"""
import argparse
import logging
import random
from datetime import date, datetime

logger = logging.getLogger("init_demo_data")

from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.transaction import safe_commit  # noqa: E402
from app.models.base import Base  # noqa: E402


def seed(db: Session) -> None:
    from app.models.supported_village import (  # noqa: F401
        SupportedVillage, VillageIncome, VillagePopulation, ForceInvestment,
        IndustrySupport, InfrastructureImprovement, ConsumptionSupport,
    )
    from app.models.project import Project
    from app.models.fund import Fund
    from app.models.fund_budget import FundBudget
    from app.models.fund_lifecycle import FundContract
    from app.models.policy import Policy
    from app.models.rural_work import RuralWork
    from app.models.approval import ApprovalTask, ApprovalWorkflow, ApprovalStatus, ApprovalRecord
    from app.models.organization import Organization

    if db.query(SupportedVillage).count() > 0:
        logger.info("帮扶村已存在，跳过演示数据初始化")
        return

    org = db.query(Organization).first()
    org_id = org.id if org else None

    # ── 帮扶村（6 个）──
    villages = []
    names = ["幸福村", "振兴村", "希望村", "前进村", "丰饶村", "同心村"]
    for i, name in enumerate(names, start=1):
        v = SupportedVillage(
            village_name=name,
            province="贵州省",
            city="黔南布依族苗族自治州",
            county="长顺县",
            township=f"示范镇{i}",
            department="省军区帮扶办",
            support_unit=f"某旅{i}",
            region_scope=random.choice(["示范点", "重点帮扶"]),
            is_three_regions=(i % 2 == 1),
            is_revitalization_tier=(i % 3 == 0),
            is_key_county=(i % 2 == 1),
            is_active=True,
            created_by=1,
            organization_id=org_id,
        )
        db.add(v)
        villages.append(v)
    db.flush()

    # 年度数据（2021-2025）
    for v in villages:
        for y in range(2021, 2026):
            db.add(VillagePopulation(
                supported_village_id=v.id, year=y,
                total_households=random.randint(150, 600),
                total_population=random.randint(800, 3000),
                resident_population=random.randint(600, 2500),
                labor_force=random.randint(300, 1200),
                poverty_population=max(0, 200 - (y - 2020) * 30),
            ))
            db.add(VillageIncome(
                supported_village_id=v.id, year=y,
                per_capita_income=9000 + (y - 2020) * 800 + random.randint(0, 300),
                collective_income=random.randint(5, 30),
            ))
        db.add(ForceInvestment(
            supported_village_id=v.id, year=2026,
            senior_leader_visits=random.randint(2, 8),
            unit_soldier_visits=random.randint(10, 40),
        ))
        db.add(IndustrySupport(
            supported_village_id=v.id, year=2026,
            investment=random.randint(30, 120), planned_investment=random.randint(40, 150),
            planting_breeding=random.randint(20, 80), rural_tourism=random.randint(5, 40),
        ))
        db.add(InfrastructureImprovement(
            supported_village_id=v.id, year=2026,
            investment=random.randint(20, 80), road_km=random.randint(1, 5),
            water_facilities=random.randint(1, 4), cultural_plaza=random.randint(0, 2),
        ))
        db.add(ConsumptionSupport(
            supported_village_id=v.id, year=2026,
            village_products_purchase=random.randint(10, 60),
            other_products_purchase=random.randint(5, 30),
            sales_counters=random.randint(1, 3),
            benefited_population=random.randint(50, 300),
        ))
    db.flush()

    # ── 项目（6 个）──
    projects = []
    for i, v in enumerate(villages, start=1):
        p = Project(
            name=f"{v.village_name}产业帮扶项目{i}",
            code=f"PRJ-2026-{i:03d}",
            village_id=v.id,
            status="in_progress" if i % 2 else "completed",
            start_date=date(2026, 3, i),
            end_date=date(2026, 12, 15),
            budget=random.randint(50, 300),
            progress=random.randint(20, 100),
            leader="张主任",
            responsible_person="李干事",
            description=f"{v.village_name}特色产业帮扶示范项目",
            is_active=True,
            created_by=1,
            organization_id=org_id,
        )
        db.add(p)
        projects.append(p)
    db.flush()

    # ── 经费（12 条）──
    for i in range(1, 13):
        p = projects[(i - 1) % len(projects)]
        f = Fund(
            name=f"{p.name}经费-{i}",
            fund_type=random.choice(["project", "operation", "education"]),
            fund_source=random.choice(["中央财政", "省级配套", "社会帮扶"]),
            amount=random.randint(10, 200),
            status=random.choice(["approved", "allocated", "in_use", "completed"]),
            project_id=p.id,
            village_id=p.village_id,
            year=2026,
            used_amount=random.randint(5, 80),
            allocated_amount=random.randint(10, 150),
            is_active=True,
            created_by=1,
        )
        f.remaining_amount = f.allocated_amount - f.used_amount
        db.add(f)
    db.flush()

    # ── 预算（5 类）──
    for cat in ["产业帮扶", "基础设施", "教育帮扶", "医疗帮扶", "消费帮扶"]:
        db.add(FundBudget(year=2026, category=cat, budget_amount=random.randint(50, 300),
                          executed_amount=random.randint(20, 200), created_by=1))
    db.flush()

    # ── 合同（6 个）──
    for i, p in enumerate(projects, start=1):
        db.add(FundContract(
            contract_no=f"HT-2026-{i:03d}",
            contract_name=f"{p.name}实施合同",
            party_a="某旅",
            party_b=f"{p.name}施工方",
            contract_amount=random.randint(30, 200),
            paid_amount=random.randint(10, 100),
            project_id=p.id,
            status=random.choice(["draft", "active", "completed"]),
            created_by="admin",
        ))
    db.flush()

    # ── 政策（6 条）──
    for i in range(1, 7):
        db.add(Policy(
            title=f"乡村振兴帮扶政策文件（2026 第{i}号）",
            code=f"政发〔2026〕{i}号",
            category="local",
            level="provincial",
            status="active",
            issuing_authority="省乡村振兴局",
            issue_date=datetime(2026, 1, i + 5),
            effective_date=datetime(2026, 2, 1),
            content=f"关于深入推进{i}号工程帮扶工作的实施意见…",
            summary="本文件明确了帮扶工作的总体要求与重点任务。",
            keywords="帮扶,乡村振兴,产业",
            is_active=True,
            created_by=1,
        ))
    db.flush()

    # ── 乡村工作（8 条，village_id 关联 villages 表）──
    from app.models.village import Village as LegacyVillage

    legacy_villages = []
    for v in villages:
        lv = LegacyVillage(
            name=v.village_name,
            province=v.province,
            county=v.county,
            township=v.township,
            status="active",
            is_active=True,
            description=v.region_scope,
        )
        db.add(lv)
        legacy_villages.append(lv)
    db.flush()

    for i, v in enumerate(villages, start=1):
        db.add(RuralWork(
            name=f"{v.village_name}帮扶工作{i}",
            type=random.choice(["industry", "education", "healthcare", "infrastructure"]),
            status=random.choice(["pending", "in_progress", "completed"]),
            start_date=date(2026, 4, i),
            end_date=date(2026, 11, 20),
            village_id=legacy_villages[i - 1].id,
            progress=random.randint(20, 100),
            responsible_person="张主任",
            description=f"{v.village_name}年度帮扶任务",
            created_by=1,
        ))
    db.flush()

    # ── 审批工作流与任务 ──
    from app.models.approval import ApprovalNode

    wf = ApprovalWorkflow(
        name="政策发布审批", entity_type="policy",
        description="政策发布前需审批", is_active=True, created_by=1,
    )
    db.add(wf)
    db.flush()
    db.add(ApprovalNode(workflow_id=wf.id, level=1, name="初审", approver_type="admin", timeout_hours=72))
    db.flush()
    for i in range(1, 5):
        db.add(ApprovalTask(
            workflow_id=wf.id, entity_type="policy", entity_id=i,
            title=f"政策发布审批-第{i}条", status=ApprovalStatus.PENDING,
            current_level=1, submitter_id=1,
        ))
    db.flush()
    for i in range(1, 4):
        db.add(ApprovalRecord(
            task_id=i, level=1, approver_id=1,
            action="submit", opinion="提交审批",
        ))
    db.flush()

    safe_commit(db)
    logger.info("演示数据初始化完成：6村/6项目/12经费/5预算/6合同/6政策/8乡村工作/4审批任务")


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化演示数据")
    parser.add_argument("--db", default=None, help="数据库文件路径")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.db:
        import os
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine_local = create_engine(f"sqlite:///{os.path.abspath(args.db)}")
        Base.metadata.create_all(bind=engine_local)
        SessionLocal_local = sessionmaker(bind=engine_local)
        db = SessionLocal_local()
        try:
            seed(db)
        finally:
            db.close()
    else:
        db = SessionLocal()
        try:
            seed(db)
        finally:
            db.close()


if __name__ == "__main__":
    main()
