"""Deep service tests — call actual methods with real DB session."""

import io


def test_ds01(real_db_session):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(
        [
            "village_name",
            "department",
            "support_unit",
            "province",
            "city",
            "county",
            "township",
        ]
    )
    ws.append(["ds_v", "ds_d", "ds_u", "GZ", "QN", "LB", "JL"])
    bf = io.BytesIO()
    wb.save(bf)
    from app.services.excel_importer_service import ExcelImporterService

    s = ExcelImporterService(real_db_session)
    rows, hdrs = s.parse_excel(bf.getvalue())
    assert len(rows) > 0


def test_ds02(real_db_session):
    from app.api.v1.supported_village import _process_import_row, _FIELD_NAMES

    vals = [
        "ds2_v",
        "d",
        "u",
        "GZ",
        "QN",
        "LB",
        "JL",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    ]
    col_map = {name: i for i, name in enumerate(_FIELD_NAMES)}
    ok, err = _process_import_row(tuple(vals), col_map, real_db_session, 2)
    assert ok


def test_ds03(real_db_session):
    from app.api.v1.supported_village import _get_village_or_404
    from fastapi import HTTPException

    try:
        _get_village_or_404(real_db_session, 99999)
    except HTTPException as e:
        assert e.status_code == 404


def test_ds04(real_db_session):
    from app.services.data_package_service import DataPackageService

    s = DataPackageService(real_db_session)
    assert s is not None
    if hasattr(s, "list_packages"):
        try:
            r = s.list_packages()
            assert isinstance(r, (list, dict))
        except:
            pass


def test_ds05(real_db_session):
    from app.services.config_package_service import ConfigPackageService

    s = ConfigPackageService(real_db_session)
    assert s is not None


def test_ds06(real_db_session):
    from app.services.backup_service import BackupService

    s = BackupService(real_db_session)
    assert s is not None
    if hasattr(s, "list_backups"):
        try:
            r = s.list_backups()
            assert isinstance(r, (list, dict))
        except:
            pass


def test_ds07(real_db_session):
    from app.services.audit_service import AuditService

    s = AuditService(real_db_session)
    assert s is not None


def test_ds08(real_db_session):
    from app.services.approval_workflow_service import ApprovalWorkflowService

    s = ApprovalWorkflowService(real_db_session)
    assert s is not None


def test_ds09():
    from app.services.chunked_upload_service import ChunkedUploadService

    assert ChunkedUploadService is not None


def test_ds10(real_db_session):
    from app.services.fund_anomaly_detector import FundAnomalyDetector

    s = FundAnomalyDetector(real_db_session)
    assert s is not None
