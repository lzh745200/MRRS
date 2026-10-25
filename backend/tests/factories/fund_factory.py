"""Fund model factories."""

from datetime import datetime, timezone

from app.models.fund import Fund, FundAttachment, BudgetRecord
from decimal import Decimal


class FundFactory:
    @staticmethod
    def build(**kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            name="测试资金",
            type="项目资金",
            fund_type="project",
            fund_source="military",
            amount=Decimal("100000.00"),
            planned_amount=Decimal("100000.00"),
            allocated_amount=Decimal("0"),
            used_amount=Decimal("0"),
            remaining_amount=Decimal("100000.00"),
            status="pending",
            purpose="乡村振兴项目",
            operator="测试人",
            lifecycle_phase=1,
            budget_locked=False,
            deviation_rate=Decimal("0"),
            health_score=100,
            has_anomaly=False,
            budget_version=1,
            created_at=now,
            updated_at=now,
        )
        data.update(kwargs)
        return Fund(**data)

    @staticmethod
    def create(db, **kwargs):
        obj = FundFactory.build(**kwargs)
        db.add(obj)
        db.flush()
        return obj

    @staticmethod
    def build_allocated(**kwargs):
        kwargs.setdefault("status", "allocated")
        kwargs.setdefault("allocated_amount", Decimal("100000.00"))
        kwargs.setdefault("remaining_amount", Decimal("100000.00"))
        return FundFactory.build(**kwargs)

    @staticmethod
    def build_in_use(**kwargs):
        kwargs.setdefault("status", "in_use")
        kwargs.setdefault("allocated_amount", Decimal("100000.00"))
        kwargs.setdefault("used_amount", Decimal("30000.00"))
        kwargs.setdefault("remaining_amount", Decimal("70000.00"))
        return FundFactory.build(**kwargs)

    @staticmethod
    def build_completed(**kwargs):
        kwargs.setdefault("status", "completed")
        kwargs.setdefault("allocated_amount", Decimal("100000.00"))
        kwargs.setdefault("used_amount", Decimal("100000.00"))
        kwargs.setdefault("remaining_amount", Decimal("0"))
        kwargs.setdefault("settlement_status", "settled")
        return FundFactory.build(**kwargs)

    @staticmethod
    def build_anomaly(**kwargs):
        kwargs.setdefault("has_anomaly", True)
        kwargs.setdefault("health_score", 40)
        kwargs.setdefault("deviation_rate", Decimal("35.00"))
        return FundFactory.build(**kwargs)


class FundAttachmentFactory:
    @staticmethod
    def build(fund_id=1, **kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            fund_id=fund_id,
            file_name="凭证.pdf",
            file_path="/uploads/funds/test.pdf",
            file_size=2048,
            file_type="pdf",
            category="voucher",
            uploaded_by=1,
            created_at=now,
        )
        data.update(kwargs)
        return FundAttachment(**data)

    @staticmethod
    def create(db, fund_id=1, **kwargs):
        obj = FundAttachmentFactory.build(fund_id=fund_id, **kwargs)
        db.add(obj)
        db.flush()
        return obj


class BudgetRecordFactory:
    @staticmethod
    def build(**kwargs):
        now = datetime.now(timezone.utc)
        data = dict(
            year=2024,
            category="项目资金",
            budget_amount=Decimal("500000.00"),
            used_amount=Decimal("200000.00"),
            created_at=now,
            updated_at=now,
        )
        data.update(kwargs)
        return BudgetRecord(**data)

    @staticmethod
    def create(db, **kwargs):
        obj = BudgetRecordFactory.build(**kwargs)
        db.add(obj)
        db.flush()
        return obj
