"""R21 深探修复的回归锁定：合同附件必须与「备注」分离。

修复前（探针实证）：
- `POST /fund-lifecycle/contracts/{id}/attachments` 把附件数组 JSON 整体写进
  `fund_contracts.remarks`（用户可见的「备注」列）→ 上传第一个附件即**静默覆盖**
  用户创建合同时填写的备注；
- `PUT /fund-lifecycle/contracts/{id}` 传 `remarks`（编辑备注）→ **清空全部附件**；
- 列表/详情把这段 JSON 当「备注」出站。

另修一处同资源两种口径：`project_id` 可选的合同能创建、能更新，但详情端无条件
`_get_project_or_403` → 恒 400「缺少有效的项目ID」。前端从菜单进入合同管理时
`route.query.project_id` 缺失，这条路径是用户可达的。
"""

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.fund_lifecycle import (
    _contract_attachments,
    _contract_to_dict,
    _parse_attachment_json,
)
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.base import Base
from app.models.fund_lifecycle import FundContract, FundTransferVoucher
from app.models.project import Project

BASE = "/api/v1/fund-lifecycle"
LEGACY = json.dumps([{"url": "http://a/1.pdf", "file_name": "1.pdf"}], ensure_ascii=False)


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
        name="R21Project",
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


def _seed(db, cid=1, project_id=1, remarks=None, attachments_json=None):
    c = FundContract(
        id=cid,
        project_id=project_id,
        contract_no=f"C{cid:03d}",
        contract_name="Contract",
        remarks=remarks,
        attachments_json=attachments_json,
    )
    db.add(c)
    db.flush()
    return c


class TestParseAttachmentJson:
    def test_none_and_empty(self):
        assert _parse_attachment_json(None) == []
        assert _parse_attachment_json("") == []

    def test_invalid_json(self):
        assert _parse_attachment_json("not-json") == []

    def test_json_object_is_not_attachment_list(self):
        assert _parse_attachment_json(json.dumps({"url": "a"})) == []

    def test_filters_entries_without_url(self):
        raw = json.dumps([{"url": "a", "file_name": "f"}, {"no_url": 1}, "x"])
        assert _parse_attachment_json(raw) == [{"url": "a", "file_name": "f"}]


class TestContractAttachmentsHelper:
    def test_prefers_dedicated_column(self):
        c = SimpleNamespace(attachments_json=LEGACY, remarks="正常备注")
        assert _contract_attachments(c) == [{"url": "http://a/1.pdf", "file_name": "1.pdf"}]

    def test_legacy_remarks_read_only_without_db(self):
        c = SimpleNamespace(attachments_json=None, remarks=LEGACY)
        assert _contract_attachments(c) == [{"url": "http://a/1.pdf", "file_name": "1.pdf"}]
        assert c.remarks == LEGACY  # 不给 db 会话时不改写

    def test_legacy_remarks_migrated_and_cleared_with_db(self, db_session):
        c = _seed(db_session, remarks=LEGACY)
        items = _contract_attachments(c, db_session)
        assert items == [{"url": "http://a/1.pdf", "file_name": "1.pdf"}]
        assert c.remarks is None, "搬迁后 remarks 不得继续冒充备注"
        assert json.loads(c.attachments_json) == items

    def test_plain_text_remarks_is_untouched(self, db_session):
        c = _seed(db_session, remarks="甲方要求分三期付款")
        assert _contract_attachments(c, db_session) == []
        assert c.remarks == "甲方要求分三期付款"
        assert c.attachments_json is None

    def test_no_source_returns_empty(self):
        assert _contract_attachments(SimpleNamespace(attachments_json=None, remarks=None)) == []


class TestContractToDictRemarksMasking:
    @staticmethod
    def _contract(remarks):
        return SimpleNamespace(
            id=1,
            fund_id=None,
            project_id=1,
            contract_no="C001",
            contract_name="Contract",
            party_a=None,
            party_b=None,
            contract_amount=0,
            paid_amount=0,
            payment_progress=0,
            sign_date=None,
            deadline=None,
            status="draft",
            remarks=remarks,
            attachments_json=None,
            created_by="admin",
            created_at=None,
        )

    def test_legacy_json_is_not_exposed_as_remarks(self):
        assert _contract_to_dict(self._contract(LEGACY))["remarks"] is None

    def test_normal_remarks_preserved(self):
        assert _contract_to_dict(self._contract("正常备注"))["remarks"] == "正常备注"


class TestUploadAttachmentDoesNotTouchRemarks:
    def test_upload_keeps_user_remarks(self, client, db_session, project):
        _seed(db_session, remarks="甲方要求分三期付款")
        resp = client.post(
            f"{BASE}/contracts/1/attachments",
            json={"url": "http://x/y.pdf", "file_name": "y.pdf", "file_size": 123.0},
        )
        assert resp.status_code == 200

        db_session.expire_all()
        c = db_session.query(FundContract).filter(FundContract.id == 1).first()
        assert c.remarks == "甲方要求分三期付款", "上传附件不得覆盖用户备注"
        assert json.loads(c.attachments_json)[0]["url"] == "http://x/y.pdf"

    def test_editing_remarks_keeps_attachments(self, client, db_session, project):
        _seed(db_session, attachments_json=LEGACY)
        resp = client.put(f"{BASE}/contracts/1", json={"remarks": "改为一次性付款"})
        assert resp.status_code == 200

        resp = client.get(f"{BASE}/contracts/1/attachments")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 1, "改备注不得清空附件"

    def test_second_upload_appends(self, client, db_session, project):
        _seed(db_session)
        client.post(f"{BASE}/contracts/1/attachments", json={"url": "http://x/1.pdf"})
        client.post(f"{BASE}/contracts/1/attachments", json={"url": "http://x/2.pdf"})
        resp = client.get(f"{BASE}/contracts/1/attachments")
        assert resp.json()["data"]["total"] == 2

    def test_upload_defaults_file_name_from_url(self, client, db_session, project):
        _seed(db_session)
        client.post(f"{BASE}/contracts/1/attachments", json={"url": "http://x/scan.pdf"})
        items = client.get(f"{BASE}/contracts/1/attachments").json()["data"]["items"]
        assert items[0]["file_name"] == "scan.pdf"


class TestContractDetailWithoutProject:
    def test_contract_with_no_project_is_readable(self, client, db_session):
        _seed(db_session, cid=7, project_id=None)
        resp = client.get(f"{BASE}/contracts/7")
        assert resp.status_code == 200, "创建放行则详情必须可读（同资源同口径）"
        assert resp.json()["data"]["id"] == 7

    def test_contract_with_project_still_checked(self, client, db_session, project):
        _seed(db_session, cid=8, project_id=999)
        resp = client.get(f"{BASE}/contracts/8")
        assert resp.status_code == 404

    def test_voucher_with_no_project_is_readable(self, client, db_session):
        v = FundTransferVoucher(
            id=5, project_id=None, voucher_no="V005", direction="military_to_local", amount=10.0
        )
        db_session.add(v)
        db_session.flush()
        resp = client.get(f"{BASE}/transfer-vouchers/5")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 5


class TestRelatedForeignKeyValidation:
    """R21：关联 ID 不存在时必须 4xx，不得让 SQLite 外键异常升级为 500。"""

    def test_contract_with_missing_project(self, client, db_session):
        resp = client.post(
            f"{BASE}/contracts",
            json={"contract_no": "C900", "contract_name": "X", "project_id": 999999},
        )
        assert resp.status_code == 404
        assert "项目不存在" in resp.json()["detail"]

    def test_contract_with_missing_fund(self, client, db_session):
        resp = client.post(
            f"{BASE}/contracts",
            json={"contract_no": "C901", "contract_name": "X", "fund_id": 999999},
        )
        assert resp.status_code == 404
        assert "经费不存在" in resp.json()["detail"]

    def test_contract_without_related_ids_is_allowed(self, client, db_session):
        resp = client.post(
            f"{BASE}/contracts", json={"contract_no": "C902", "contract_name": "X"}
        )
        assert resp.status_code == 200

    def test_voucher_with_missing_project(self, client, db_session):
        resp = client.post(
            f"{BASE}/transfer-vouchers",
            json={
                "voucher_no": "V900",
                "direction": "military_to_local",
                "amount": 1.0,
                "project_id": 999999,
            },
        )
        assert resp.status_code == 404
        assert "项目不存在" in resp.json()["detail"]

    def test_voucher_with_missing_fund(self, client, db_session):
        resp = client.post(
            f"{BASE}/transfer-vouchers",
            json={
                "voucher_no": "V901",
                "direction": "military_to_local",
                "amount": 1.0,
                "fund_id": 999999,
            },
        )
        assert resp.status_code == 404
        assert "经费不存在" in resp.json()["detail"]


class TestProjectAccessCheckBranches:
    """`_get_project_or_403` 三条出口（400 缺 ID / 404 不存在 / 403 跨组织）。"""

    def test_missing_project_id(self, db_session):
        from app.api.v1.fund_lifecycle import _get_project_or_403

        with pytest.raises(HTTPException) as exc:
            _get_project_or_403(0, SimpleNamespace(), db_session)
        assert exc.value.status_code == 400

    def test_project_not_found(self, db_session):
        from app.api.v1.fund_lifecycle import _get_project_or_403

        with pytest.raises(HTTPException) as exc:
            _get_project_or_403(999999, SimpleNamespace(), db_session)
        assert exc.value.status_code == 404

    def test_cross_org_denied(self, db_session, project, monkeypatch):
        from app.api.v1 import fund_lifecycle as fl

        monkeypatch.setattr(fl, "check_record_access", lambda *a, **k: False)
        with pytest.raises(HTTPException) as exc:
            fl._get_project_or_403(1, SimpleNamespace(organization_id=2), db_session)
        assert exc.value.status_code == 403

    def test_allowed(self, db_session, project, monkeypatch):
        from app.api.v1 import fund_lifecycle as fl

        monkeypatch.setattr(fl, "check_record_access", lambda *a, **k: True)
        assert fl._get_project_or_403(1, SimpleNamespace(), db_session).id == 1
