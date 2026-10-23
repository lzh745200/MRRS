# -*- coding: utf-8 -*-
"""P2 单位码校验模块：来源单位码比对的四态行为。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.package_org_code import (
    MATCH_MISMATCH,
    MATCH_OK,
    MATCH_UNKNOWN,
    check_org_code,
    extract_manifest_org_code,
    local_org_code,
)


class TestExtractManifestOrgCode:
    def test_dict_manifest(self):
        assert extract_manifest_org_code({"org_code": "520000"}) == "520000"

    def test_object_manifest(self):
        assert extract_manifest_org_code(SimpleNamespace(org_code="520100")) == "520100"

    def test_none_and_empty(self):
        assert extract_manifest_org_code(None) == ""
        assert extract_manifest_org_code({}) == ""
        assert extract_manifest_org_code(SimpleNamespace(org_code=None)) == ""

    def test_strips_whitespace(self):
        assert extract_manifest_org_code({"org_code": "  520000  "}) == "520000"


class TestLocalOrgCode:
    def test_no_org_id(self):
        assert local_org_code(MagicMock(), None) == ""

    def test_org_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(code="520000")
        assert local_org_code(db, 1) == "520000"

    def test_org_missing(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        assert local_org_code(db, 1) == ""

    def test_query_failure_returns_empty(self):
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")
        assert local_org_code(db, 1) == ""


class TestCheckOrgCode:
    def _db(self, code):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(code=code)
        return db

    def test_match(self):
        result = check_org_code(self._db("520000"), {"org_code": "520000"}, 1)
        assert result["status"] == MATCH_OK
        assert result["message"] == ""

    def test_mismatch(self):
        result = check_org_code(self._db("520000"), {"org_code": "520100"}, 1)
        assert result["status"] == MATCH_MISMATCH
        assert "520100" in result["message"]
        assert "520000" in result["message"]

    def test_package_without_code_is_unknown(self):
        result = check_org_code(self._db("520000"), {}, 1)
        assert result["status"] == MATCH_UNKNOWN
        assert "未声明来源单位码" in result["message"]

    def test_local_without_code_is_unknown(self):
        result = check_org_code(self._db(""), {"org_code": "520000"}, 1)
        assert result["status"] == MATCH_UNKNOWN
        assert "本机目标单位没有设置单位码" in result["message"]
