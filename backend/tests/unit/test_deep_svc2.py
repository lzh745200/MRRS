import io


def test_v01(real_db_session):
    from app.services.data_package_service import DataPackageService

    s = DataPackageService(real_db_session)
    assert s is not None


def test_v02(real_db_session):
    from app.services.config_package_service import ConfigPackageService

    s = ConfigPackageService(real_db_session)
    assert s is not None


def test_v03(real_db_session):
    from app.services.backup_service import BackupService

    s = BackupService(real_db_session)
    assert s is not None


def test_v04(real_db_session):
    from app.services.audit_service import AuditService

    s = AuditService(real_db_session)
    assert s is not None


def test_v05(real_db_session):
    from app.services.message_service import MessageService

    s = MessageService(real_db_session)
    assert s is not None


def test_v06(real_db_session):
    from app.services.message_template_service import MessageTemplateService

    s = MessageTemplateService(real_db_session)
    assert s is not None


def test_v07(real_db_session):
    from app.services.notification_preference_service import (
        NotificationPreferenceService,
    )

    s = NotificationPreferenceService(real_db_session)
    assert s is not None


def test_v08(real_db_session):
    from app.services.organization_service import OrganizationService

    s = OrganizationService(real_db_session)
    assert s is not None


def test_v09(real_db_session):
    from app.services.policy_service import PolicyService

    s = PolicyService(real_db_session)
    assert s is not None


def test_v10(real_db_session):
    from app.services.user_service import UserService

    s = UserService(real_db_session)
    assert s is not None


def test_v11(real_db_session):
    from app.services.work_log_service import WorkLogService

    s = WorkLogService(real_db_session)
    assert s is not None


def test_v12(real_db_session):
    from app.services.update_log_service import UpdateLogService

    s = UpdateLogService(real_db_session)
    assert s is not None


def test_v13(real_db_session):
    from app.services.data_report_service import DataReportService

    s = DataReportService(real_db_session)
    assert s is not None


def test_v14(real_db_session):
    from app.services.fund_health_service import FundHealthService

    s = FundHealthService(real_db_session)
    assert s is not None


def test_v15(real_db_session):
    from app.services.user_permission_service import UserPermissionService

    s = UserPermissionService(real_db_session)
    assert s is not None


def test_v16(real_db_session):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["a", "b", "c", "d", "e", "f", "g"])
    ws.append(["v16", "x", "y", "GZ", "QN", "LB", "JL"])
    bf = io.BytesIO()
    wb.save(bf)
    from app.services.excel_importer_service import ExcelImporterService

    s = ExcelImporterService(real_db_session)
    rows, hdrs = s.parse_excel(bf.getvalue())
    assert len(rows) > 0


def test_v17(real_db_session):
    from app.api.v1.supported_village import _process_import_row, _FIELD_NAMES

    vals = [
        "v17",
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
