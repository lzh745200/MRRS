# -*- coding: utf-8 -*-
"""P2 介质导入守卫：校验和 / 查重 / 台账 的行为锁定。"""

import hashlib
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.models.audit import AuditLog
from app.services.package_import_guard import (
    assert_not_duplicate,
    build_duplicate_message,
    find_previous_import,
    package_checksum,
    record_import,
)


class TestChecksum:
    def test_checksum_matches_sha256(self, tmp_path):
        payload = b"MRRS-PKG" * 200000  # 约 1.6MB，覆盖分块读取
        p = tmp_path / "pkg.zip"
        p.write_bytes(payload)
        assert package_checksum(str(p)) == hashlib.sha256(payload).hexdigest()

    def test_missing_file_returns_empty(self, tmp_path):
        """不可读的包不阻断导入：返回空串，由调用方跳过查重。"""
        assert package_checksum(str(tmp_path / "nope.zip")) == ""

    def test_blank_path_returns_empty(self):
        assert package_checksum("") == ""


class TestFindPreviousImport:
    def test_empty_checksum_returns_none(self):
        assert find_previous_import(MagicMock(), "") is None

    def test_no_record_returns_none(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        assert find_previous_import(db, "abc") is None

    def test_hit_returns_ledger_fields(self):
        row = AuditLog(
            username="admin",
            created_at=datetime(2026, 10, 23, 8, 0, 0),
            resource_type="data_package",
            new_value={"imported_at": "2026-10-23T08:00:00", "file_name": "a.zip"},
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
        info = find_previous_import(db, "abc")
        assert info["username"] == "admin"
        assert info["package_type"] == "data_package"
        assert info["file_name"] == "a.zip"
        assert info["created_at"] == "2026-10-23T08:00:00"

    def test_hit_with_non_dict_payload_falls_back(self):
        row = AuditLog(username="u", created_at=None, resource_type=None, new_value="raw")
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
        info = find_previous_import(db, "abc")
        assert info["username"] == "u"
        assert info["file_name"] == ""
        assert info["created_at"] is None


class TestJsonSafeBranches:
    def test_datetime_payload_falls_back_to_isoformat(self):
        row = AuditLog(
            username="u",
            created_at=datetime(2026, 10, 23, 9, 30, 0),
            resource_type="data_package",
            new_value={},
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
        info = find_previous_import(db, "abc")
        assert info["created_at"] == "2026-10-23T09:30:00"

    def test_unknown_payload_type_is_stringified(self):
        row = AuditLog(
            username="u",
            created_at=None,
            resource_type="data_package",
            new_value={"imported_at": object()},
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
        info = find_previous_import(db, "abc")
        assert isinstance(info["created_at"], str)


class TestDuplicateMessage:
    def test_message_contains_time_and_user(self):
        msg = build_duplicate_message(
            {"created_at": "2026-10-23T08:00:00", "username": "admin"}
        )
        assert "2026-10-23T08:00:00" in msg
        assert "admin" in msg
        assert "force=true" in msg

    def test_message_defaults_when_fields_missing(self):
        msg = build_duplicate_message({})
        assert "未知时间" in msg
        assert "未知操作人" in msg


class TestRecordImport:
    def test_writes_audit_entry(self, monkeypatch):
        captured = {}

        def _fake_log(**kwargs):
            captured.update(kwargs)

        from app.services import package_import_guard as guard

        monkeypatch.setattr(guard.AuditLogger, "log", staticmethod(_fake_log))

        record_import(
            MagicMock(),
            checksum="d" * 64,
            package_type="data_package",
            user_id=7,
            username="admin",
            file_name="a.zip",
            source_org_code="520000",
            record_count=12,
        )

        assert captured["resource_id"] == "d" * 64
        assert captured["resource_type"] == "data_package"
        assert captured["username"] == "admin"
        assert captured["details"]["record_count"] == 12
        assert captured["details"]["source_org_code"] == "520000"
        assert captured["details"]["imported_at"]

    def test_swallows_audit_failure(self, monkeypatch):
        """台账（审计）写入失败必须被吞掉，不得阻断导入流程。

        W27：原用例只"跑通不断言"（零 assert），被零断言棘轮门禁判为违规。
        这里补上真正要锁定的行为：**审计确实被尝试调用过**（失败被吞，
        而不是压根没写），且导入调用正常返回。
        """
        calls = []

        def _boom(**kwargs):
            calls.append(kwargs)
            raise RuntimeError("db down")

        from app.services import package_import_guard as guard

        monkeypatch.setattr(guard.AuditLogger, "log", staticmethod(_boom))
        # 关键：调用本身不抛异常（台账故障被吞），且审计确实被尝试写过一次
        record_import(MagicMock(), checksum="x", package_type="data_package")

        assert len(calls) == 1, "审计写入未被尝试（静默跳过而非失败被吞）"


class TestAssertNotDuplicate:
    """端点唯一入口：查重即抛 409，其余返回校验和。"""

    def _db_returning(self, row):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = row
        return db

    def test_unreadable_package_skips_check(self, tmp_path):
        assert assert_not_duplicate(self._db_returning(None), str(tmp_path / "gone.zip")) == ""

    def test_first_import_returns_checksum(self, tmp_path):
        p = tmp_path / "pkg.zip"
        p.write_bytes(b"MRRS-PKG")
        checksum = assert_not_duplicate(self._db_returning(None), str(p))
        assert checksum == package_checksum(str(p))

    def test_duplicate_without_force_raises_409(self, tmp_path):
        from fastapi import HTTPException

        p = tmp_path / "pkg.zip"
        p.write_bytes(b"MRRS-PKG")
        row = AuditLog(
            username="admin",
            created_at=datetime(2026, 10, 23, 8, 0, 0),
            resource_type="data_package",
            new_value={"imported_at": "2026-10-23T08:00:00"},
        )
        with pytest.raises(HTTPException) as exc:
            assert_not_duplicate(self._db_returning(row), str(p))
        assert exc.value.status_code == 409
        assert "force=true" in exc.value.detail

    def test_duplicate_with_force_passes(self, tmp_path):
        p = tmp_path / "pkg.zip"
        p.write_bytes(b"MRRS-PKG")
        row = AuditLog(
            username="admin",
            created_at=None,
            resource_type="data_package",
            new_value={},
        )
        checksum = assert_not_duplicate(self._db_returning(row), str(p), force=True)
        assert checksum == package_checksum(str(p))
