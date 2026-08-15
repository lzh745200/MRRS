"""年度考核闭环(T3.4): evaluate 后生成复核审批任务"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _superuser():
    return SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)


def test_evaluate_creates_review_task():
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    # 评估结果
    eval_result = {"status": "ok", "score": 88.5, "total_score": 88.5}

    review_task = SimpleNamespace(id=42)

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: _superuser()
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch(
            "app.services.effectiveness_service.EffectivenessService.evaluate_village",
            return_value=eval_result,
        ):
            with patch(
                "app.services.approval_workflow_service.ApprovalWorkflowService.submit_approval",
                return_value=review_task,
            ) as mk_submit:
                resp = client.post(
                    "/api/v1/effectiveness/evaluate",
                    json={"village_id": 3, "year": 2026},
                    headers={"X-Internal-Backup": "k"},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_task_id"] == 42
        assert data["review_status"] == "pending_review"
        mk_submit.assert_called_once_with(
            entity_type="assessment",
            entity_id=3,
            submitter_id=1,
            title="年度考核复核-村3-2026年",
            change_data={"year": 2026, "score": 88.5},
        )
    finally:
        app.dependency_overrides.clear()


def test_evaluate_without_workflow_ok():
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user

    mock_db = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: _superuser()
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch(
            "app.services.effectiveness_service.EffectivenessService.evaluate_village",
            return_value={"status": "ok", "score": 90},
        ):
            with patch(
                "app.services.approval_workflow_service.ApprovalWorkflowService.submit_approval",
                return_value=None,
            ):
                resp = client.post(
                    "/api/v1/effectiveness/evaluate",
                    json={"village_id": 4, "year": 2026},
                    headers={"X-Internal-Backup": "k"},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert "review_task_id" not in data
    finally:
        app.dependency_overrides.clear()


def test_evaluate_submit_exception_still_ok():
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user

    mock_db = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: _superuser()
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch(
            "app.services.effectiveness_service.EffectivenessService.evaluate_village",
            return_value={"status": "ok", "score": 91},
        ):
            with patch(
                "app.services.approval_workflow_service.ApprovalWorkflowService.submit_approval",
                side_effect=RuntimeError("wf down"),
            ):
                resp = client.post(
                    "/api/v1/effectiveness/evaluate",
                    json={"village_id": 5, "year": 2026},
                    headers={"X-Internal-Backup": "k"},
                )
        assert resp.status_code == 200
        assert "review_task_id" not in resp.json()
    finally:
        app.dependency_overrides.clear()


def test_evaluate_requires_admin():
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user

    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=2, username="u", role="user", is_superuser=False
    )
    client = TestClient(app, raise_server_exceptions=False)
    try:
        resp = client.post(
            "/api/v1/effectiveness/evaluate",
            json={"village_id": 1, "year": 2026},
            headers={"X-Internal-Backup": "k"},
        )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_evaluate_reuses_existing_pending_review_task():
    """幂等：同村同年度已有待处理复核任务时复用，不重复创建"""
    from app.main import app
    from app.core.database import get_db
    from app.core.security import get_current_user

    mock_db = MagicMock()
    existing = SimpleNamespace(id=77, change_data={"year": 2026})
    mock_db.query.return_value.filter.return_value.all.return_value = [existing]

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: _superuser()
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with patch(
            "app.services.effectiveness_service.EffectivenessService.evaluate_village",
            return_value={"status": "ok", "total_score": 90.0},
        ):
            with patch(
                "app.services.approval_workflow_service.ApprovalWorkflowService.submit_approval"
            ) as mk_submit:
                resp = client.post(
                    "/api/v1/effectiveness/evaluate",
                    json={"village_id": 3, "year": 2026},
                    headers={"X-Internal-Backup": "k"},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_task_id"] == 77
        assert data["review_status"] == "pending_review"
        mk_submit.assert_not_called()
    finally:
        app.dependency_overrides.clear()
