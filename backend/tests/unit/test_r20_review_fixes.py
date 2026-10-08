# -*- coding: utf-8 -*-
"""R20 审查修复守护测试（修正版）。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

NON_ADMIN = dict(id=9, username="ops", role="user", is_superuser=False, is_active=True,
                 organization_id=1, email="ops@test.com", full_name="普通用户", permissions_list=[])


@pytest.fixture
def non_admin_client(client):
    """登录但非管理角色的客户端（触发各 403 守卫）。"""
    from app.core.security import get_current_user

    user = MagicMock()
    for k, v in NON_ADMIN.items():
        setattr(user, k, v)
    client.app.dependency_overrides[get_current_user] = lambda: user
    yield client
    client.app.dependency_overrides.pop(get_current_user, None)


# ── 未认证 → 401 ──

def test_health_full_requires_auth(client):
    assert client.get("/api/v1/health/full").status_code in (401, 403)


def test_help_articles_requires_auth(client):
    assert client.get("/api/v1/system/help/articles").status_code in (401, 403)


# ── 登录但非管理员 → 403 ──

def test_metrics_business_forbidden(non_admin_client):
    assert non_admin_client.get("/api/v1/metrics/business").status_code == 403


def test_secrets_status_forbidden(non_admin_client):
    assert non_admin_client.get("/api/v1/secrets/status").status_code == 403


def test_system_config_export_forbidden(non_admin_client):
    assert non_admin_client.get("/api/v1/system/config/export/json").status_code == 403


def test_backup_target_forbidden(non_admin_client):
    resp = non_admin_client.put("/api/v1/system/backup/target", json={"target_dir": "D:/tmp"})
    assert resp.status_code == 403


def test_error_report_endpoints_forbidden(non_admin_client):
    assert non_admin_client.get("/api/v1/system/error-reports").status_code == 403
    assert non_admin_client.get("/api/v1/system/error-reports/stats").status_code == 403
    assert non_admin_client.get("/api/v1/system/error-reports/1").status_code == 403


def test_zero_trust_events_forbidden(non_admin_client):
    resp = non_admin_client.post("/api/v1/system/zero-trust/events", json={
        "event_type": "probe", "source": "test", "severity": "low", "message": "x",
    })
    assert resp.status_code == 403


def test_report_template_create_forbidden(non_admin_client):
    resp = non_admin_client.post("/api/v1/report-templates", json={
        "name": "t", "type": "import", "module": "village",
    })
    assert resp.status_code == 403, resp.text[:200]


def test_report_template_update_delete_upload_forbidden(non_admin_client):
    assert non_admin_client.put("/api/v1/report-templates/1", json={"name": "x"}).status_code == 403
    assert non_admin_client.delete("/api/v1/report-templates/1").status_code == 403
    resp = non_admin_client.post(
        "/api/v1/report-templates/1/upload",
        files={"file": ("a.xlsx", b"fake", "application/vnd.ms-excel")},
    )
    assert resp.status_code == 403


# ── 项目任务：无权修改 → 403 ──

def test_project_task_update_forbidden(auth_client, monkeypatch):
    from app.api.v1 import projects as proj_mod

    project = MagicMock()
    monkeypatch.setattr(proj_mod, "_get_project_or_404", lambda db, pid, user: project)
    monkeypatch.setattr(proj_mod, "_can_modify_project", lambda p, u: False)
    resp = auth_client.put("/api/v1/projects/1/tasks/1", json={"title": "x"})
    assert resp.status_code == 403


def test_project_task_delete_forbidden(auth_client, monkeypatch):
    from app.api.v1 import projects as proj_mod

    project = MagicMock()
    monkeypatch.setattr(proj_mod, "_get_project_or_404", lambda db, pid, user: project)
    monkeypatch.setattr(proj_mod, "_can_modify_project", lambda p, u: False)
    resp = auth_client.delete("/api/v1/projects/1/tasks/1")
    assert resp.status_code == 403


# ── 项目导入：overwrite 分支 + 逐行 SAVEPOINT 失败路径（M13/M14） ──

def _call_process(builder):
    """直接驱动 _process_import_rows：两行数据，builder 控制第二行是否抛错。"""
    from app.api.v1.projects import _process_import_rows

    db = MagicMock()
    ws = MagicMock()
    ws.iter_rows.return_value = iter([[None, None], ["项目A", "单位A"], ["项目B", "单位B"]])
    headers = {0: "name", 1: "responsible_unit"}

    def _extract(row, headers_):
        if all(c is None for c in row):
            return {}
        return {"name": row[0], "responsible_unit": row[1]}

    calls = {"n": 0}

    def builder_wrap(db_, data, user):
        calls["n"] += 1
        if calls["n"] == 2:
            raise ValueError("第2行必填缺失")
        return MagicMock()

    with patch("app.api.v1.projects._extract_row_data", side_effect=_extract), \
         patch("app.api.v1.projects._build_import_project", side_effect=builder_wrap):
        created, failed, errors = _process_import_rows(db, ws, 0, headers, MagicMock(), mode="incremental")
    return created, failed, errors, db, calls


def test_import_rows_savepoint_isolates_row_failure():
    """M14：第 2 行构造抛错 → 该行计 failed，其余行照常 created，且不向外抛异常。"""
    created, failed, errors, db, calls = _call_process(builder=None)
    assert calls["n"] == 2
    assert created == 1
    assert failed == 1
    assert errors and errors[0]["name"] == "项目B"
    assert db.begin_nested.called


def test_import_overwrite_softdeletes_scoped_projects():
    """M13：mode=overwrite 会按数据域软删既有活跃项目（分支覆盖）。"""
    from app.main import app

    scoped = MagicMock()
    scoped.update.return_value = 3
    with patch("app.core.data_permission.filter_by_data_scope", return_value=scoped), \
         patch("app.api.v1.projects._check_import_rate_limit", new=AsyncMock()), \
         patch("app.api.v1.projects._parse_import_excel", return_value=MagicMock()), \
         patch("app.api.v1.projects._detect_import_headers", return_value=(1, {0: "name"})), \
         patch("app.api.v1.projects._process_import_rows", return_value=(1, 0, [])), \
         patch("app.api.v1.projects.safe_commit"), \
         patch("app.api.v1.projects.get_client_ip", return_value="127.0.0.1"):
        from app.core.security import get_current_user

        user = MagicMock()
        for k, v in dict(id=1, username="admin", is_superuser=True, is_active=True,
                         organization_id=1, role="admin").items():
            setattr(user, k, v)
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            from fastapi.testclient import TestClient

            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/api/v1/projects/import?mode=overwrite",
                files={"file": ("a.xlsx", b"fake", "application/vnd.ms-excel")},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code in (200, 201), resp.text[:200]
    assert scoped.update.called
