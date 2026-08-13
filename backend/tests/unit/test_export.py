from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi import status

from app.api.v1.import_export.export import format_datetime
from app.core.database import get_db

BASE = "/api/v1/export"


def _query_mock(records, scalar_value=0):
    q = Mock()
    q.filter.return_value = q
    q.limit.return_value = q
    q.order_by.return_value = q
    q.offset.return_value = q
    q.all.return_value = records
    q.count.return_value = len(records)
    q.first.return_value = records[0] if records else None
    q.scalar = Mock(return_value=scalar_value)
    return q


def _model(**kwargs):
    m = Mock()
    for k, v in kwargs.items():
        setattr(m, k, v)
    return m


def _override_get_db(db):
    def gen():
        yield db
    return gen


# ─── format_datetime ───

def test_format_datetime_none():
    assert format_datetime(None) == ""


def test_format_datetime_datetime():
    dt = datetime(2024, 6, 15, 14, 30, 0)
    assert format_datetime(dt) == "2024-06-15 14:30:00"


def test_format_datetime_str():
    assert format_datetime("plain") == "plain"


# ─── 401 Unauthorized ───

class TestUnauthorized:
    @pytest.mark.parametrize("path,params", [
        ("/users", {}),
        ("/villages", {}),
        ("/schools", {}),
        ("/projects", {}),
        ("/funds", {}),
        ("/comprehensive", {}),
        ("/report-word", {"report_type": "summary"}),
        ("/report-pdf", {"report_type": "summary"}),
    ])
    def test_all_endpoints(self, client, path, params):
        resp = client.get(f"{BASE}{path}", params=params)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ─── 400 Unsupported Format ───

class TestUnsupportedFormat:
    @pytest.mark.parametrize("path", ["/comprehensive"])
    def test_csv_format(self, client_with_mocked_auth, path):
        client = client_with_mocked_auth
        resp = client.get(f"{BASE}{path}", params={"format": "csv"})
        assert resp.status_code == 400

    @pytest.mark.parametrize("path", ["/users", "/villages", "/schools", "/projects", "/funds"])
    def test_pdf_format_rejected(self, client_with_mocked_auth, path):
        """pdf 不属于支持的导出格式 → 400（前端已下线 pdf 选项）"""
        client = client_with_mocked_auth
        resp = client.get(f"{BASE}{path}", params={"format": "pdf"})
        assert resp.status_code == 400


class TestCsvFormat:
    """csv 导出格式支持（问题18：数据导出全功能）。"""

    @pytest.mark.parametrize("path", ["/users", "/villages", "/schools", "/projects", "/funds"])
    def test_csv_format_supported(self, client_with_mocked_auth, path):
        client = client_with_mocked_auth
        resp = client.get(f"{BASE}{path}", params={"format": "csv"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        disposition = resp.headers["content-disposition"]
        assert ".csv" in disposition


# ─── export_users ───

class TestExportUsers:
    @patch("app.api.v1.import_export.export.export_service")
    def test_success(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_user_list.return_value = b"fake_xlsx"

        users = [
            _model(id=1, username="alice", email="a@x.com", full_name="Alice",
                   role="admin", is_active=True, last_login=datetime(2024, 1, 1, 10, 0, 0)),
            _model(id=2, username="bob", email="", full_name=None, role=None,
                   is_active=False, last_login=None),
        ]
        db = _model(query=Mock(return_value=_query_mock(users)))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/users")

        assert resp.status_code == 200
        assert "spreadsheetml.sheet" in resp.headers["content-type"]
        assert resp.content == b"fake_xlsx"

        data = mock_svc.export_user_list.call_args[0][0]
        assert len(data) == 2
        assert data[0] == {
            "ID": 1, "用户名": "alice", "邮箱": "a@x.com", "姓名": "Alice",
            "角色": "admin", "状态": "启用", "最后登录": "2024-01-01 10:00:00",
        }
        assert data[1] == {
            "ID": 2, "用户名": "bob", "邮箱": "", "姓名": "",
            "角色": "无", "状态": "禁用", "最后登录": "",
        }

    @patch("app.api.v1.import_export.export.export_service")
    def test_keyword_filter(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_user_list.return_value = b"x"

        users = [_model(id=1, username="found", email="", full_name="Found",
                        role="user", is_active=True, last_login=None)]
        q = _query_mock(users)
        db = _model(query=Mock(return_value=q))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/users", params={"keyword": "found"})

        assert resp.status_code == 200
        assert q.filter.called
        data = mock_svc.export_user_list.call_args[0][0]
        assert len(data) == 1
        assert data[0]["用户名"] == "found"

    @patch("app.api.v1.import_export.export.export_service")
    def test_is_active_filter(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_user_list.return_value = b"x"

        users = [_model(id=1, username="u", email="", full_name="",
                        role="user", is_active=True, last_login=None)]
        q = _query_mock(users)
        db = _model(query=Mock(return_value=q))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/users", params={"is_active": "false"})

        assert resp.status_code == 200
        assert q.filter.called


# ─── export_villages ───

class TestExportVillages:
    @patch("app.api.v1.import_export.export.export_service")
    def test_success(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_village_list.return_value = b"fake_xlsx"

        villages = [
            _model(id=1, name="v1", village_name="v1", sequence_no="001",
                   province="P", city="C", county="Co",
                   transition_status="active",
                   population_data=[_model(year=2024, total_population=500)],
                   created_at=datetime(2024, 3, 1, 12, 0, 0)),
            _model(id=2, name="v2", village_name="v2", sequence_no=None,
                   province="", city="", county=None,
                   transition_status="",
                   population_data=[],
                   created_at=None),
        ]
        db = _model(query=Mock(return_value=_query_mock(villages)))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/villages")

        assert resp.status_code == 200
        data = mock_svc.export_village_list.call_args[0][0]
        assert len(data) == 2
        assert data[0]["编码"] == "001"
        assert data[0]["人口"] == 500
        assert data[0]["状态"] == "active"
        assert data[1]["人口"] == 0
        assert data[1]["编码"] == ""
        assert data[1]["创建时间"] == ""
        assert data[0]["创建时间"] == "2024-03-01 12:00:00"

    @patch("app.api.v1.import_export.export.export_service")
    def test_status_filter(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_village_list.return_value = b"x"

        q = _query_mock([])
        db = _model(query=Mock(return_value=q))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/villages", params={"status": "active"})

        assert resp.status_code == 200
        assert q.filter.called


# ─── export_schools ───

class TestExportSchools:
    @patch("app.api.v1.import_export.export.export_service")
    def test_success(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_school_list.return_value = b"fake_xlsx"

        schools = [
            _model(id=1, name="s1", code="001", type="primary", city="C",
                   student_count=200, teacher_count=15,
                   support_status=_model(value="active")),
            _model(id=2, name="s2", code="002", type="", city=None,
                   student_count=None, teacher_count=None,
                   support_status=None),
        ]
        db = _model(query=Mock(return_value=_query_mock(schools)))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/schools")

        assert resp.status_code == 200
        data = mock_svc.export_school_list.call_args[0][0]
        assert len(data) == 2
        assert data[0]["类型"] == "primary"
        assert data[0]["状态"] == "active"
        assert data[1]["学生数"] == 0
        assert data[1]["教师数"] == 0
        assert data[1]["状态"] == ""

    @patch("app.api.v1.import_export.export.export_service")
    def test_school_type_filter(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_school_list.return_value = b"x"

        q = _query_mock([])
        db = _model(query=Mock(return_value=q))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/schools", params={"school_type": "primary"})

        assert resp.status_code == 200
        assert q.filter.called


# ─── export_projects ───

class TestExportProjects:
    @patch("app.api.v1.import_export.export.export_service")
    def test_success(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_project_list.return_value = b"fake_xlsx"

        projects = [
            _model(id=1, name="p1", code="001", type="infrastructure",
                   status="active", budget=100000, progress=50,
                   start_date=datetime(2024, 1, 1), end_date=datetime(2024, 12, 31)),
            _model(id=2, name="p2", code="002", type="", status="draft",
                   budget=None, progress=None,
                   start_date=None, end_date=None),
        ]
        db = _model(query=Mock(return_value=_query_mock(projects)))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/projects")

        assert resp.status_code == 200
        data = mock_svc.export_project_list.call_args[0][0]
        assert len(data) == 2
        assert data[0]["预算"] == 100000
        assert data[0]["进度"] == "50%"
        assert data[1]["预算"] == 0
        assert data[1]["进度"] == "0%"

    @patch("app.api.v1.import_export.export.export_service")
    def test_filters(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_project_list.return_value = b"x"

        q = _query_mock([])
        db = _model(query=Mock(return_value=q))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/projects", params={
            "keyword": "road", "project_type": "infrastructure", "status": "active",
        })

        assert resp.status_code == 200


# ─── export_funds ───

class TestExportFunds:
    @patch("app.api.v1.import_export.export.export_service")
    def test_success(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_fund_list.return_value = b"fake_xlsx"

        funds = [
            _model(id=1, name="f1", type="project", amount=50000,
                   source="gov", purpose="build", status="approved",
                   operator="admin", date=datetime(2024, 6, 1)),
            _model(id=2, name="f2", type="", amount=0,
                   source=None, purpose=None, status="pending",
                   operator=None, date=None),
        ]
        db = _model(query=Mock(return_value=_query_mock(funds)))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/funds")

        assert resp.status_code == 200
        data = mock_svc.export_fund_list.call_args[0][0]
        assert len(data) == 2
        assert data[0]["金额"] == 50000
        assert data[0]["来源"] == "gov"
        assert data[0]["使用日期"] == "2024-06-01 00:00:00"
        assert data[1]["金额"] == 0
        assert data[1]["来源"] == ""
        assert data[1]["使用日期"] == ""

    @patch("app.api.v1.import_export.export.export_service")
    def test_filters(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_fund_list.return_value = b"x"

        q = _query_mock([])
        db = _model(query=Mock(return_value=q))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/funds", params={
            "keyword": "road", "fund_type": "project", "status": "approved",
        })

        assert resp.status_code == 200


# ─── export_comprehensive ───

class TestExportComprehensive:
    @patch("app.api.v1.import_export.export.export_service")
    def test_success(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_comprehensive_report.return_value = b"fake_xlsx"

        user_mock = _model(id=1, username="admin")
        village_mock = _model(id=1, name="v1", population_data=[])
        school_mock = _model(id=1, name="s1")
        project_mock = _model(id=1, name="p1", status="active", budget=10000, progress=50)
        fund_mock = _model(id=1, name="f1", amount=1000, status="approved", date=datetime(2024, 1, 1))

        registry = {
            "User": [user_mock],
            "SupportedVillage": [village_mock],
            "School": [school_mock],
            "Project": [project_mock],
            "Fund": [fund_mock],
        }

        def mock_query(entity):
            import sqlalchemy as sa
            if isinstance(entity, type) and hasattr(entity, "__tablename__"):
                key = entity.__name__
            elif (isinstance(entity, sa.sql.elements.BinaryExpression) or
                  isinstance(entity, sa.sql.elements.Null) or
                  hasattr(entity, "visit")):
                q = _query_mock([], scalar_value=50000.0)
                return q
            else:
                q = _query_mock([])
                return q
            q = _query_mock(registry.get(key, []))
            if key == "Fund":
                q.scalar = Mock(return_value=50000.0)
            return q

        db = _model(query=Mock(side_effect=mock_query))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/comprehensive")

        assert resp.status_code == 200

        args = mock_svc.export_comprehensive_report.call_args
        summary, villages_data, projects_data, funds_data = args[0]
        assert "用户总数" in summary
        assert summary["用户总数"] == 1
        assert "经费总金额" in summary
        assert len(villages_data) == 1
        assert len(projects_data) == 1
        assert len(funds_data) == 1

    @patch("app.api.v1.import_export.export.export_service")
    def test_with_year(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.export_comprehensive_report.return_value = b"x"

        all_records = {"User": [_model(id=1, username="u")]}

        def mock_query(entity):
            if isinstance(entity, type) and hasattr(entity, "__tablename__"):
                key = entity.__name__
            else:
                q = _query_mock([], scalar_value=0)
                return q
            q = _query_mock(all_records.get(key, []))
            return q

        db = _model(query=Mock(side_effect=mock_query))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/comprehensive", params={"year": 2024})

        assert resp.status_code == 200


# ─── report-word ───

class TestExportReportWord:
    @patch("app.api.v1.import_export.export.report_export_service")
    def test_summary(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.generate_summary_report_data.return_value = {"year": 2024, "sections": []}
        mock_svc.export_word.return_value = b"fake_docx"

        db = _model(query=Mock(return_value=_query_mock([])))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/report-word", params={"report_type": "summary"})

        assert resp.status_code == 200
        assert "wordprocessingml.document" in resp.headers["content-type"]
        assert resp.content == b"fake_docx"
        mock_svc.generate_summary_report_data.assert_called_once()
        mock_svc.export_word.assert_called_once()

    @patch("app.api.v1.import_export.export.report_export_service")
    def test_fund_detail(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.generate_fund_detail_report_data.return_value = {"year": 2024, "items": []}
        mock_svc.export_word.return_value = b"fake_docx"

        db = _model(query=Mock(return_value=_query_mock([])))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/report-word", params={"report_type": "fund_detail"})

        assert resp.status_code == 200
        mock_svc.generate_fund_detail_report_data.assert_called_once()
        mock_svc.export_word.assert_called_once()

    @patch("app.api.v1.import_export.export.report_export_service")
    def test_project_progress(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.generate_project_progress_report_data.return_value = {"year": 2024, "projects": []}
        mock_svc.export_word.return_value = b"fake_docx"

        db = _model(query=Mock(return_value=_query_mock([])))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/report-word", params={"report_type": "project_progress"})

        assert resp.status_code == 200
        mock_svc.generate_project_progress_report_data.assert_called_once()
        mock_svc.export_word.assert_called_once()

    def test_invalid_report_type(self, client_with_mocked_auth):
        client = client_with_mocked_auth
        db = _model(query=Mock(return_value=_query_mock([])))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/report-word", params={"report_type": "invalid"})

        assert resp.status_code == 400
        assert "不支持的报告类型" in resp.text


# ─── report-pdf ───

class TestExportReportPdf:
    @patch("app.api.v1.import_export.export.report_export_service")
    def test_summary(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.generate_summary_report_data.return_value = {"year": 2024, "sections": []}
        mock_svc.export_pdf.return_value = b"fake_pdf"

        db = _model(query=Mock(return_value=_query_mock([])))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/report-pdf", params={"report_type": "summary"})

        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]
        assert resp.content == b"fake_pdf"
        mock_svc.generate_summary_report_data.assert_called_once()
        mock_svc.export_pdf.assert_called_once()

    @patch("app.api.v1.import_export.export.report_export_service")
    def test_fund_detail(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.generate_fund_detail_report_data.return_value = {"year": 2024, "items": []}
        mock_svc.export_pdf.return_value = b"fake_pdf"

        db = _model(query=Mock(return_value=_query_mock([])))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/report-pdf", params={"report_type": "fund_detail"})

        assert resp.status_code == 200
        mock_svc.generate_fund_detail_report_data.assert_called_once()
        mock_svc.export_pdf.assert_called_once()

    @patch("app.api.v1.import_export.export.report_export_service")
    def test_project_progress(self, mock_svc, client_with_mocked_auth):
        client = client_with_mocked_auth
        mock_svc.generate_project_progress_report_data.return_value = {"year": 2024, "projects": []}
        mock_svc.export_pdf.return_value = b"fake_pdf"

        db = _model(query=Mock(return_value=_query_mock([])))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/report-pdf", params={"report_type": "project_progress"})

        assert resp.status_code == 200
        mock_svc.generate_project_progress_report_data.assert_called_once()
        mock_svc.export_pdf.assert_called_once()

    def test_invalid_report_type(self, client_with_mocked_auth):
        client = client_with_mocked_auth
        db = _model(query=Mock(return_value=_query_mock([])))
        client.app.dependency_overrides[get_db] = _override_get_db(db)

        resp = client.get(f"{BASE}/report-pdf", params={"report_type": "invalid"})

        assert resp.status_code == 400
        assert "不支持的报告类型" in resp.text

    def test_viewer_rejected(self, client_with_mocked_auth):
        """v1.8.1：PDF 报告导出与 Word 一致，仅管理员可用（viewer 返回 403）。"""
        from app.core.security import get_current_user

        client = client_with_mocked_auth
        viewer = Mock()
        viewer.id = 2
        viewer.username = "viewer"
        viewer.role = "viewer"
        viewer.is_superuser = False
        viewer.is_active = True
        viewer.permissions_list = []
        client.app.dependency_overrides[get_current_user] = lambda: viewer

        resp = client.get(f"{BASE}/report-pdf", params={"report_type": "summary"})

        assert resp.status_code == status.HTTP_403_FORBIDDEN

