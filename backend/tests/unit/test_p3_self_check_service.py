# -*- coding: utf-8 -*-
"""P3 系统自检：六项体检的判定逻辑。"""

from unittest.mock import MagicMock, patch

from app.models.organization import Organization
from app.services.self_check_service import (
    LEVEL_ERROR,
    LEVEL_OK,
    LEVEL_WARN,
    collect_self_check,
)


def _org(oid, name, code, level, parent_id=None):
    org = Organization()
    org.id = oid
    org.name = name
    org.code = code
    org.level = level
    org.parent_id = parent_id
    org.is_active = True
    return org


def _db_with(orgs=None, users=None, audits=None):
    """构造按模型分流的 mock 会话。"""
    db = MagicMock()

    def _query(model):
        q = MagicMock()
        chain = q.filter.return_value
        chain.all.return_value = orgs if model is Organization else []
        chain.count.return_value = 0
        q.all.return_value = orgs or []
        return q

    db.query.side_effect = _query
    return db


class TestOrgCodeCheck:
    def test_all_good(self):
        db = _db_with(orgs=[
            _org(1, "贵州省", "520000", "1"),
            _org(2, "贵阳市", "520100", "2", 1),
        ])
        result = collect_self_check(db)
        code_check = next(c for c in result["checks"] if c["name"] == "组织单位码")
        assert code_check["level"] == LEVEL_OK
        assert result["status"] == LEVEL_OK

    def test_missing_code_warns(self):
        db = _db_with(orgs=[_org(1, "某单位", "", "1")])
        result = collect_self_check(db)
        code_check = next(c for c in result["checks"] if c["name"] == "组织单位码")
        assert code_check["level"] == LEVEL_WARN
        assert "缺失 1" in code_check["detail"]

    def test_invalid_code_is_error(self):
        db = _db_with(orgs=[_org(1, "某单位", "5200", "1")])
        result = collect_self_check(db)
        code_check = next(c for c in result["checks"] if c["name"] == "组织单位码")
        assert code_check["level"] == LEVEL_ERROR
        assert result["status"] == LEVEL_ERROR

    def test_level_mismatch_is_error(self):
        # 520100 是市州级，但 level 写成省级
        db = _db_with(orgs=[_org(1, "某单位", "520100", "1")])
        result = collect_self_check(db)
        code_check = next(c for c in result["checks"] if c["name"] == "组织单位码")
        assert code_check["level"] == LEVEL_ERROR
        assert "层级不符" in code_check["detail"]

    def test_duplicate_code_detected(self):
        db = _db_with(orgs=[
            _org(1, "甲", "520000", "1"),
            _org(2, "乙", "520000", "1"),
        ])
        result = collect_self_check(db)
        code_check = next(c for c in result["checks"] if c["name"] == "组织单位码")
        assert "重复" in code_check["detail"]


class TestHierarchyCheck:
    def test_valid_hierarchy(self):
        db = _db_with(orgs=[
            _org(1, "贵州省", "520000", "1"),
            _org(2, "贵阳市", "520100", "2", 1),
        ])
        result = collect_self_check(db)
        check = next(c for c in result["checks"] if c["name"] == "组织层级")
        assert check["level"] == LEVEL_OK

    def test_root_not_province_warns(self):
        db = _db_with(orgs=[_org(1, "某市", "520100", "2")])
        result = collect_self_check(db)
        check = next(c for c in result["checks"] if c["name"] == "组织层级")
        assert check["level"] == LEVEL_WARN
        assert "根组织非省级" in check["detail"]

    def test_cross_level_parent_warns(self):
        # 县级直接挂省级（跨级）
        db = _db_with(orgs=[
            _org(1, "贵州省", "520000", "1"),
            _org(2, "南明区", "520102", "3", 1),
        ])
        result = collect_self_check(db)
        check = next(c for c in result["checks"] if c["name"] == "组织层级")
        assert check["level"] == LEVEL_WARN
        assert "父级与子级不相邻" in check["detail"]

    def test_missing_parent_ignored(self):
        db = _db_with(orgs=[_org(2, "孤儿", "520100", "2", 999)])
        result = collect_self_check(db)
        check = next(c for c in result["checks"] if c["name"] == "组织层级")
        assert check["level"] == LEVEL_OK

    def test_unknown_level_skipped(self):
        db = _db_with(orgs=[_org(1, "无层级", "520000", None)])
        result = collect_self_check(db)
        check = next(c for c in result["checks"] if c["name"] == "组织层级")
        assert check["level"] == LEVEL_OK


class TestUserChecks:
    def test_no_pending_no_locked(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.count.return_value = 0
        result = collect_self_check(db)
        names = {c["name"]: c for c in result["checks"]}
        assert names["待审核账号"]["level"] == LEVEL_OK
        assert names["账号锁定"]["level"] == LEVEL_OK

    def test_pending_and_locked_warn(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.count.return_value = 3
        result = collect_self_check(db)
        names = {c["name"]: c for c in result["checks"]}
        assert names["待审核账号"]["level"] == LEVEL_WARN
        assert names["账号锁定"]["level"] == LEVEL_WARN
        assert result["status"] == LEVEL_WARN


class TestPiiKeyCheck:
    def test_fingerprint_ok(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.count.return_value = 0
        with patch("app.core.pii_crypto.key_fingerprint", return_value="abcdef1234567890"):
            result = collect_self_check(db)
        check = next(c for c in result["checks"] if c["name"] == "PII 密钥")
        assert check["level"] == LEVEL_OK
        assert "abcdef1234567890" in check["detail"]

    def test_empty_fingerprint_is_error(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.count.return_value = 0
        with patch("app.core.pii_crypto.key_fingerprint", return_value=""):
            result = collect_self_check(db)
        check = next(c for c in result["checks"] if c["name"] == "PII 密钥")
        assert check["level"] == LEVEL_ERROR

    def test_exception_is_error(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.count.return_value = 0
        with patch("app.core.pii_crypto.key_fingerprint", side_effect=RuntimeError("boom")):
            result = collect_self_check(db)
        check = next(c for c in result["checks"] if c["name"] == "PII 密钥")
        assert check["level"] == LEVEL_ERROR


class TestImportCheck:
    def test_no_failure(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.count.return_value = 0
        result = collect_self_check(db)
        check = next(c for c in result["checks"] if c["name"] == "介质导入")
        assert check["level"] == LEVEL_OK

    def test_failures_warn(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.count.return_value = 2
        result = collect_self_check(db)
        check = next(c for c in result["checks"] if c["name"] == "介质导入")
        assert check["level"] == LEVEL_WARN
        assert "2 次导入失败" in check["detail"]


class TestSummary:
    def test_summary_fields(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.count.return_value = 0
        result = collect_self_check(db)
        assert result["summary"]["check_count"] == 6
        assert result["summary"]["error_count"] == 0
        assert result["summary"]["warn_count"] == 0
        assert result["generated_at"]
        assert len(result["checks"]) == 6
