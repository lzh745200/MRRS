"""Coverage gap tests for report_templates.py — fills remaining lines to 100%.

Covers:
- 372, 410: ``except HTTPException: raise`` in create/update (safe_commit 抛 HTTPException)
- 546-547: ``_to_bool`` 非 None 值分支
- 656-657, 660-661, 681-685, 719-720: 帮扶村导入的空村名/跳过重复/成功建行/工作日志降级
- 781-782, 826-827: 帮扶学校导入的空校名/工作日志降级
- 905-906, 925, 967-968, 996-997: 帮扶项目导入的空项目名/关联村命中/行异常/工作日志降级
- 1074-1075, 1089, 1109-1110, 1138-1139: 乡村工作导入同上
- 1221: 上传未知模块 confirm 模式

注: 生产 bug 已修复——``_village_process_rows`` 此前向 ``SupportedVillage(...)``
传入模型不存在的关键字（prefecture/total_households/registered_population），
导致村导入每行必抛 TypeError；现已改为 city 映射并移除无效 kwargs，
成功建行路径使用真实模型覆盖。
"""

import io
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1 import report_templates as rt
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Base
from app.models.project import Project
from app.models.report_template import ReportTemplate
from app.models.rural_work import RuralWork
from app.models.supported_village import SupportedVillage
from app.models.village import Village

API_PREFIX = "/api/v1"


def P(p):
    return f"{API_PREFIX}/report-templates{p}"


# ── 端点测试用的真实 SQLite fixtures（与 test_report_templates_api.py 同模式）──


@pytest.fixture(scope="module")
def engine():
    e = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=e)
    return e


@pytest.fixture
def db_session(engine):
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    if trans.is_active:
        trans.rollback()
    conn.close()


@pytest.fixture
def client(db_session):
    from app.main import app

    async def _override_get_db():
        yield db_session

    _original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = _original_overrides


@pytest.fixture
def auth_setup(client):
    async def mock_get_current_user():
        u = MagicMock()
        u.id = 1
        u.role = "admin"
        u.is_superuser = True
        return u

    client.app.dependency_overrides[get_current_user] = mock_get_current_user
    yield client


def _mock_db():
    """MagicMock db：q.filter.return_value=q 链式，all()/first()/delete() 默认安全。"""
    db = MagicMock()

    def _query(*args):
        q = MagicMock()
        q.filter.return_value = q
        q.all.return_value = []
        q.first.return_value = None
        q.delete.return_value = 0
        return q

    db.query.side_effect = _query
    return db


# ── create/update: except HTTPException → raise（372, 410）──


class TestHTTPExceptionReraise:
    def test_create_safe_commit_http_exception(self, auth_setup):
        """覆盖 372: safe_commit 抛 HTTPException 时被原样 re-raise。"""
        with patch(
            "app.api.v1.report_templates.safe_commit",
            side_effect=HTTPException(status_code=503, detail="db unavailable"),
        ):
            resp = auth_setup.post(
                P(""),
                json={"name": "提交异常", "type": "import", "module": "village"},
            )
        assert resp.status_code == 503

    def test_update_safe_commit_http_exception(self, auth_setup, db_session):
        """覆盖 410: 更新时 safe_commit 抛 HTTPException 被原样 re-raise。"""
        t = ReportTemplate(name="待更新", type="import", module="village")
        db_session.add(t)
        db_session.commit()
        db_session.refresh(t)
        with patch(
            "app.api.v1.report_templates.safe_commit",
            side_effect=HTTPException(status_code=503, detail="db unavailable"),
        ):
            resp = auth_setup.put(P(f"/{t.id}"), json={"name": "新名"})
        assert resp.status_code == 503


# ── 上传未知模块（1221）──


class TestUploadUnknownModule:
    def test_upload_confirm_unknown_module(self, auth_setup, db_session):
        """覆盖 1221: confirm 模式下未支持的模块 → 400（fields 必须非空才能走到分发）。"""
        t = ReportTemplate(
            name="未知模块模板",
            type="import",
            module="unknown",
            fields=json.dumps(
                [{"excel_col": "A", "excel_header": "名称", "db_field": "name", "required": False}],
                ensure_ascii=False,
            ),
        )
        db_session.add(t)
        db_session.commit()
        db_session.refresh(t)

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["名称"])
        ws.append(["行"])
        ws.append(["测试"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        resp = auth_setup.post(
            P(f"/{t.id}/upload?mode=confirm&import_mode=incremental"),
            files={
                "file": (
                    "data.xlsx",
                    buf,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert resp.status_code == 400
        assert "暂不支持导入" in resp.json()["detail"]


# ── _safe_float 辅助函数 ──


class TestSafeFloat:
    def test_none_returns_default(self):
        assert rt._safe_float(None) is None

    def test_valid_value(self):
        assert rt._safe_float("107.5") == 107.5

    def test_invalid_returns_default(self):
        assert rt._safe_float("abc") is None


# ── 帮扶村导入 ──


class TestVillageImportGaps:
    def test_process_rows_success(self):
        """覆盖成功建行路径（含 _to_bool 非 None 值）。

        使用真实 SupportedVillage 模型（此前的 kwargs bug 已修复：prefecture→city，
        并移除模型不存在的 total_households/registered_population；错表 village_map
        关联逻辑已移除——SupportedVillage 无 village_id 字段）。
        """
        db = _mock_db()
        parsed = [
            {
                "village_name": "示范村",
                "county": "某县",
                "is_three_regions": "是",
                "longitude": "107.5",
                "latitude": "26.2",
            }
        ]
        created, skipped, errors = rt._village_process_rows(
            db, parsed, "overwrite", set(), 1
        )
        assert created == 1
        assert skipped == 0
        assert errors == []
        record = db.add.call_args.args[0]
        assert record.village_name == "示范村"
        assert record.city == "黔南布依族苗族自治州"
        assert record.is_three_regions is True
        assert record.longitude == 107.5
        db.add.assert_called_once()

    def test_process_rows_row_exception(self):
        """行级 except: 行数据 __str__ 异常 → 记错误并继续。"""

        class _BadStr:
            def __str__(self):
                raise TypeError("boom")

        db = _mock_db()
        created, skipped, errors = rt._village_process_rows(
            db, [{"village_name": _BadStr()}], "overwrite", set(), 1
        )
        assert created == 0
        assert any("boom" in e for e in errors)

    def test_process_rows_empty_name(self):
        """覆盖 656-657: 村名空白 → 记错误并跳过。"""
        db = _mock_db()
        created, skipped, errors = rt._village_process_rows(
            db, [{"village_name": "   "}], "incremental", set(), 1
        )
        assert created == 0
        assert any("村名为空" in e for e in errors)

    def test_process_rows_skip_duplicate(self):
        """覆盖 660-661: 增量模式下重名 → skipped+1。"""
        db = _mock_db()
        created, skipped, errors = rt._village_process_rows(
            db,
            [{"village_name": "示范村"}],
            "incremental",
            {"示范村"},
            1,
        )
        assert created == 0
        assert skipped == 1
        assert errors == []

    def test_import_worklog_failure(self):
        """覆盖 719-720: 写工作日志失败仅降级记日志，不影响导入结果。"""
        db = _mock_db()
        with patch(
            "app.services.work_log_service.write_work_log",
            side_effect=Exception("log boom"),
        ):
            result = rt._import_village_data(db, [], 1, "incremental")
        assert result["success"] is True
        assert result["imported"] == 0


# ── 帮扶学校导入（781-782, 826-827）──


class TestSchoolImportGaps:
    def test_import_school_empty_name(self):
        """覆盖 781-782: 学校名称空白 → 记错误并跳过。"""
        db = _mock_db()
        result = rt._import_school_data(db, [{"name": "   "}], 1, "incremental")
        assert result["imported"] == 0
        assert result["failed"] == 1
        assert any("学校名称为空" in e for e in result["errors"])

    def test_import_school_worklog_failure(self):
        """覆盖 826-827: 写工作日志失败降级。"""
        db = _mock_db()
        with patch(
            "app.services.work_log_service.write_work_log",
            side_effect=Exception("log boom"),
        ):
            result = rt._import_school_data(db, [], 1, "incremental")
        assert result["success"] is True


# ── 帮扶项目导入（905-906, 925, 967-968, 996-997）──


class TestProjectImportGaps:
    def test_process_rows_empty_name(self):
        """覆盖 905-906: 项目名称空白（_safe_str 归一为 None）→ 记错误。"""
        db = _mock_db()
        created, skipped, errors = rt._project_process_rows(
            db, [{"name": "   "}], "incremental", set(), 1
        )
        assert created == 0
        assert any("项目名称为空" in e for e in errors)

    def test_process_rows_village_found(self):
        """覆盖 925: village_name 在 SupportedVillage 表中命中 → village_id 被赋值。"""
        db = _mock_db()
        village = MagicMock()
        village.id = 7
        village.village_name = "示范村"

        def _query(*args):
            q = MagicMock()
            q.filter.return_value = q
            q.all.return_value = []
            q.delete.return_value = 0
            q.first.return_value = village if args and args[0] is SupportedVillage else None
            return q

        db.query.side_effect = _query
        created, skipped, errors = rt._project_process_rows(
            db,
            [{"name": "关联村项目", "village_name": "示范村"}],
            "incremental",
            set(),
            1,
        )
        assert created == 1
        assert errors == []
        record = db.add.call_args[0][0]
        assert record.village_id == 7

    def test_process_rows_exception(self):
        """覆盖 967-968: 单行构造异常 → 记入 errors，循环继续。"""
        db = _mock_db()
        with patch.object(Project, "__init__", side_effect=Exception("broken")):
            created, skipped, errors = rt._project_process_rows(
                db, [{"name": "异常项目"}], "incremental", set(), 1
            )
        assert created == 0
        assert any("broken" in e for e in errors)

    def test_import_worklog_failure(self):
        """覆盖 996-997: 写工作日志失败降级。"""
        db = _mock_db()
        with patch(
            "app.services.work_log_service.write_work_log",
            side_effect=Exception("log boom"),
        ):
            result = rt._import_project_data(db, [], 1, "incremental")
        assert result["success"] is True


# ── 乡村工作导入（1074-1075, 1089, 1109-1110, 1138-1139）──


class TestRuralWorkImportGaps:
    def test_process_rows_empty_name(self):
        """覆盖 1074-1075: 工作名称空白 → 记错误。"""
        db = _mock_db()
        created, skipped, errors = rt._rural_work_process_rows(
            db, [{"name": "   "}], "incremental", set(), 1
        )
        assert created == 0
        assert any("工作名称为空" in e for e in errors)

    def test_process_rows_village_found(self):
        """覆盖 1089: village_name 命中 Village 表 → village_id 被赋值。"""
        db = _mock_db()
        village = MagicMock()
        village.id = 9
        village.name = "示范村"

        def _query(*args):
            q = MagicMock()
            q.filter.return_value = q
            q.all.return_value = []
            q.delete.return_value = 0
            q.first.return_value = village if args and args[0] is Village else None
            return q

        db.query.side_effect = _query
        created, skipped, errors = rt._rural_work_process_rows(
            db,
            [{"name": "关联工作", "village_name": "示范村"}],
            "incremental",
            set(),
            1,
        )
        assert created == 1
        assert errors == []
        record = db.add.call_args[0][0]
        assert record.village_id == 9

    def test_process_rows_exception(self):
        """覆盖 1109-1110: 单行构造异常 → 记入 errors。"""
        db = _mock_db()
        with patch.object(RuralWork, "__init__", side_effect=Exception("broken")):
            created, skipped, errors = rt._rural_work_process_rows(
                db, [{"name": "异常工作"}], "incremental", set(), 1
            )
        assert created == 0
        assert any("broken" in e for e in errors)

    def test_import_worklog_failure(self):
        """覆盖 1138-1139: 写工作日志失败降级。"""
        db = _mock_db()
        with patch(
            "app.services.work_log_service.write_work_log",
            side_effect=Exception("log boom"),
        ):
            result = rt._import_rural_work_data(db, [], 1, "incremental")
        assert result["success"] is True


# ── _to_bool 直接测试（546-547 兜底）──


class TestToBool:
    def test_to_bool_non_none_values(self):
        """覆盖 546-547: 非 None 输入的字符串化判断。"""
        assert rt._to_bool("是") is True
        assert rt._to_bool("true") is True
        assert rt._to_bool(1) is True
        assert rt._to_bool("否") is False


# ── get_available_fields 端点（384-385）──


class TestGetAvailableFields:
    def test_known_module_returns_fields(self, auth_setup):
        """覆盖 384-385: 已知模块返回字段列表。"""
        resp = auth_setup.get(P("/available-fields?module=village"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["success"] is True
        keys = [f["key"] for f in body["data"]]
        assert "village_name" in keys

    def test_unknown_module_returns_empty(self, auth_setup):
        """覆盖 384: MODULE_FIELDS.get 未命中返回 []。"""
        resp = auth_setup.get(P("/available-fields?module=__nope__"))
        assert resp.status_code == 200
        assert resp.json()["data"] == []
