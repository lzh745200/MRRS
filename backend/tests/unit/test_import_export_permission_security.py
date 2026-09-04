"""导入导出与权限包安全红线回归测试（Task #7）。

覆盖三处军事审计红线缺陷的最小复现回归：

* **S2**（数据隔离）：部门级管理员（role=admin, is_superuser=False → OWN_DEPT）
  通过 export_funds/export_schools/export_projects 导出时，只能拿到本组织
  数据，跨组织记录必须被过滤；同时（M1）软删记录不得出现在导出文件。
* **S4**（完整性校验绕过）：篡改权限包（校验和不匹配）后，直接调用
  confirm_import 必须被拒绝（integrity_failed），且不触发破坏性
  _clear_existing_data、不落库；API 层将 integrity_failed 映射为 400。
* **S1**（弱加密升级 + 向后兼容）：新格式走 PBKDF2 加解密；历史旧格式
  （裸 SHA-256 派生的 Fernet token）仍可被 looks_encrypted 识别并解密。
"""
import base64
import csv
import hashlib
import io
import json
import os
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.models.organization import Organization
from app.models.project import Fund, Project
from app.models.rbac import RbacRole
from app.models.school import School
from app.models.user import User
from app.services.permission_package_service import PermissionPackageService
from app.utils import package_crypto
from app.utils.package_crypto import decrypt_bytes, encrypt_bytes, looks_encrypted

BASE = "/api/v1/export"


def _csv_ids(content: bytes):
    """解析 CSV 导出内容，返回其中出现的 ID 集合（首列为 'ID'）。"""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    ids = set()
    for row in reader:
        val = row.get("ID")
        if val not in (None, ""):
            ids.add(int(val))
    return ids


# ══════════════════════════════════════════════════════════════════════
# S2 · 数据隔离红线：部门级管理员导出不得跨组织泄漏
# ══════════════════════════════════════════════════════════════════════
class TestS2ExportDataIsolation:
    """部门 admin（OWN_DEPT）导出资金/学校/项目仅可见本组织在用记录。"""

    def _seed(self, db):
        """播种两个组织：org1（当前管理员所属）与 org2（他组织）。

        每个模型均含：org1 在用记录、org1 软删记录、org2 在用记录。
        返回 (org1, records_dict)，records_dict[model] = (own_active, own_deleted, other_active)。
        """
        org1 = Organization(name="Org One", code="SEC_ORG1")
        org2 = Organization(name="Org Two", code="SEC_ORG2")
        db.add_all([org1, org2])
        db.commit()
        db.refresh(org1)
        db.refresh(org2)

        funds = [
            Fund(name="Fund O1 Active", organization_id=org1.id, created_by=1, is_active=True),
            Fund(name="Fund O1 Deleted", organization_id=org1.id, created_by=1, is_active=False),
            Fund(name="Fund O2 Active", organization_id=org2.id, created_by=1, is_active=True),
        ]
        schools = [
            School(name="School O1 Active", code="SEC_S1", organization_id=org1.id,
                   created_by=1, is_active=True),
            School(name="School O1 Deleted", code="SEC_S1D", organization_id=org1.id,
                   created_by=1, is_active=False),
            School(name="School O2 Active", code="SEC_S2", organization_id=org2.id,
                   created_by=1, is_active=True),
        ]
        projects = [
            Project(name="Project O1 Active", code="SEC_P1", organization_id=org1.id,
                    created_by=1, is_active=True),
            Project(name="Project O1 Deleted", code="SEC_P1D", organization_id=org1.id,
                    created_by=1, is_active=False),
            Project(name="Project O2 Active", code="SEC_P2", organization_id=org2.id,
                    created_by=1, is_active=True),
        ]
        db.add_all(funds + schools + projects)
        db.commit()
        for r in funds + schools + projects:
            db.refresh(r)
        return org1, {"funds": funds, "schools": schools, "projects": projects}

    def _dept_admin(self, org1_id):
        """部门级管理员：role=admin 但 is_superuser=False → OWN_DEPT 范围。"""
        return Mock(
            id=1, username="dept_admin", role="admin", is_superuser=False,
            is_active=True, permissions_list=["*"], organization_id=org1_id,
        )

    @pytest.mark.parametrize("endpoint,key", [
        ("/funds", "funds"),
        ("/schools", "schools"),
        ("/projects", "projects"),
    ])
    def test_export_scoped_to_own_dept(self, client_with_db, endpoint, key):
        from app.core.security import get_current_user

        client, db = client_with_db
        org1, records = self._seed(db)
        own_active, own_deleted, other_active = records[key]

        client.app.dependency_overrides[get_current_user] = lambda: self._dept_admin(org1.id)

        resp = client.get(f"{BASE}{endpoint}", params={"format": "csv"})
        assert resp.status_code == 200, resp.text[:300]
        ids = _csv_ids(resp.content)

        # S2：本组织在用记录可见
        assert own_active.id in ids, f"{endpoint}: 本组织在用记录应出现在导出中"
        # S2 红线：他组织记录必须被过滤，杜绝跨组织数据泄漏
        assert other_active.id not in ids, f"{endpoint}: 跨组织(他部门)记录泄漏！违反数据隔离红线"
        # M1：本组织软删记录不得出现在导出文件
        assert own_deleted.id not in ids, f"{endpoint}: 软删记录泄漏！与列表页口径不一致"


# ══════════════════════════════════════════════════════════════════════
# S4 · 完整性校验绕过：confirm 阶段必须复验校验和并拒绝落库
# ══════════════════════════════════════════════════════════════════════
def _make_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine), engine


def _seed_source(Session):
    """源机：播种一个自定义角色 + 用户，供导出权限包。"""
    db = Session()
    alice = User(id=7, username="alice", full_name="Alice", hashed_password="x",
                 role="user", is_active=True)
    db.add(alice)
    db.flush()
    role = RbacRole(name="village_officer", description="村官", is_system=False,
                    is_active=True, priority=50)
    db.add(role)
    db.commit()
    db.close()


class TestS4ConfirmChecksumReverify:
    def test_tampered_package_rejected_in_confirm(self, tmp_path):
        """篡改包直接 confirm 必须被拒（integrity_failed），且不破坏既有数据。"""
        # ── 源机导出合法权限包 ──
        src_session, src_eng = _make_db()
        _seed_source(src_session)
        svc_src = PermissionPackageService(src_session())
        exported = svc_src.export_package(description="S4 回归")
        assert exported["success"] is True, exported.get("errors")
        src_zip = exported["file_path"]

        # ── 篡改 data/roles.json（不更新 manifest.content_checksum）→ 重打包 ──
        tampered = str(tmp_path / "tampered_s4.zip")
        with zipfile.ZipFile(src_zip, "r") as zin, \
                zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                data = zin.read(item)
                if item == "data/roles.json":
                    roles = json.loads(data.decode("utf-8"))
                    roles[0]["priority"] = 9999  # 篡改
                    data = json.dumps(roles).encode("utf-8")
                zout.writestr(item, data)

        # ── 目标机：预置一个自定义角色，overwrite 模式若执行会被 _clear 删除 ──
        tgt_session, tgt_eng = _make_db()
        tgt_db = tgt_session()
        pre_existing = RbacRole(name="pre_existing_role", description="既有", is_system=False,
                                is_active=True, priority=10)
        tgt_db.add(pre_existing)
        tgt_db.commit()

        try:
            svc_tgt = PermissionPackageService(tgt_db)
            result = svc_tgt.confirm_import(tampered, overwrite_existing=True)

            # S4：确认阶段复验校验和 → 拒绝落库
            assert result["success"] is False
            assert result.get("integrity_failed") is True
            assert any("校验" in e for e in result.get("errors", []))

            # 破坏性清空未发生：既有自定义角色仍在
            tgt_db.expire_all()
            still = tgt_db.query(RbacRole).filter(
                RbacRole.name == "pre_existing_role").first()
            assert still is not None, "S4 失败：_clear_existing_data 在校验前已破坏既有权限"

            # 篡改包的角色未落库
            leaked = tgt_db.query(RbacRole).filter(
                RbacRole.name == "village_officer").first()
            assert leaked is None, "S4 失败：被拒的篡改包数据仍落库"
        finally:
            tgt_db.close()
            tgt_eng.dispose()
            src_eng.dispose()
            for p in (src_zip, tampered):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def test_untampered_package_confirm_still_passes(self, tmp_path):
        """未篡改包 confirm 应通过校验（防误伤：S4 不得阻断合法导入）。"""
        src_session, src_eng = _make_db()
        _seed_source(src_session)
        svc_src = PermissionPackageService(src_session())
        exported = svc_src.export_package(description="S4 正向")
        src_zip = exported["file_path"]

        tgt_session, tgt_eng = _make_db()
        tgt_db = tgt_session()
        try:
            svc_tgt = PermissionPackageService(tgt_db)
            result = svc_tgt.confirm_import(src_zip, overwrite_existing=True)
            assert result.get("integrity_failed") is not True
            assert result["success"] is True, result.get("errors")
        finally:
            tgt_db.close()
            tgt_eng.dispose()
            src_eng.dispose()
            try:
                os.unlink(src_zip)
            except OSError:
                pass

    def test_api_maps_integrity_failed_to_400(self, tmp_path):
        """API 层：service 返回 integrity_failed → HTTP 400（区别于服务端 500）。"""
        import app.api.v1.permission_package as pp
        from fastapi import HTTPException

        (tmp_path / "pkg.zip").write_bytes(b"PK")
        admin = SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)
        req = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
        body = SimpleNamespace(overwrite_existing=True, mode=None)

        with patch.object(pp, "PermissionPackageService") as svc_cls, \
                patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path):
            svc_cls.return_value.confirm_import.return_value = {
                "success": False,
                "message": "内容校验失败，权限包已损坏或被篡改，拒绝导入",
                "integrity_failed": True,
            }
            with pytest.raises(HTTPException) as exc_info:
                pp.confirm_import_permission_package(
                    "pkg.zip", body, admin, MagicMock(), req
                )
        assert exc_info.value.status_code == 400

    async def test_preview_failure_deletes_uploaded_file(self, tmp_path):
        """S4b：预览 success:false → 上传文件被删除（零磁盘残留）。

        杜绝旧缺陷：预览被拒（如校验和不匹配）时文件仍留在上传目录，
        攻击者可直接 POST /confirm/{file_name} 绕过预览落库。
        """
        import app.api.v1.permission_package as pp

        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(side_effect=[b"PK", b""]))
        req = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
        admin = SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True)

        with patch.object(pp, "PermissionPackageService") as svc_cls, \
                patch("app.utils.paths.get_runtime_uploads_path", return_value=tmp_path):
            svc_cls.return_value.import_package.return_value = {
                "success": False,
                "errors": ["内容校验和不匹配：权限包已损坏或被篡改，拒绝导入"],
                "message": "内容校验失败，请重新导出权限包",
            }
            resp = await pp.import_permission_package(req, file, admin, MagicMock())

        # 预览失败仍以 JSON 返回 success:false
        assert resp.status_code == 200
        assert json.loads(resp.body)["success"] is False
        # 关键：所有拒绝路径零磁盘残留
        assert not (tmp_path / "pkg.zip").exists(), "S4b 失败：预览被拒后上传文件未删除"


# ══════════════════════════════════════════════════════════════════════
# S1 · 弱加密升级（PBKDF2）+ 向后兼容（旧 SHA-256 格式仍可解密）
# ══════════════════════════════════════════════════════════════════════
def _legacy_sha256_token(data: bytes, password: str) -> bytes:
    """构造历史旧格式密文：裸 SHA-256 派生 Fernet 密钥加密（无魔术包头）。"""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest)).encrypt(data)


class TestS1CryptoUpgradeAndBackwardCompat:
    def test_new_format_uses_pbkdf2_and_roundtrips(self):
        """新格式：encrypt_bytes 产出带魔术包头的 PBKDF2 密文，可正确解密。"""
        data = b"RBAC sensitive payload \xe6\x9d\x83\xe9\x99\x90"
        pw = "Str0ng-Passphrase!"
        enc = encrypt_bytes(data, pw)

        # 带魔术包头（新格式标记）
        assert enc.startswith(package_crypto._MAGIC)
        assert looks_encrypted(enc) is True
        # 正确密码可解密
        assert decrypt_bytes(enc, pw) == data
        # 相同明文/密码两次加密因随机 salt 而密文不同（非确定性）
        assert encrypt_bytes(data, pw) != enc

    def test_new_format_wrong_password_raises_invalid_token(self):
        data = b"payload"
        enc = encrypt_bytes(data, "right-password")
        with pytest.raises(InvalidToken):
            decrypt_bytes(enc, "wrong-password")

    def test_legacy_sha256_package_still_decryptable(self):
        """向后兼容：历史旧格式（裸 SHA-256 Fernet token）仍可识别并解密。"""
        data = b"legacy RBAC package bytes"
        pw = "legacy-pass"
        legacy = _legacy_sha256_token(data, pw)

        # 旧格式无魔术包头，但仍被识别为加密
        assert not legacy.startswith(package_crypto._MAGIC)
        assert looks_encrypted(legacy) is True
        # 旧格式仍可解密（不破坏现有加密包导入）
        assert decrypt_bytes(legacy, pw) == data

    def test_legacy_wrong_password_raises_invalid_token(self):
        legacy = _legacy_sha256_token(b"x", "right")
        with pytest.raises(InvalidToken):
            decrypt_bytes(legacy, "wrong")

    def test_looks_encrypted_rejects_plaintext_zip_and_empty(self):
        """明文 ZIP 与空字节不应被误判为加密。"""
        assert looks_encrypted(b"") is False
        assert looks_encrypted(b"PK\x03\x04 not really encrypted") is False

    @pytest.mark.parametrize("truncated", [
        package_crypto._MAGIC,                                       # 只有魔术头
        package_crypto._MAGIC + b"\x00\x00",                         # 迭代数字段被截断
        package_crypto._MAGIC + b"\x00\x01\x86\xa0",                 # 缺整个 salt
        package_crypto._MAGIC + b"\x00\x01\x86\xa0" + b"\x01" * 10,  # salt 不足 32 字节
    ])
    def test_truncated_new_format_raises_invalid_token(self, truncated):
        """截断/损坏的新格式包必须抛 InvalidToken，不得让 struct.error 逃逸。

        历史缺陷：_parse_header 无长度校验，struct.unpack 对不足 4 字节的切片抛
        struct.error；该异常发生在 decrypt_bytes 的 try 块之前，逃过 InvalidToken
        归一化，使上传截断文件得到未分类 HTTP 500，而非调用方按 InvalidToken
        统一处理的「密码错误或包已损坏」。
        """
        assert len(truncated) < package_crypto._HEADER_LEN
        # 仍被识别为加密包，因而确实会走进 decrypt_bytes 的新格式分支
        assert looks_encrypted(truncated) is True
        with pytest.raises(InvalidToken):
            decrypt_bytes(truncated, "any-password")
