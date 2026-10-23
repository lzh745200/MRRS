"""b3 攻坚：覆盖 app.models.base 的 soft_delete(deleted_by) 与 to_dict datetime 分支"""
from datetime import datetime, timezone

from app.models.base import SoftDeleteMixin


class TestSoftDeleteWithOperator:
    def test_soft_delete_with_deleted_by(self):
        obj = SoftDeleteMixin.__new__(SoftDeleteMixin)
        obj.is_deleted = False
        obj.deleted_at = None
        obj.deleted_by = None
        obj.soft_delete(deleted_by=99)
        assert obj.is_deleted is True
        assert obj.deleted_at is not None
        assert obj.deleted_by == 99

    def test_soft_delete_without_deleted_by(self):
        obj = SoftDeleteMixin.__new__(SoftDeleteMixin)
        obj.is_deleted = False
        obj.deleted_at = None
        obj.deleted_by = None
        obj.soft_delete()
        assert obj.deleted_by is None


class TestBaseModelToDictDatetime:
    def test_to_dict_isoformat_for_datetime(self):
        from app.models.annual_population import AnnualPopulation as _IncomeModel

        income = _IncomeModel()
        income.id = 1
        income.created_at = datetime(2024, 5, 6, 7, 8, 9, tzinfo=timezone.utc)
        income.updated_at = None
        d = income.to_dict()
        assert d["createdAt"] == "2024-05-06T07:08:09+00:00"
        assert d["updatedAt"] is None

    def test_to_dict_snake_case(self):
        from app.models.annual_population import AnnualPopulation as _IncomeModel

        income = _IncomeModel()
        income.id = 2
        d = income.to_dict(camel_case=False)
        assert "created_at" in d
