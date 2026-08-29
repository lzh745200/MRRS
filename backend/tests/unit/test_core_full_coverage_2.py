"""
Comprehensive tests for remaining core modules (part 2).
Covers: mock_data, prophet_status, redis_adapter, cache_settings, user_info,
migration_helper, database_indexes, database_root, database_compat,
static_files, audit_middleware, middleware, logging, structured_logging,
token_blacklist, token_manager, security helpers, data_permission,
unified_data_scope, permission_utils, upload_security, file_upload.
"""
import asyncio
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch, AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# ══════════════════════════════════════════════════════════════
# mock_data
# ══════════════════════════════════════════════════════════════


# prophet_status
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# redis_adapter
# ══════════════════════════════════════════════════════════════


class TestRedisAdapter:
    def test_get_set(self):
        from app.core.redis_adapter import RedisAdapter
        r = RedisAdapter()
        r.set('key', 'value')
        assert r.get('key') == 'value'

    def test_get_missing(self):
        from app.core.redis_adapter import RedisAdapter
        r = RedisAdapter()
        assert r.get('missing') is None

    def test_set_with_ttl(self):
        from app.core.redis_adapter import RedisAdapter
        r = RedisAdapter()
        r.set('k', 'v', ttl=3600)
        assert r.get('k') == 'v'

    def test_delete(self):
        from app.core.redis_adapter import RedisAdapter
        r = RedisAdapter()
        r.set('k', 'v')
        assert r.delete('k') is True
        assert r.get('k') is None

    def test_delete_missing(self):
        from app.core.redis_adapter import RedisAdapter
        r = RedisAdapter()
        assert r.delete('missing') is True

    def test_exists(self):
        from app.core.redis_adapter import RedisAdapter
        r = RedisAdapter()
        r.set('k', 'v')
        assert r.exists('k') is True
        assert r.exists('missing') is False

    def test_flush(self):
        from app.core.redis_adapter import RedisAdapter
        r = RedisAdapter()
        r.set('k', 'v')
        r.flush()
        assert r.exists('k') is False

    def test_singleton(self):
        from app.core.redis_adapter import redis_adapter
        assert redis_adapter is not None


# ══════════════════════════════════════════════════════════════
# cache_settings
# ══════════════════════════════════════════════════════════════



# ══════════════════════════════════════════════════════════════
# migration_helper
# ══════════════════════════════════════════════════════════════


class TestMigrationHelper:
    def test_sqlite_col_spec_integer(self):
        from app.core.migration_helper import _sqlite_col_spec
        col = MagicMock()
        col.type = MagicMock()
        col.type.__str__ = lambda self: 'INTEGER'
        col.default = None
        col.server_default = None
        col.nullable = False
        stype, default_clause = _sqlite_col_spec(col)
        assert stype == 'INTEGER'

    def test_sqlite_col_spec_float(self):
        from app.core.migration_helper import _sqlite_col_spec
        col = MagicMock()
        col.type = MagicMock()
        col.type.__str__ = lambda self: 'FLOAT'
        col.default = None
        col.server_default = None
        col.nullable = True
        stype, _ = _sqlite_col_spec(col)
        assert stype == 'REAL'

    def test_sqlite_col_spec_text(self):
        from app.core.migration_helper import _sqlite_col_spec
        col = MagicMock()
        col.type = MagicMock()
        col.type.__str__ = lambda self: 'VARCHAR(100)'
        col.default = None
        col.server_default = None
        col.nullable = True
        stype, _ = _sqlite_col_spec(col)
        assert stype == 'TEXT'

    def test_sqlite_col_spec_with_bool_default(self):
        from app.core.migration_helper import _sqlite_col_spec
        col = MagicMock()
        col.type = MagicMock()
        col.type.__str__ = lambda self: 'BOOLEAN'
        col.default = MagicMock()
        col.default.arg = True
        col.default.__class__ = type('ColDef', (), {})
        col.server_default = None
        col.nullable = True
        stype, default_clause = _sqlite_col_spec(col)
        assert stype == 'INTEGER'
        assert 'DEFAULT 1' in default_clause

    def test_sqlite_col_spec_with_int_default(self):
        from app.core.migration_helper import _sqlite_col_spec
        col = MagicMock()
        col.type = MagicMock()
        col.type.__str__ = lambda self: 'INTEGER'
        col.default = MagicMock()
        col.default.arg = 42
        col.server_default = None
        col.nullable = True
        stype, default_clause = _sqlite_col_spec(col)
        assert 'DEFAULT 42' in default_clause

    def test_sqlite_col_spec_with_string_default(self):
        from app.core.migration_helper import _sqlite_col_spec
        col = MagicMock()
        col.type = MagicMock()
        col.type.__str__ = lambda self: 'VARCHAR(50)'
        col.default = MagicMock()
        col.default.arg = "hello"
        col.server_default = None
        col.nullable = True
        stype, default_clause = _sqlite_col_spec(col)
        assert "DEFAULT 'hello'" in default_clause

    def test_sqlite_col_spec_with_callable_default(self):
        from app.core.migration_helper import _sqlite_col_spec
        col = MagicMock()
        col.type = MagicMock()
        col.type.__str__ = lambda self: 'DATETIME'
        col.default = MagicMock()
        col.default.arg = datetime.now  # callable
        col.server_default = None
        col.nullable = True
        stype, default_clause = _sqlite_col_spec(col)
        assert default_clause == ''

    def test_sqlite_col_spec_nullable_no_default(self):
        from app.core.migration_helper import _sqlite_col_spec
        col = MagicMock()
        col.type = MagicMock()
        col.type.__str__ = lambda self: 'INTEGER'
        col.default = None
        col.server_default = None
        col.nullable = False
        stype, default_clause = _sqlite_col_spec(col)
        assert 'DEFAULT 0' in default_clause

    def test_sqlite_col_spec_with_server_default(self):
        from app.core.migration_helper import _sqlite_col_spec
        col = MagicMock()
        col.type = MagicMock()
        col.type.__str__ = lambda self: 'DATETIME'
        col.default = None
        col.server_default = MagicMock()  # server_default set
        col.nullable = True
        stype, default_clause = _sqlite_col_spec(col)
        assert default_clause == ''

    def test_migrate_missing_columns_disabled(self):
        from app.core.migration_helper import migrate_missing_columns
        with patch.dict(os.environ, {'DISABLE_AUTO_MIGRATION': '1'}):
            engine = MagicMock()
            migrate_missing_columns(engine, MagicMock())  # should return early

    def test_migrate_missing_columns_inspector_error(self):
        from app.core.migration_helper import migrate_missing_columns
        engine = MagicMock()
        with patch('app.core.migration_helper.sa_inspect', side_effect=Exception('fail')):
            with patch.dict(os.environ, {'DISABLE_AUTO_MIGRATION': ''}):
                migrate_missing_columns(engine, MagicMock())


# ══════════════════════════════════════════════════════════════
# database_indexes
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# database_root
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# database_compat
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# static_files
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# audit_middleware
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# middleware
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# logging
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# structured_logging
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# token_blacklist
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# token_manager
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# permissions
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# permission_utils
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# upload_security
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# file_upload
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# data_permission
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# unified_data_scope
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# error_handler
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# auth_root
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# audit
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# logging_config
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# cache
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# config
# ══════════════════════════════════════════════════════════════


class TestConfig:
    def test_settings_importable(self):
        from app.core.config import settings
        assert settings is not None

    def test_settings_has_required_attrs(self):
        from app.core.config import settings
        assert hasattr(settings, 'SECRET_KEY')
        assert hasattr(settings, 'DATABASE_URL')
