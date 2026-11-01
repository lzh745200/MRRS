"""长期项（2026-11-01）：数据包两阶段导入的第一阶段 —— 只读演练。

背景：原流程只有「预览前 5 条」与「直接 confirm」两档。confirm 是 savepoint +
独占写锁的原子提交，一旦用户点下去就写库；包内主键与本地撞号时到底会新增多少、
覆盖多少、拒绝多少，用户在点之前看不到。本文件锁定 ``dry_run_import`` 的契约：

* 与 confirm 读同一个包、同一套 ``validate_records``；
* **绝不写库**（不 add/execute/flush/commit，也不改 package.status）；
* 覆盖开关只影响「将覆盖」计数，不影响「将新增」；
* 非法状态 / 包不存在 → BusinessError；未知 data_type 静默跳过。
"""

import json
import zipfile
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import BusinessError
from app.models.data_package import DataPackage, PackageStatus
from app.services.data_package_service import DataPackageService


def _build_zip(tmp_path, data_types, records_by_type):
    path = tmp_path / "package.zip"
    manifest = {
        "version": "1.0",
        "data_types": data_types,
        "org_code": "520000",
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        for data_type, records in records_by_type.items():
            zf.writestr(f"data/{data_type}.json", json.dumps(records))
    return str(path)


def _service_with_package(file_path, status=None, existing=0, package_exists=True):
    package = MagicMock()
    package.id = 7
    package.package_code = "PKG-7"
    package.status = status if status is not None else PackageStatus.validated.value
    package.file_path = file_path

    db = MagicMock()

    def _query(model):
        query = MagicMock()
        if model is DataPackage:
            query.filter.return_value.first.return_value = package if package_exists else None
        else:
            query.filter.return_value.count.return_value = existing
        return query

    db.query.side_effect = _query
    return DataPackageService(db), db


def test_dry_run_counts_create_and_rejected_without_writes(tmp_path):
    file_path = _build_zip(
        tmp_path,
        ["villages"],
        {"villages": [
            {"id": 1, "village_name": "甲村"},
            {"id": 2},                       # 缺必填 → rejected
            {"village_name": "新乙村"},       # 无 id → 必新增
        ]},
    )
    existing = 1  # 本地已有 id=1
    service, db = _service_with_package(file_path, existing=existing)

    report = service.dry_run_import(7, overwrite_existing=False)

    assert report["success"] is True
    assert report["package_id"] == 7
    assert report["total_records"] == 3
    assert report["total_rejected"] == 1
    assert report["total_to_create"] == 1, "accepted(2) - existing(1)"
    assert report["total_to_update"] == 0, "未开覆盖：撞号记录只会被跳过"
    village_report = report["types"][0]
    assert village_report["data_type"] == "villages"
    assert village_report["accepted"] == 2
    assert village_report["existing"] == 1
    assert village_report["id_samples"] == [1]
    assert report["rejected"][0]["row"] == 2

    # 绝不写库：演练只读
    db.add.assert_not_called()
    db.execute.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_dry_run_overwrite_turns_existing_into_updates(tmp_path):
    file_path = _build_zip(
        tmp_path,
        ["villages"],
        {"villages": [{"id": 1, "village_name": "甲村"}]},
    )
    service, _db = _service_with_package(file_path, existing=1)

    report = service.dry_run_import(7, overwrite_existing=True)

    assert report["total_to_create"] == 0
    assert report["total_to_update"] == 1
    assert report["total_rejected"] == 0


def test_dry_run_skips_unknown_data_type_and_missing_file(tmp_path):
    file_path = _build_zip(
        tmp_path,
        ["unknown_type", "schools"],
        {"schools": [{"id": 5, "name": "希望小学"}]},
    )
    service, _db = _service_with_package(file_path)

    report = service.dry_run_import(7)

    assert [row["data_type"] for row in report["types"]] == ["schools"]
    assert report["total_records"] == 1


def test_dry_run_honours_selected_types(tmp_path):
    file_path = _build_zip(
        tmp_path,
        ["villages", "schools"],
        {
            "villages": [{"id": 1, "village_name": "甲村"}],
            "schools": [{"id": 5, "name": "希望小学"}],
        },
    )
    service, _db = _service_with_package(file_path)

    report = service.dry_run_import(7, selected_types=["schools"])

    assert [row["data_type"] for row in report["types"]] == ["schools"]
    assert report["total_records"] == 1


def test_dry_run_rejects_package_not_validated(tmp_path):
    file_path = _build_zip(tmp_path, ["villages"], {"villages": []})
    service, _db = _service_with_package(file_path, status="draft")

    with pytest.raises(BusinessError) as exc:
        service.dry_run_import(7)

    assert "不允许演练" in str(exc.value)


def test_dry_run_rejects_missing_package():
    service, _db = _service_with_package("/tmp/none.zip", package_exists=False)

    with pytest.raises(BusinessError) as exc:
        service.dry_run_import(7)

    assert "数据包不存在" in str(exc.value)


# ── 长期项 4（故障注入）：演练/确认在坏包与中途异常下必须可预测 ──


def test_dry_run_corrupted_zip_raises_bad_zip(tmp_path):
    """坏包在演练阶段就要炸，而不是等到 confirm 写库时才失败。"""
    bad = tmp_path / "broken.zip"
    bad.write_bytes(b"this is not a zip file")
    svc, _db = _service_with_package(str(bad))

    with pytest.raises(zipfile.BadZipFile):
        svc.dry_run_import(7)


def test_confirm_rolls_back_and_counts_failure_on_midway_error(tmp_path, monkeypatch):
    """confirm 中途异常：回滚、包标记 failed、失败计数 +1（故障注入用例）。"""
    from app.core import business_metrics

    path = _build_zip(tmp_path, ["villages"], {"villages": []})
    svc, db = _service_with_package(path)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("注入的中途失败")

    monkeypatch.setattr("app.services.data_package_service.read_zip_member", _boom)
    business_metrics.reset()
    try:
        result = svc._confirm_import_sync(package_id=7, confirmed_by=1)
    finally:
        db.rollback.assert_called()
        snapshot = business_metrics.snapshot()
        assert snapshot.get("data_package.import_failed") == 1
        assert snapshot.get("data_package.import") is None
        business_metrics.reset()

    assert result.success is False
    assert result.errors and result.errors[0].message == "注入的中途失败"

def test_dry_run_skips_declared_type_without_data_file(tmp_path):
    """manifest 声明了类型但包内缺 data/<type>.json：跳过，不报错也不写库。"""
    path = tmp_path / "package.zip"
    manifest = {"version": "1.0", "data_types": ["villages"], "org_code": "520000"}
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))

    service, db = _service_with_package(str(path))
    report = service.dry_run_import(7)

    assert report["success"] is True
    assert report["total_records"] == 0
    assert report["types"] == []
    db.add.assert_not_called()


def test_dry_run_without_int_primary_keys_skips_existence_query(tmp_path):
    """accepted 记录都没有 int 主键时不查库（existing 恒 0），避免 IN 空集查询。"""
    file_path = _build_zip(
        tmp_path,
        ["villages"],
        {"villages": [{"village_name": "无编号村"}]},
    )
    service, db = _service_with_package(file_path, existing=99)

    report = service.dry_run_import(7)

    assert report["success"] is True
    assert report["total_records"] == 1
    village_report = report["types"][0]
    assert village_report["existing"] == 0, "无 int 主键时不得把桩返回的 99 当已存在"
    assert village_report["to_create"] == 1
    db.add.assert_not_called()
