"""R63：恢复码服务/端点覆盖补充分支。"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.models.machine_recovery_code import MachineRecoveryCode
from app.services.recovery_code_service import (
    PURPOSE_PASSWORD_RESET,
    RecoveryCodeService,
)
from app.utils.time_utils import utcnow


@pytest.fixture(autouse=True)
def _no_camel_to_snake():
    with patch(
        "app.middleware.camel_to_snake._convert_keys",
        side_effect=lambda obj, converter: (obj, False),
    ):
        yield


def test_check_rejects_unknown_purpose(real_db_session):
    assert (
        RecoveryCodeService.check(
            real_db_session, "MC-X", "12345678", "unknown", consume=True
        )
        is False
    )


def test_check_rejects_empty_hash(real_db_session):
    real_db_session.add(
        MachineRecoveryCode(
            machine_code="MC-EMPTY",
            code_hash="",
            purpose=PURPOSE_PASSWORD_RESET,
            expires_at=utcnow() + timedelta(minutes=5),
        )
    )
    real_db_session.commit()
    assert (
        RecoveryCodeService.check(
            real_db_session, "MC-EMPTY", "12345678", PURPOSE_PASSWORD_RESET, consume=True
        )
        is False
    )


def test_issue_is_case_sensitive_purpose(real_db_session):
    with pytest.raises(ValueError):
        RecoveryCodeService.issue(real_db_session, "MC-Y", purpose="PASSWORD_RESET")


class TestRecoveryEndpointBranches:
    def test_rate_limited(self, client):
        with patch("app.api.v1.machine_code._client_is_loopback", return_value=True):
            with patch(
                "app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=False)
            ):
                resp = client.post("/api/v1/machine-code/recovery-code", json={})
        assert resp.status_code == 429
        assert "过于频繁" in resp.json()["detail"]

    def test_admin_recovery_purpose_passes_to_service(self, client):
        with patch("app.api.v1.machine_code._client_is_loopback", return_value=True):
            with patch(
                "app.api.v1.machine_code.check_rate_limit", AsyncMock(return_value=True)
            ):
                with patch(
                    "app.api.v1.machine_code.MachineCodeService.get_machine_code",
                    return_value="MC-ADMIN",
                ):
                    with patch(
                        "app.api.v1.machine_code.RecoveryCodeService.issue",
                        return_value=("87654321", utcnow()),
                    ) as issue:
                        resp = client.post(
                            "/api/v1/machine-code/recovery-code",
                            json={"purpose": "admin_recovery"},
                        )
        assert resp.status_code == 200
        assert issue.call_args.kwargs["purpose"] == "admin_recovery"
