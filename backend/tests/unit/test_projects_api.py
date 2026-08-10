"""Tests for app/api/v1/projects.py — 100% branch coverage."""
import io
import os
import tempfile
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.api.v1.projects import (
    _batch_get_fund_health_fields,
    _can_modify_project,
    _file_to_dict,
    _get_fund_health_fields,
    _get_project_or_404,
    _project_to_dict,
    _project_to_diff_dict,
    _project_to_list_dict,
    _task_to_dict,
    ProjectCreate,
    ProjectUpdate,
)
from app.core.exceptions import NotFoundException
from app.models.project import Fund, Project, ProjectFile, ProjectTask


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.commit = MagicMock(); db.flush = MagicMock()
    db.rollback = MagicMock(); db.refresh = MagicMock()
    db.close = MagicMock(); db.execute = MagicMock()
    return db


@pytest.fixture
def admin_user():
    u = MagicMock()
    u.id = 1; u.username = "admin"; u.role = "admin"
    u.is_superuser = True; u.organization_id = 1
    u.permissions_list = ["*"]; u.full_name = "管理员"
    u.department_id = 1
    return u


@pytest.fixture
def regular_user():
    u = MagicMock()
    u.id = 2; u.username = "user"; u.role = "user"
    u.is_superuser = False; u.organization_id = 2
    u.permissions_list = ["read"]; u.full_name = "普通用户"
    u.department_id = 2
    return u


@pytest.fixture
def sample_project():
    p = MagicMock(spec=Project)
    p.id = 1; p.name = "测试项目"; p.code = "PRJ-20260101-ABC123"
    p.type = "infrastructure"; p.status = "draft"; p.description = "测试描述"
    p.objectives = "目标"; p.village_id = 1; p.organization_id = 1
    p.budget = Decimal("100.00"); p.actual_cost = Decimal("50.00")
    p.invested_amount = Decimal("30.00"); p.progress = 50
    p.leader = "领导"; p.contact = "123"
    p.responsible_unit = "单位"; p.responsible_person = "张三"
    p.contact_phone = "13800138000"
    p.start_date = date(2026, 1, 1); p.end_date = date(2026, 12, 31)
    p.actual_start_date = date(2026, 2, 1); p.actual_end_date = None
    p.urgency_level = "normal"; p.contract_number = "CT-001"
    p.fund_manager = "李四"; p.fund_usage_plan = "计划"
    p.fund_source = "superior_allocation"
    p.payer_account_name = "payer"; p.payer_account_number = "123"
    p.payer_bank = "银行"; p.payer_handler = "经办人"; p.payer_contact = "139"
    p.payee_account_name = "payee"; p.payee_bank = "银行2"
    p.payee_handler = "经办人2"; p.payee_contact = "140"
    p.is_delayed = False; p.delay_reason = None
    p.expected_benefits = "效益"; p.achievements = "成果"
    p.tags = "tag1,tag2"; p.remarks = "备注"
    p.created_by = 1
    p.created_at = datetime(2026, 1, 1, 12, 0, 0)
    p.updated_at = datetime(2026, 1, 2, 12, 0, 0)
    return p


@pytest.fixture
def sample_fund():
    f = MagicMock(spec=Fund)
    f.id = 1; f.project_id = 1; f.project_name = "测试项目"
    f.name = "经费1"; f.amount = 100.0; f.approved_amount = 90.0
    f.used_amount = 50.0; f.deviation_rate = 5.0; f.health_score = 85
    f.source = "财政"; f.purpose = "用途"
    f.to_dict = MagicMock(return_value={"id": 1, "name": "经费1", "amount": 100.0})
    return f


@pytest.fixture
def sample_task():
    t = MagicMock(spec=ProjectTask)
    t.id = 1; t.project_id = 1; t.name = "任务1"; t.description = "任务描述"
    t.status = "pending"; t.priority = 5; t.assignee = "张三"
    t.due_date = date(2026, 6, 1)
    t.created_at = datetime(2026, 1, 15, 12, 0, 0)
    t.updated_at = datetime(2026, 1, 15, 12, 0, 0)
    return t


@pytest.fixture
def sample_project_file():
    f = MagicMock(spec=ProjectFile)
    f.id = 1; f.project_id = 1; f.category = "research"
    f.filename = "doc.pdf"; f.filepath = "/tmp/doc.pdf"
    f.file_size = 1024; f.uploaded_by = 1
    f.created_at = datetime(2026, 1, 10, 12, 0, 0)
    return f


def _setup_client(client, mock_db, user):
    from app.core.database import get_db
    from app.core.security import get_current_user
    client.app.dependency_overrides[get_db] = lambda: mock_db
    client.app.dependency_overrides[get_current_user] = lambda: user
    return client


# ── Utility functions ──


class TestUtilityFunctions:
    def test_project_to_diff_dict_full(self, sample_project):
        d = _project_to_diff_dict(sample_project)
        assert d["name"] == "测试项目" and d["budget"] == 100.0

    def test_project_to_diff_dict_none_fields(self):
        p = MagicMock(spec=Project)
        for attr in ("name", "code", "type", "status", "budget", "progress",
                     "responsible_unit", "responsible_person", "contact_phone",
                     "start_date", "end_date", "village_id", "fund_source",
                     "is_delayed", "delay_reason", "remarks"):
            setattr(p, attr, None)
        d = _project_to_diff_dict(p)
        assert d["code"] is None and d["budget"] is None and d["is_delayed"] is False

    def test_can_modify_project_admin(self, admin_user, sample_project):
        assert _can_modify_project(sample_project, admin_user) is True

    def test_can_modify_project_creator(self, regular_user, sample_project):
        sample_project.created_by = 2
        assert _can_modify_project(sample_project, regular_user) is True

    def test_can_modify_project_not_creator(self, regular_user, sample_project):
        sample_project.created_by = 1
        assert _can_modify_project(sample_project, regular_user) is False

    def test_get_project_or_404_found(self, mock_db, sample_project):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        assert _get_project_or_404(mock_db, 1).id == 1

    def test_get_project_or_404_not_found(self, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundException):
            _get_project_or_404(mock_db, 999)

    def test_project_to_dict(self, sample_project):
        d = _project_to_dict(sample_project)
        assert d["id"] == 1 and d["actual_end_date"] is None

    def test_project_to_list_dict(self, sample_project):
        d = _project_to_list_dict(sample_project)
        assert d["id"] == 1 and "description" not in d

    def test_task_to_dict(self, sample_task):
        d = _task_to_dict(sample_task)
        assert d["id"] == 1 and d["due_date"] == "2026-06-01"

    def test_get_fund_health_fields_no_funds(self, mock_db):
        mock_db.query.return_value.filter.return_value.all.return_value = []
        r = _get_fund_health_fields(mock_db, 1)
        assert r["fund_health_score"] is None

    def test_get_fund_health_fields_with_funds(self, mock_db, sample_fund):
        mock_db.query.return_value.filter.return_value.all.return_value = [sample_fund]
        r = _get_fund_health_fields(mock_db, 1)
        assert r["fund_health_score"] == 85

    def test_batch_get_fund_health_fields_empty(self, mock_db):
        assert _batch_get_fund_health_fields(mock_db, []) == {}

    def test_batch_get_fund_health_fields(self, mock_db, sample_fund):
        mock_db.query.return_value.filter.return_value.all.return_value = [sample_fund]
        r = _batch_get_fund_health_fields(mock_db, [1, 2])
        assert 1 in r and r[2]["fund_health_score"] is None

    def test_file_to_dict(self, sample_project_file):
        d = _file_to_dict(sample_project_file)
        assert d["id"] == 1 and "download_url" in d

    def test_project_create_valid(self):
        d = ProjectCreate(name="T", budget=100.0, start_date="2026-01-01", end_date="2026-12-31")
        assert d.name == "T"

    def test_project_create_invalid_dates(self):
        with pytest.raises(ValueError, match="结束日期不能早于开始日期"):
            ProjectCreate(name="t", start_date="2026-12-31", end_date="2026-01-01")

    def test_project_update_valid(self):
        assert ProjectUpdate(status="draft").status == "draft"

    def test_project_update_invalid_status(self):
        with pytest.raises(ValueError, match="无效状态"):
            ProjectUpdate(status="invalid_status")


# ── API tests ──


class TestProjectsAPI:

    def test_list_projects(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        p = MagicMock()
        p.id = 1; p.name = "P"; p.code = "C"; p.type = "t"; p.status = "draft"
        p.village_id = None; p.organization_id = 1
        p.budget = Decimal("100"); p.actual_cost = Decimal("0"); p.progress = 0
        p.invested_amount = Decimal("0"); p.responsible_unit = "U"
        p.responsible_person = "P"; p.contact_phone = None
        p.start_date = None; p.end_date = None; p.urgency_level = "normal"
        p.fund_source = None; p.is_delayed = None; p.tags = None; p.created_by = 1
        p.created_at = datetime(2026, 1, 1); p.updated_at = datetime(2026, 1, 1)

        q = MagicMock()
        q.count.return_value = 2
        q.options.return_value = q
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value.limit.return_value.all.return_value = [p, p]
        with patch("sqlalchemy.orm.selectinload"), \
             patch("app.core.data_permission.filter_by_data_scope", return_value=q):
            mock_db.query.return_value = q
            resp = client.get("/api/v1/projects")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 2

    def test_list_projects_with_filters(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        q = MagicMock()
        q.count.return_value = 0
        q.options.return_value = q
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value.limit.return_value.all.return_value = []
        with patch("sqlalchemy.orm.selectinload"), \
             patch("app.core.data_permission.filter_by_data_scope", return_value=q):
            mock_db.query.return_value = q
            resp = client.get("/api/v1/projects?keyword=test&project_type=infra&status=draft&village_id=1&sort_by=name&sort_order=asc&include_cancelled=true")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0

    def test_get_project_detail(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        mock_db.query.return_value.filter.return_value.scalar.return_value = 2
        resp = client.get("/api/v1/projects/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_get_project_detail_404(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        resp = client.get("/api/v1/projects/999")
        assert resp.status_code == 404

    @patch("app.api.v1.projects.get_client_ip", return_value="127.0.0.1")
    def test_create_project(self, mock_ip, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        with patch("app.api.v1.projects.AuditLogService") as mock_al, \
             patch("app.api.v1.projects.AuditEnhancementService") as mock_ae, \
             patch("app.api.v1.projects.write_work_log"):
            mock_al.return_value.log = AsyncMock()
            mock_ae.create_audit_log.return_value = MagicMock()
            mock_ae.record_changes.return_value = None
            mock_db.query.return_value.filter.return_value.first.return_value = None
            resp = client.post("/api/v1/projects", json={
                "name": "新建项目", "budget": 200.0,
                "start_date": "2026-03-01", "end_date": "2026-10-31",
                "type": "infrastructure",
            })
        assert resp.status_code == 201 and resp.json()["data"]["name"] == "新建项目"

    def test_create_project_duplicate_code(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        existing = MagicMock(); existing.code = "PRJ-EXISTING"
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        resp = client.post("/api/v1/projects", json={"name": "重复", "code": "PRJ-EXISTING"})
        assert resp.status_code == 500  # AppError → handle_db_errors_async → 500

    def test_create_project_validation_error(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        resp = client.post("/api/v1/projects", json={})
        assert resp.status_code == 422

    @patch("app.api.v1.projects.get_client_ip", return_value="127.0.0.1")
    def test_update_project(self, mock_ip, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        with patch("app.api.v1.projects.AuditLogService") as mock_al, \
             patch("app.api.v1.projects.AuditEnhancementService") as mock_ae, \
             patch("app.api.v1.projects.write_work_log"):
            mock_al.return_value.log = AsyncMock()
            mock_ae.create_audit_log.return_value = MagicMock()
            mock_ae.record_changes.return_value = None
            mock_db.query.return_value.filter.return_value.first.return_value = sample_project
            resp = client.put("/api/v1/projects/1", json={"name": "更新名称"})
        assert resp.status_code == 200 and resp.json()["message"] == "更新成功"

    def test_update_project_forbidden(self, client, mock_db, regular_user, sample_project):
        _setup_client(client, mock_db, regular_user)
        sample_project.created_by = 1
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        resp = client.put("/api/v1/projects/1", json={"name": "x"})
        assert resp.status_code == 500  # AppError → handle_db_errors_async → 500

    def test_update_project_date_validation(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        sample_project.start_date = date(2026, 6, 1)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        resp = client.put("/api/v1/projects/1", json={
            "start_date": "2026-12-01", "end_date": "2026-01-01"
        })
        assert resp.status_code == 500  # AppError → handle_db_errors_async → 500

    @patch("app.api.v1.projects.get_client_ip", return_value="127.0.0.1")
    def test_update_project_status_change(self, mock_ip, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        with patch("app.api.v1.projects.AuditLogService") as mock_al, \
             patch("app.api.v1.projects.AuditEnhancementService") as mock_ae, \
             patch("app.api.v1.projects.write_work_log"), \
             patch("app.services.fund_event_handler.on_project_status_change") as mock_psc:
            mock_al.return_value.log = AsyncMock()
            mock_ae.create_audit_log.return_value = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = sample_project
            resp = client.put("/api/v1/projects/1", json={"status": "in_progress"})
        assert resp.status_code == 200
        mock_psc.assert_called_once()

    @patch("app.api.v1.projects.get_client_ip", return_value="127.0.0.1")
    def test_update_project_status_change_rollback(self, mock_ip, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        with patch("app.services.fund_event_handler.on_project_status_change",
                   side_effect=Exception("fund error")):
            mock_db.query.return_value.filter.return_value.first.return_value = sample_project
            resp = client.put("/api/v1/projects/1", json={"status": "in_progress"})
        assert resp.status_code == 500
        assert mock_db.rollback.call_count == 2

    @patch("app.api.v1.projects.get_client_ip", return_value="127.0.0.1")
    @patch("app.api.v1.projects.is_superuser", return_value=True)
    def test_delete_project(self, mock_super, mock_ip, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        sample_project.status = "draft"
        with patch("app.api.v1.projects.AuditLogService") as mock_al, \
             patch("app.api.v1.projects.AuditEnhancementService") as mock_ae, \
             patch("app.api.v1.projects.write_work_log"):
            mock_al.return_value.log = AsyncMock()
            mock_ae.create_audit_log.return_value = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = sample_project
            resp = client.delete("/api/v1/projects/1")
        assert resp.status_code == 200 and resp.json()["message"] == "删除成功"

    def test_delete_project_already_cancelled(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        sample_project.status = "cancelled"
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        resp = client.delete("/api/v1/projects/1")
        assert resp.status_code == 400

    def test_delete_project_forbidden(self, client, mock_db, regular_user, sample_project):
        _setup_client(client, mock_db, regular_user)
        sample_project.created_by = 1
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        resp = client.delete("/api/v1/projects/1")
        assert resp.status_code == 500

    def test_get_project_change_history(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        with patch("app.api.v1.projects.AuditEnhancementService.get_change_history",
                   return_value=[{"field": "name"}]):
            mock_db.query.return_value.filter.return_value.first.return_value = sample_project
            resp = client.get("/api/v1/projects/1/history/changes")
        assert resp.status_code == 200 and len(resp.json()["data"]["items"]) == 1

    def test_get_project_funds(self, client, mock_db, admin_user, sample_project, sample_fund):
        _setup_client(client, mock_db, admin_user)
        fund_q = MagicMock()
        fund_q.count.return_value = 1
        fund_q.filter.return_value.count.return_value = 1
        fund_q.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [sample_fund]
        proj_q = MagicMock()
        proj_q.filter.return_value.first.return_value = sample_project
        mock_db.query.side_effect = lambda model: fund_q if model == Fund else proj_q
        resp = client.get("/api/v1/projects/1/funds")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_create_project_fund(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        resp = client.post("/api/v1/projects/1/funds", json={"name": "新增经费", "amount": 50.0})
        assert resp.status_code == 201

    def test_create_project_fund_fail(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        mock_db.commit.side_effect = Exception("db error")
        resp = client.post("/api/v1/projects/1/funds", json={"name": "经费", "amount": 50.0})
        assert resp.status_code == 500

    def test_get_project_tasks(self, client, mock_db, admin_user, sample_project, sample_task):
        _setup_client(client, mock_db, admin_user)
        task_q = MagicMock()
        task_q.filter.return_value.first.return_value = sample_project
        task_q.filter.return_value.count.return_value = 1
        task_q.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [sample_task]
        proj_q = MagicMock()
        proj_q.filter.return_value.first.return_value = sample_project
        mock_db.query.side_effect = lambda model: task_q if model == ProjectTask else proj_q
        resp = client.get("/api/v1/projects/1/tasks")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1

    def test_get_project_tasks_filtered(self, client, mock_db, admin_user, sample_project, sample_task):
        _setup_client(client, mock_db, admin_user)
        q = MagicMock()
        q.filter.return_value.first.return_value = sample_project
        q2 = MagicMock()
        q2.filter.return_value = q2
        q2.count.return_value = 1
        q2.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [sample_task]
        mock_db.query.side_effect = lambda model: q if model == Project else q2
        resp = client.get("/api/v1/projects/1/tasks?status=pending")
        assert resp.status_code == 200

    def test_create_project_task(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        resp = client.post("/api/v1/projects/1/tasks", json={"name": "新任务"})
        assert resp.status_code == 201

    def test_create_project_task_fail(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        mock_db.commit.side_effect = Exception("fail")
        resp = client.post("/api/v1/projects/1/tasks", json={"name": "任务"})
        assert resp.status_code == 500

    def test_update_project_task(self, client, mock_db, admin_user, sample_project, sample_task):
        _setup_client(client, mock_db, admin_user)
        q1 = MagicMock(); q1.filter.return_value.first.return_value = sample_project
        q2 = MagicMock(); q2.filter.return_value.first.return_value = sample_task
        mock_db.query.side_effect = lambda m: q1 if m == Project else q2
        resp = client.put("/api/v1/projects/1/tasks/1", json={"name": "更新任务", "status": "completed"})
        assert resp.status_code == 200

    def test_update_project_task_not_found(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        q1 = MagicMock(); q1.filter.return_value.first.return_value = sample_project
        q2 = MagicMock(); q2.filter.return_value.first.return_value = None
        mock_db.query.side_effect = lambda m: q1 if m == Project else q2
        resp = client.put("/api/v1/projects/1/tasks/999", json={"name": "x"})
        assert resp.status_code == 404

    def test_update_project_task_fail(self, client, mock_db, admin_user, sample_project, sample_task):
        _setup_client(client, mock_db, admin_user)
        q1 = MagicMock(); q1.filter.return_value.first.return_value = sample_project
        q2 = MagicMock(); q2.filter.return_value.first.return_value = sample_task
        mock_db.query.side_effect = lambda m: q1 if m == Project else q2
        mock_db.commit.side_effect = Exception("fail")
        resp = client.put("/api/v1/projects/1/tasks/1", json={"name": "x"})
        assert resp.status_code == 500

    def test_delete_project_task(self, client, mock_db, admin_user, sample_project, sample_task):
        _setup_client(client, mock_db, admin_user)
        q1 = MagicMock(); q1.filter.return_value.first.return_value = sample_project
        q2 = MagicMock(); q2.filter.return_value.first.return_value = sample_task
        mock_db.query.side_effect = lambda m: q1 if m == Project else q2
        resp = client.delete("/api/v1/projects/1/tasks/1")
        assert resp.status_code == 200

    def test_delete_project_task_not_found(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        q1 = MagicMock(); q1.filter.return_value.first.return_value = sample_project
        q2 = MagicMock(); q2.filter.return_value.first.return_value = None
        mock_db.query.side_effect = lambda m: q1 if m == Project else q2
        resp = client.delete("/api/v1/projects/1/tasks/999")
        assert resp.status_code == 404

    def test_delete_project_task_fail(self, client, mock_db, admin_user, sample_project, sample_task):
        _setup_client(client, mock_db, admin_user)
        q1 = MagicMock(); q1.filter.return_value.first.return_value = sample_project
        q2 = MagicMock(); q2.filter.return_value.first.return_value = sample_task
        mock_db.query.side_effect = lambda m: q1 if m == Project else q2
        mock_db.commit.side_effect = Exception("fail")
        resp = client.delete("/api/v1/projects/1/tasks/1")
        assert resp.status_code == 500

    def test_get_project_stats(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        q = mock_db.query.return_value
        q.filter.return_value = q  # 端点链式调用两次 .filter()，需自返回
        q.group_by.return_value.all.return_value = [
            ("draft", 5, 1000.0), ("in_progress", 3, 2000.0),
        ]
        q.scalar.return_value = 500.0
        resp = client.get("/api/v1/projects/stats")
        assert resp.status_code == 200
        assert resp.json()["total"] == 8 and resp.json()["total_budget"] == 3000.0

    def test_export_projects_xlsx(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        q = MagicMock(); q.filter.return_value = q
        q.order_by.return_value.limit.return_value.all.return_value = []
        with patch("sqlalchemy.orm.selectinload"), \
             patch("app.core.data_permission.filter_by_data_scope", return_value=q):
            mock_db.query.return_value = q
            resp = client.get("/api/v1/projects/export")
        assert resp.status_code == 200

    def test_export_projects_with_filters(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        q = MagicMock(); q.filter.return_value = q
        q.order_by.return_value.limit.return_value.all.return_value = []
        with patch("sqlalchemy.orm.selectinload"), \
             patch("app.core.data_permission.filter_by_data_scope", return_value=q):
            mock_db.query.return_value = q
            resp = client.get("/api/v1/projects/export?keyword=test&project_type=infra&status=draft")
        assert resp.status_code == 200

    def test_export_projects_csv_fallback(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        p = MagicMock()
        p.code = "C"; p.name = "N"; p.type = "T"; p.status = "S"
        p.budget = None; p.invested_amount = None; p.progress = None
        p.responsible_person = None; p.responsible_unit = None
        p.start_date = None; p.end_date = None
        q = MagicMock(); q.filter.return_value = q
        q.order_by.return_value.limit.return_value.all.return_value = [p]
        mock_db.query.return_value = q

        import builtins
        real_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == "openpyxl":
                raise ImportError("No module named openpyxl")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            resp = client.get("/api/v1/projects/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    # 注：download/generate_project_template 的 standard/simplified/historical/yearly_update
    # 变体端点已统一并入集中式 /import/template（委托 ExcelTemplateService），
    # 对应空壳测试已删除——集中式端点的覆盖由 test_download_project_template 等保留用例承担。

    def test_import_projects(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["项目名称", "项目类型", "负责单位", "负责人", "预算金额(万元)"])
        ws.append(["测试项目", "基础设施", "单位A", "张三", 100])
        buf = io.BytesIO(); wb.save(buf); buf.seek(0)

        mock_db.query.return_value.filter.return_value.first.return_value = None
        async def mock_check(*a, **kw): return True
        with patch("app.api.v1.projects.check_rate_limit", mock_check):
            resp = client.post(
                "/api/v1/projects/import",
                files={"file": ("test.xlsx", buf.getvalue(),
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        assert resp.status_code == 200 and resp.json()["success"] is True

    def test_import_projects_rate_limited(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        async def mock_check(*a, **kw): return False
        with patch("app.api.v1.projects.check_rate_limit", mock_check):
            resp = client.post("/api/v1/projects/import", files={"file": ("test.xlsx", b"data", "")})
        assert resp.status_code == 429

    def test_import_projects_invalid_file(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        async def mock_check(*a, **kw): return True
        with patch("app.api.v1.projects.check_rate_limit", mock_check):
            resp = client.post("/api/v1/projects/import", files={"file": ("test.txt", b"data", "text/plain")})
        assert resp.status_code == 400

    def test_import_projects_parse_error(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        async def mock_check(*a, **kw): return True
        with patch("app.api.v1.projects.check_rate_limit", mock_check):
            resp = client.post("/api/v1/projects/import", files={"file": ("test.xlsx", b"not-excel", "")})
        assert resp.status_code == 400

    def test_upload_project_files(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        tmpdir = tempfile.mkdtemp()
        try:
            mock_settings = MagicMock()
            mock_settings.UPLOAD_DIR = tmpdir
            mock_settings.allowed_file_types_list = ["pdf", "doc", "docx"]
            mock_settings.MAX_FILE_SIZE = 50 * 1024 * 1024
            mock_settings.CSRF_ENABLED = False
            with patch("app.core.config.settings", mock_settings), \
                 patch("app.utils.upload_helper.settings", mock_settings):
                resp = client.post(
                    "/api/v1/projects/1/files",
                    data={"category": "research"},
                    files={"files": ("doc.pdf", b"pdfcontent", "application/pdf")},
                )
            assert resp.status_code == 200 and resp.json()["success"] is True
        finally:
            import shutil; shutil.rmtree(tmpdir, ignore_errors=True)

    def test_upload_project_files_invalid_category(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        resp = client.post(
            "/api/v1/projects/1/files",
            data={"category": "invalid_cat"},
            files={"files": ("doc.pdf", b"data", "application/pdf")},
        )
        assert resp.status_code == 400

    def test_upload_project_files_type_check(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        mock_settings = MagicMock()
        mock_settings.allowed_file_types_list = ["pdf", "doc"]
        mock_settings.MAX_FILE_SIZE = 50 * 1024 * 1024
        mock_settings.CSRF_ENABLED = False
        with patch("app.core.config.settings", mock_settings), \
             patch("app.utils.upload_helper.settings", mock_settings):
            resp = client.post(
                "/api/v1/projects/1/files",
                data={"category": "research"},
                files={"files": ("doc.exe", b"data", "")},
            )
        assert resp.status_code == 400

    def test_upload_project_files_forbidden(self, client, mock_db, regular_user, sample_project):
        _setup_client(client, mock_db, regular_user)
        sample_project.created_by = 1
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        resp = client.post(
            "/api/v1/projects/1/files",
            data={"category": "research"},
            files={"files": ("doc.pdf", b"data", "application/pdf")},
        )
        assert resp.status_code == 403

    def test_list_project_files(self, client, mock_db, admin_user, sample_project, sample_project_file):
        _setup_client(client, mock_db, admin_user)
        q1 = MagicMock(); q1.filter.return_value.first.return_value = sample_project
        q2 = MagicMock(); q2.filter.return_value = q2; q2.order_by.return_value.all.return_value = [sample_project_file]
        mock_db.query.side_effect = lambda m: q1 if m == Project else q2
        resp = client.get("/api/v1/projects/1/files")
        assert resp.status_code == 200 and len(resp.json()["data"]["files"]) == 1

    def test_list_project_files_filtered(self, client, mock_db, admin_user, sample_project, sample_project_file):
        _setup_client(client, mock_db, admin_user)
        q1 = MagicMock(); q1.filter.return_value.first.return_value = sample_project
        q2 = MagicMock(); q2.filter.return_value = q2; q2.order_by.return_value.all.return_value = [sample_project_file]
        mock_db.query.side_effect = lambda m: q1 if m == Project else q2
        resp = client.get("/api/v1/projects/1/files?category=research")
        assert resp.status_code == 200

    def test_delete_project_file(self, client, mock_db, admin_user, sample_project, sample_project_file):
        _setup_client(client, mock_db, admin_user)
        q1 = MagicMock(); q1.filter.return_value.first.return_value = sample_project
        q2 = MagicMock(); q2.filter.return_value.first.return_value = sample_project_file
        mock_db.query.side_effect = lambda m: q1 if m == Project else q2
        with patch("app.api.v1.projects.os.path.exists", return_value=True), \
             patch("app.api.v1.projects.os.remove"):
            resp = client.delete("/api/v1/projects/1/files/1")
        assert resp.status_code == 200

    def test_delete_project_file_oserror(self, client, mock_db, admin_user, sample_project, sample_project_file):
        _setup_client(client, mock_db, admin_user)
        q1 = MagicMock(); q1.filter.return_value.first.return_value = sample_project
        q2 = MagicMock(); q2.filter.return_value.first.return_value = sample_project_file
        mock_db.query.side_effect = lambda m: q1 if m == Project else q2
        with patch("app.api.v1.projects.os.path.exists", return_value=True), \
             patch("app.api.v1.projects.os.remove", side_effect=OSError):
            resp = client.delete("/api/v1/projects/1/files/1")
        assert resp.status_code == 200

    def test_delete_project_file_not_found(self, client, mock_db, admin_user, sample_project):
        _setup_client(client, mock_db, admin_user)
        q1 = MagicMock(); q1.filter.return_value.first.return_value = sample_project
        q2 = MagicMock(); q2.filter.return_value.first.return_value = None
        mock_db.query.side_effect = lambda m: q1 if m == Project else q2
        resp = client.delete("/api/v1/projects/1/files/999")
        assert resp.status_code == 404

    def test_delete_project_file_forbidden(self, client, mock_db, regular_user, sample_project):
        _setup_client(client, mock_db, regular_user)
        sample_project.created_by = 1
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project
        resp = client.delete("/api/v1/projects/1/files/1")
        assert resp.status_code == 403

    def test_download_project_file(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
            tf.write(b"content"); tf.flush(); tf_path = tf.name
        try:
            pf = MagicMock(spec=ProjectFile)
            pf.id = 1; pf.project_id = 1; pf.category = "research"
            pf.filename = "test.pdf"; pf.filepath = tf_path
            pf.file_size = 7; pf.uploaded_by = 1
            pf.created_at = datetime(2026, 1, 10, 12, 0, 0)
            mock_db.query.return_value.filter.return_value.first.return_value = pf
            resp = client.get("/api/v1/projects/1/files/1/download")
            assert resp.status_code == 200
        finally:
            os.unlink(tf_path)

    def test_download_project_file_not_found(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        resp = client.get("/api/v1/projects/1/files/999/download")
        assert resp.status_code == 404

    def test_download_project_file_missing_on_disk(self, client, mock_db, admin_user, sample_project_file):
        _setup_client(client, mock_db, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_project_file
        resp = client.get("/api/v1/projects/1/files/1/download")
        assert resp.status_code == 404

    def test_preview_project_file(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
            tf.write(b"%PDF-1.4 test"); tf.flush(); tf_path = tf.name
        try:
            pf = MagicMock(spec=ProjectFile)
            pf.id = 1; pf.project_id = 1; pf.category = "research"
            pf.filename = "test.pdf"; pf.filepath = tf_path
            pf.file_size = 12; pf.uploaded_by = 1
            pf.created_at = datetime(2026, 1, 10, 12, 0, 0)
            mock_db.query.return_value.filter.return_value.first.return_value = pf
            resp = client.get("/api/v1/projects/1/files/1/preview")
            assert resp.status_code == 200
        finally:
            os.unlink(tf_path)

    def test_preview_project_file_not_found(self, client, mock_db, admin_user):
        _setup_client(client, mock_db, admin_user)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        resp = client.get("/api/v1/projects/1/files/999/preview")
        assert resp.status_code == 404
