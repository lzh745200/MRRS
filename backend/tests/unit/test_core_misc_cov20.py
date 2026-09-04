"""app.core 零散缺口补测（task#20）。

覆盖：response.from_pagination(28) / money._quantize_4(25) /
redis_adapter.get_stats+health_check / error_handler 三个响应构造器 /
token_blacklist naive-datetime 分支(45,95) / pii_crypto(40,50-51,93) /
data_scope_adapter._apply_org_filter fail-closed(204) /
database._set_sqlite_pragma SQLCipher 分支(96-98,100-101,125-127) +
check_disk_space cwd 回退(321)。
"""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────── response.py ───────────────────────────


class TestPaginationMeta:
    def test_from_pagination_computes_total_pages(self):
        from app.core.response import PaginationMeta

        meta = PaginationMeta.from_pagination(page=1, page_size=10, total=25)
        assert meta.total_pages == 3  # 行 28 math.ceil 分支
        assert meta.has_next is True and meta.has_prev is False

    def test_from_pagination_zero_page_size(self):
        from app.core.response import PaginationMeta

        meta = PaginationMeta.from_pagination(page=1, page_size=0, total=25)
        assert meta.total_pages == 0  # 行 25-26 分支

    def test_from_pagination_zero_total(self):
        from app.core.response import PaginationMeta

        meta = PaginationMeta.from_pagination(page=1, page_size=10, total=0)
        assert meta.total_pages == 0  # total==0 → else 0


# ─────────────────────────── money.py ───────────────────────────


class TestMoneyQuantize:
    def test_none_returns_zero(self):
        from decimal import Decimal

        from app.core.money import _quantize_4

        assert _quantize_4(None) == Decimal("0")  # 行 24-25

    def test_float_quantized_half_up(self):
        from decimal import Decimal

        from app.core.money import _quantize_4

        assert _quantize_4(1.23456) == Decimal("1.2346")

    def test_decimal_passthrough(self):
        from decimal import Decimal

        from app.core.money import _quantize_4

        assert _quantize_4(Decimal("2.5")) == Decimal("2.5000")


# ─────────────────────────── redis_adapter.py ───────────────────────────


class TestRedisAdapterStats:
    def test_get_stats(self):
        from app.core.redis_adapter import RedisAdapter

        a = RedisAdapter()
        a.set("k", "v")
        stats = a.get_stats()  # 行 32
        assert stats["type"] == "memory" and stats["keys"] == 1
        assert stats["hit_ratio"] is None

    def test_health_check(self):
        from app.core.redis_adapter import RedisAdapter

        assert RedisAdapter().health_check() == {  # 行 40
            "status": "healthy", "backend": "memory"
        }


# ─────────────────────────── error_handler.py ───────────────────────────


class TestErrorHandlerResponses:
    def test_not_found_without_id(self):
        from app.core.error_handler import not_found_response

        resp = not_found_response("用户")  # 行 73-74
        assert resp.status_code == 404

    def test_not_found_with_id(self):
        from app.core.error_handler import not_found_response

        resp = not_found_response("用户", resource_id="7")
        assert resp.status_code == 404

    def test_forbidden_response(self):
        from app.core.error_handler import forbidden_response

        assert forbidden_response().status_code == 403  # 行 82

    def test_server_error_response(self):
        from app.core.error_handler import server_error_response

        assert server_error_response().status_code == 500  # 行 90


# ─────────────────────────── token_blacklist.py ───────────────────────────


class TestTokenBlacklistNaiveDatetime:
    def test_add_naive_expires_at_assumes_utc(self):
        from app.core import token_blacklist as tbl

        naive = datetime(2099, 1, 1, 0, 0, 0)  # 无 tzinfo
        tbl.add("jti-naive-add", expires_at=naive)  # 行 43-45
        try:
            assert tbl.is_blacklisted("jti-naive-add") is True
        finally:
            tbl.remove("jti-naive-add")

    def test_load_from_db_naive_expires_at(self):
        from app.core import token_blacklist as tbl

        entry = SimpleNamespace(
            token_jti="jti-naive-load",
            expires_at=datetime(2099, 1, 1, 0, 0, 0),  # naive → 行 94-95
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]
        try:
            count = tbl.load_from_db(db)
            assert count == 1
            assert tbl.is_blacklisted("jti-naive-load") is True
        finally:
            tbl.remove("jti-naive-load")


# ─────────────────────────── pii_crypto.py ───────────────────────────


class TestPiiCryptoKeyLoading:
    def test_load_key_from_encryption_key_setting(self, monkeypatch):
        from app.core import pii_crypto
        from app.core.config import settings

        pii_crypto.reset_key_cache()  # 行 93
        monkeypatch.setattr(settings, "ENCRYPTION_KEY", "explicit-test-key", raising=False)
        try:
            key = pii_crypto._load_key()  # 行 39-40 logger.info 分支
            assert isinstance(key, bytes) and len(key) == 64
        finally:
            pii_crypto.reset_key_cache()

    def test_load_key_runtime_secret_failure_raises(self, monkeypatch):
        from app.core import pii_crypto
        from app.core.config import settings

        pii_crypto.reset_key_cache()
        monkeypatch.setattr(settings, "ENCRYPTION_KEY", "", raising=False)

        def _boom(*a, **k):
            raise OSError("cannot read runtime_secrets.json")

        monkeypatch.setattr(
            "app.utils.runtime_secrets.get_or_create_secret", _boom, raising=False
        )
        try:
            with pytest.raises(RuntimeError, match="PII 加密密钥初始化失败"):
                pii_crypto._load_key()  # 行 50-54 except → RuntimeError
        finally:
            pii_crypto.reset_key_cache()

    def test_reset_key_cache_clears(self):
        from app.core import pii_crypto

        pii_crypto._key_cache = b"x"
        pii_crypto.reset_key_cache()
        assert pii_crypto._key_cache is None


# ─────────────────────────── data_scope_adapter.py ───────────────────────────


class TestApplyOrgFilterFailClosed:
    def test_missing_org_field_raises(self):
        from app.core.data_scope_adapter import DataScopeFilterError, _apply_org_filter

        class NoOrgModel:
            __name__ = "NoOrgModel"

        with pytest.raises(DataScopeFilterError, match="缺少组织字段"):
            _apply_org_filter(MagicMock(), NoOrgModel, "organization_id", [1])  # 行 202-204


# ─────────────────────────── database.py ───────────────────────────


class TestSetSqlitePragmaEncryption:
    def _conn(self, exec_side_effect):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.execute.side_effect = exec_side_effect
        conn.cursor.return_value = cursor
        return conn, cursor

    def test_cipher_probe_exception_fails_closed(self, monkeypatch):
        from app.core import database
        from app.core.config import settings

        monkeypatch.setattr(database, "IS_SQLITE", True, raising=False)
        monkeypatch.setattr(settings, "DB_ENCRYPTION_ENABLED", True, raising=False)

        def _exec(stmt, *a, **k):
            if "cipher_version" in stmt:
                raise RuntimeError("no such function")  # 触发 96-98 探测异常
            return MagicMock()

        conn, cursor = self._conn(_exec)
        with pytest.raises(RuntimeError, match="不支持 SQLCipher"):
            database._set_sqlite_pragma(conn, None)  # 行 100-101 close + raise
        cursor.close.assert_called()

    def test_key_check_failure_raises(self, monkeypatch, tmp_path):
        from app.core import database
        from app.core.config import settings

        monkeypatch.setattr(database, "IS_SQLITE", True, raising=False)
        monkeypatch.setattr(settings, "DB_ENCRYPTION_ENABLED", True, raising=False)
        # BASE_DIR 非 pydantic 字段（database.py 用 getattr 带默认值读取），
        # 绕过 pydantic 赋值校验直接写入实例 __dict__，测后清理。
        object.__setattr__(settings, "BASE_DIR", tmp_path)
        key_dir = tmp_path / "config"
        key_dir.mkdir()
        (key_dir / "db.key").write_text("secret-key", encoding="utf-8")

        def _exec(stmt, *a, **k):
            if "cipher_version" in stmt:
                m = MagicMock()
                m.fetchone.return_value = ("4.5.0",)
                return m
            if "sqlite_master" in stmt:
                raise RuntimeError("file is not a database")  # 触发 125-127
            return MagicMock()

        conn, cursor = self._conn(_exec)
        try:
            with pytest.raises(RuntimeError, match="密钥校验失败"):
                database._set_sqlite_pragma(conn, None)
            cursor.close.assert_called()
        finally:
            object.__delattr__(settings, "BASE_DIR")


class TestCheckDiskSpaceCwdFallback:
    def test_unresolvable_path_falls_back_to_cwd(self, monkeypatch):
        from app.core import database

        # 令所有 Path.exists 返回 False：while 回溯至根后仍 not exists →
        # 命中行 320-321 的 cwd 兜底（生产中根目录恒存在，此为防御分支）。
        monkeypatch.setattr(Path, "exists", lambda self: False, raising=True)
        result = database.check_disk_space(min_mb=1, path="some/deep/missing/dir")
        assert result["path"] is not None
        assert "free_mb" in result and "sufficient" in result
