"""Targeted coverage tests for fund_lifecycle.py uncovered lines.

Covers:
- TransferVoucherCreate/Update _empty_date_to_none validators (645, 662-664)
- ContractCreate/Update _empty_date_to_none validators (938, 958)
- approve_settlement idempotency guard (1557)
- batch_health non-empty project_ids (1678, 1680-1681)
- upload_contract_attachment (2301-2324)
- list_contract_attachments (2334-2341)
- _contract_attachments helper (2346-2355)
"""

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.base import Base
from app.models.fund_lifecycle import FundContract, FundSettlement, SettlementStatus
from app.models.project import Project
from app.api.v1.fund_lifecycle import (
    ContractCreate,
    ContractUpdate,
    TransferVoucherCreate,
    TransferVoucherUpdate,
    _contract_attachments,
)

BASE = "/api/v1/fund-lifecycle"


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db_session):
    from app.main import app

    def _get_db():
        yield db_session

    admin = Mock()
    admin.id = 1
    admin.username = "admin"
    admin.role = "admin"
    admin.is_superuser = True
    admin.is_active = True
    admin.permissions_list = ["*"]
    admin.organization_id = 1
    admin.email = "admin@test.com"
    admin.full_name = "Admin"

    async def _get_current_user():
        return admin

    _original = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user

    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides = _original


@pytest.fixture
def project(db_session):
    p = Project(
        id=1,
        name="TestProject",
        type="infrastructure",
        description="desc",
        objectives="obj",
        budget=Decimal("1000.00"),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        leader="Leader",
        responsible_unit="Unit",
        status="in_progress",
        progress=50.0,
        organization_id=1,
    )
    db_session.add(p)
    db_session.flush()
    return p


class TestEmptyDateValidators:
    def test_transfer_create_empty_date(self):
        v = TransferVoucherCreate(
            voucher_no="V001", direction="military_to_local", amount=10.0, transfer_date=""
        )
        assert v.transfer_date is None

    def test_transfer_create_valid_date(self):
        v = TransferVoucherCreate(
            voucher_no="V001", direction="military_to_local", amount=10.0, transfer_date="2025-06-01"
        )
        assert v.transfer_date == date(2025, 6, 1)

    def test_transfer_update_empty_date(self):
        v = TransferVoucherUpdate(transfer_date="")
        assert v.transfer_date is None

    def test_transfer_update_valid_date(self):
        v = TransferVoucherUpdate(transfer_date="2025-06-01")
        assert v.transfer_date == date(2025, 6, 1)

    def test_contract_create_empty_dates(self):
        c = ContractCreate(contract_no="C001", contract_name="N", sign_date="", deadline="")
        assert c.sign_date is None
        assert c.deadline is None

    def test_contract_update_empty_date(self):
        c = ContractUpdate(sign_date="")
        assert c.sign_date is None

    def test_contract_update_valid_date(self):
        c = ContractUpdate(sign_date="2025-06-01")
        assert c.sign_date == date(2025, 6, 1)


class TestApproveSettlementGuard:
    def test_non_draft_status_rejected(self, client, project, db_session):
        s = FundSettlement(id=1, project_id=project.id, settlement_no="JS-001",
                           status=SettlementStatus.APPROVED.value)
        db_session.add(s)
        db_session.flush()
        resp = client.post(f"{BASE}/settlement/1/approve")
        assert resp.status_code == 400
        assert "不可审批" in resp.json()["detail"]


class TestBatchHealth:
    def test_non_empty_project_ids(self, client, project):
        resp = client.post(f"{BASE}/health/batch", json={"project_ids": [project.id]})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["project_id"] == project.id


class TestContractAttachmentsEndpoint:
    def _seed_contract(self, db_session, project, remarks=None):
        c = FundContract(id=1, project_id=project.id, contract_no="C001",
                         contract_name="Contract", remarks=remarks)
        db_session.add(c)
        db_session.flush()
        return c

    def test_upload_success(self, client, project, db_session):
        self._seed_contract(db_session, project)
        resp = client.post(
            f"{BASE}/contracts/1/attachments",
            json={"url": "http://x/y.pdf", "file_name": "y.pdf", "file_size": 123.0},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["url"] == "http://x/y.pdf"

    def test_upload_not_found(self, client):
        resp = client.post(
            f"{BASE}/contracts/999/attachments",
            json={"url": "http://x/y.pdf"},
        )
        assert resp.status_code == 404

    def test_list_success(self, client, project, db_session):
        self._seed_contract(db_session, project)
        client.post(f"{BASE}/contracts/1/attachments", json={"url": "http://x/y.pdf"})
        resp = client.get(f"{BASE}/contracts/1/attachments")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["url"] == "http://x/y.pdf"

    def test_list_not_found(self, client):
        resp = client.get(f"{BASE}/contracts/999/attachments")
        assert resp.status_code == 404

    def test_list_with_remarks_roundtrip(self, client, project, db_session):
        remarks = json.dumps([{"url": "http://a/1.pdf", "file_name": "1.pdf"}], ensure_ascii=False)
        self._seed_contract(db_session, project, remarks=remarks)
        resp = client.get(f"{BASE}/contracts/1/attachments")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert items[0]["url"] == "http://a/1.pdf"


class TestContractAttachmentsHelper:
    def test_none_remarks(self):
        assert _contract_attachments(SimpleNamespace(remarks=None)) == []

    def test_empty_remarks(self):
        assert _contract_attachments(SimpleNamespace(remarks="")) == []

    def test_valid_json_list_filtered(self):
        remarks = json.dumps([{"url": "a", "file_name": "f"}, {"no_url": 1}])
        result = _contract_attachments(SimpleNamespace(remarks=remarks))
        assert result == [{"url": "a", "file_name": "f"}]

    def test_invalid_json(self):
        assert _contract_attachments(SimpleNamespace(remarks="not-json")) == []

    def test_json_not_list(self):
        assert _contract_attachments(SimpleNamespace(remarks=json.dumps({"url": "a"}))) == []
