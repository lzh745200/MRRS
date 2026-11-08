"""数据包必须真正支持前端已暴露的“乡村工作”类型。

历史缺陷：ReportPackage.vue 提供 rural_works 复选框，但后端
DATA_TYPE_MODELS / RECORD_MODELS 均未注册，勾选后既不导出也不校验，
接口仍返回成功，属于静默丢数据。
"""
from unittest.mock import MagicMock

from app.models.rural_work import RuralWork
from app.services.data_package_service import (
    BUSINESS_KEYS,
    DATA_TYPE_MODELS,
    _business_key_of,
)
from app.services.package_record_validator import RECORD_MODELS, validate_records


def test_rural_works_registered_in_both_mappings():
    assert DATA_TYPE_MODELS["rural_works"] is RuralWork
    assert RECORD_MODELS["rural_works"] is RuralWork
    assert BUSINESS_KEYS["rural_works"] == ("organization_id", "code")


def test_rural_work_business_key():
    assert _business_key_of(
        RuralWork, {"organization_id": 3, "code": "RW-001"}
    ) == (3, "RW-001")
    # code 为空时不可判定，按“不同记录”保守处理
    assert _business_key_of(RuralWork, {"organization_id": 3, "code": ""}) is None


def test_rural_work_record_validation():
    result = validate_records(
        "rural_works",
        [
            {
                "name": "村道硬化",
                "type": "infrastructure",
                "status": "planned",
                "progress": 10,
            }
        ],
    )
    assert len(result["ok"]) == 1
    assert not result["rejected"]


def test_rural_work_export_iterates_org_scoped_table():
    from app.services.data_package_service import DataPackageService

    db = MagicMock()
    db.execute.return_value = []
    service = DataPackageService(db, upload_dir="/tmp/mrrs-test-packages")
    assert list(service._iter_export_data_type(7, RuralWork)) == []
    sql = str(db.execute.call_args.args[0])
    assert "rural_works" in sql
    assert "organization_id" in sql
