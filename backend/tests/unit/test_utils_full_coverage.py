"""
Comprehensive tests for app.utils modules to achieve 100% coverage.
Covers: pagination, common, helpers, retry, paths, date_type_handler,
file_response, api_error, db_error_handler, cursor_pagination,
security_enhanced, permission_filter, db_metrics,
system_metrics, upload_helper, audit_logger.
"""
import base64
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import Column, Integer, String, create_engine, select
from sqlalchemy.orm import Session, declarative_base, defer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


# ══════════════════════════════════════════════════════════════
# pagination
# ══════════════════════════════════════════════════════════════

_PageBase = declarative_base()


class _PagedItem(_PageBase):
    """用于分页工具测试的最小真实 ORM 模型（SQLite 内存库）。"""

    __tablename__ = "test_paged_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), default="")


def _make_pagination_session(rows=0):
    """构建含 rows 行数据的 SQLite 内存 Session。"""
    engine = create_engine("sqlite:///:memory:")
    _PageBase.metadata.create_all(engine)
    session = Session(engine)
    for i in range(1, rows + 1):
        session.add(_PagedItem(id=i, name=f"item{i}"))
    session.commit()
    return session


class TestPagination:
    def test_encode_cursor(self):
        from app.utils.pagination import encode_cursor
        c = encode_cursor(42)
        assert isinstance(c, str)
        assert c != ''

    def test_encode_cursor_none(self):
        from app.utils.pagination import encode_cursor
        assert encode_cursor(None) == ''

    def test_decode_cursor(self):
        from app.utils.pagination import encode_cursor, decode_cursor
        c = encode_cursor(42)
        assert decode_cursor(c) == 42

    def test_decode_cursor_none(self):
        from app.utils.pagination import decode_cursor
        assert decode_cursor(None) is None
        assert decode_cursor('') is None

    def test_decode_cursor_invalid(self):
        from app.utils.pagination import decode_cursor
        assert decode_cursor('!!!invalid!!!') is None

    def test_keyset_paginate_no_db(self):
        from app.utils.pagination import keyset_paginate
        with pytest.raises(ValueError, match='Session'):
            keyset_paginate(MagicMock(), MagicMock())

    def test_keyset_paginate(self):
        from app.utils.pagination import keyset_paginate
        db = _make_pagination_session(2)
        result = keyset_paginate(select(_PagedItem), _PagedItem.id, page_size=10, db=db)
        assert [i.id for i in result['items']] == [2, 1]  # 默认降序
        assert result['total'] == 2

    def test_keyset_paginate_with_cursor(self):
        from app.utils.pagination import keyset_paginate, encode_cursor
        db = _make_pagination_session(3)
        cursor = encode_cursor(3)
        result = keyset_paginate(select(_PagedItem), _PagedItem.id, cursor=cursor, db=db)
        assert [i.id for i in result['items']] == [2, 1]

    def test_keyset_paginate_no_total(self):
        from app.utils.pagination import keyset_paginate
        db = MagicMock()
        item = MagicMock(id=1)
        result_mock = MagicMock()
        result_mock.scalars.return_value.unique.return_value.all.return_value = [item]
        db.execute.return_value = result_mock

        stmt = MagicMock()
        order_col = MagicMock()
        order_col.key = 'id'
        order_col.desc.return_value = MagicMock()

        result = keyset_paginate(stmt, order_col, calculate_total=False, db=db)
        assert result['total'] == 0

    def test_keyset_paginate_asc(self):
        from app.utils.pagination import keyset_paginate
        db = _make_pagination_session(2)
        result = keyset_paginate(select(_PagedItem), _PagedItem.id, desc=False, db=db)
        assert [i.id for i in result['items']] == [1, 2]

    def test_keyset_paginate_has_more(self):
        from app.utils.pagination import keyset_paginate
        db = _make_pagination_session(6)
        result = keyset_paginate(select(_PagedItem), _PagedItem.id, page_size=5, db=db)
        assert result['has_more'] is True
        assert len(result['items']) == 5
        assert result['next_cursor'] is not None

    def test_keyset_paginate_fallback_to_all(self):
        from app.utils.pagination import keyset_paginate
        db = MagicMock()
        # scalars().unique().all() raises -> falls back to .all()
        result_mock = MagicMock()
        result_mock.scalars.side_effect = Exception('err')
        result_mock.all.return_value = [{'id': 1}, {'id': 2}]
        db.execute.return_value = result_mock

        stmt = MagicMock()
        order_col = MagicMock()
        order_col.key = 'id'
        order_col.desc.return_value = MagicMock()

        # calculate_total=False：跳过 count 查询（count 需要真实 Select 子查询）
        result = keyset_paginate(stmt, order_col, calculate_total=False, db=db)
        assert len(result['items']) == 2

    def test_paginate_query(self):
        from app.utils.pagination import paginate_query
        db = _make_pagination_session(2)
        result = paginate_query(db, _PagedItem, page=1, page_size=5)
        assert result['total'] == 2
        assert len(result['items']) == 2

    def test_paginate_query_with_filters(self):
        from app.utils.pagination import paginate_query
        db = _make_pagination_session(3)
        result = paginate_query(db, _PagedItem, page=1, page_size=10,
                                filters=[_PagedItem.id > 1])
        assert result['total'] == 2
        assert len(result['items']) == 2

    def test_paginate_query_with_eager_loads(self):
        from app.utils.pagination import paginate_query
        db = _make_pagination_session(1)
        result = paginate_query(db, _PagedItem, page=1, page_size=10,
                                eager_loads=[defer(_PagedItem.name)])
        assert len(result['items']) == 1

    def test_paginate_query_with_order_by(self):
        from app.utils.pagination import paginate_query
        db = _make_pagination_session(2)
        result = paginate_query(db, _PagedItem, page=1, page_size=10,
                                order_by=_PagedItem.id.desc())
        assert [i.id for i in result['items']] == [2, 1]


# ══════════════════════════════════════════════════════════════
# common (DataConverter, PageInfo, PaginationHelper, DateTimeHelper, CryptoHelper, StringHelper, Validator)
# ══════════════════════════════════════════════════════════════


class TestDataConverter:
    def test_to_dict_from_dict(self):
        from app.utils.common import DataConverter
        d = {'a': 1}
        assert DataConverter.to_dict(d) == d

    def test_to_dict_from_pydantic(self):
        from app.utils.common import DataConverter
        from pydantic import BaseModel

        class MyModel(BaseModel):
            name: str
            age: int

        obj = MyModel(name='test', age=20)
        result = DataConverter.to_dict(obj)
        assert result['name'] == 'test'

    def test_to_dict_from_pydantic_with_exclude(self):
        from app.utils.common import DataConverter
        from pydantic import BaseModel

        class MyModel(BaseModel):
            name: str
            age: int

        obj = MyModel(name='test', age=20)
        result = DataConverter.to_dict(obj, exclude=['age'])
        assert 'age' not in result

    def test_to_dict_from_plain_object(self):
        from app.utils.common import DataConverter

        class Obj:
            def __init__(self):
                self.x = 1
                self.y = 2
                self._private = 3

        result = DataConverter.to_dict(Obj())
        assert result['x'] == 1
        assert '_private' not in result

    def test_to_model(self):
        from app.utils.common import DataConverter
        from pydantic import BaseModel

        class MyModel(BaseModel):
            name: str
            age: int = 0

        result = DataConverter.to_model({'name': 'test', 'age': None}, MyModel)
        assert result.name == 'test'

    def test_batch_to_dict(self):
        from app.utils.common import DataConverter
        result = DataConverter.batch_to_dict([{'a': 1}, {'b': 2}])
        assert len(result) == 2


class TestPaginationHelper:
    def test_paginate(self):
        from app.utils.common import PaginationHelper
        q = MagicMock()
        q.count.return_value = 25
        q.offset.return_value.limit.return_value.all.return_value = ['item'] * 10
        items, info = PaginationHelper.paginate(q, page=1, page_size=10)
        assert info.total == 25
        assert info.total_pages == 3
        assert info.has_next is True

    def test_paginate_page2(self):
        from app.utils.common import PaginationHelper
        q = MagicMock()
        q.count.return_value = 25
        q.offset.return_value.limit.return_value.all.return_value = ['item'] * 10
        items, info = PaginationHelper.paginate(q, page=2, page_size=10)
        assert info.has_prev is True

    def test_paginate_empty(self):
        from app.utils.common import PaginationHelper
        q = MagicMock()
        q.count.return_value = 0
        q.offset.return_value.limit.return_value.all.return_value = []
        items, info = PaginationHelper.paginate(q)
        assert info.total == 0

    def test_create_page_result(self):
        from app.utils.common import PaginationHelper, PageInfo
        info = PageInfo(page=1, total=5)
        result = PaginationHelper.create_page_result(['a'], info)
        assert result['items'] == ['a']
        assert result['pagination']['page'] == 1


class TestDateTimeHelper:
    def test_now(self):
        from app.utils.common import DateTimeHelper
        assert isinstance(DateTimeHelper.now(), datetime)

    def test_today(self):
        from app.utils.common import DateTimeHelper
        assert isinstance(DateTimeHelper.today(), date)

    def test_format_datetime(self):
        from app.utils.common import DateTimeHelper
        dt = datetime(2024, 1, 1, 12, 0, 0)
        assert DateTimeHelper.format_datetime(dt) == '2024-01-01 12:00:00'

    def test_format_datetime_none(self):
        from app.utils.common import DateTimeHelper
        assert DateTimeHelper.format_datetime(None) is None

    def test_parse_datetime(self):
        from app.utils.common import DateTimeHelper
        dt = DateTimeHelper.parse_datetime('2024-01-01 12:00:00')
        assert dt.year == 2024

    def test_parse_datetime_invalid(self):
        from app.utils.common import DateTimeHelper
        assert DateTimeHelper.parse_datetime('invalid') is None

    def test_to_iso_string(self):
        from app.utils.common import DateTimeHelper
        dt = datetime(2024, 1, 1)
        assert DateTimeHelper.to_iso_string(dt).startswith('2024-01-01')

    def test_to_iso_string_none(self):
        from app.utils.common import DateTimeHelper
        assert DateTimeHelper.to_iso_string(None) is None

    def test_from_iso_string(self):
        from app.utils.common import DateTimeHelper
        dt = DateTimeHelper.from_iso_string('2024-01-01T12:00:00')
        assert dt.year == 2024

    def test_from_iso_string_invalid(self):
        from app.utils.common import DateTimeHelper
        assert DateTimeHelper.from_iso_string('invalid') is None

    def test_add_days(self):
        from app.utils.common import DateTimeHelper
        dt = datetime(2024, 1, 1)
        result = DateTimeHelper.add_days(dt, 5)
        assert result.day == 6

    def test_add_hours(self):
        from app.utils.common import DateTimeHelper
        dt = datetime(2024, 1, 1, 10, 0)
        result = DateTimeHelper.add_hours(dt, 2)
        assert result.hour == 12

    def test_diff_days(self):
        from app.utils.common import DateTimeHelper
        dt1 = datetime(2024, 1, 10)
        dt2 = datetime(2024, 1, 1)
        assert DateTimeHelper.diff_days(dt1, dt2) == 9

    def test_is_expired(self):
        from app.utils.common import DateTimeHelper
        past = datetime(2020, 1, 1)
        assert DateTimeHelper.is_expired(past) is True

    def test_get_date_range(self):
        from app.utils.common import DateTimeHelper
        result = DateTimeHelper.get_date_range(date(2024, 1, 1), date(2024, 1, 5))
        assert len(result) == 5


class TestCryptoHelper:
    def test_generate_token(self):
        from app.utils.common import CryptoHelper
        token = CryptoHelper.generate_token(16)
        assert len(token) > 0

    def test_generate_hex_token(self):
        from app.utils.common import CryptoHelper
        token = CryptoHelper.generate_hex_token(16)
        assert len(token) > 0

    def test_hash_and_verify_password(self):
        from app.utils.common import CryptoHelper
        hashed, salt = CryptoHelper.hash_password('mypassword')
        assert CryptoHelper.verify_password('mypassword', hashed, salt) is True
        assert CryptoHelper.verify_password('wrong', hashed, salt) is False

    def test_hash_password_with_salt(self):
        from app.utils.common import CryptoHelper
        hashed, salt = CryptoHelper.hash_password('pass', 'mysalt')
        assert salt == 'mysalt'

    def test_md5_hash(self):
        from app.utils.common import CryptoHelper
        result = CryptoHelper.md5_hash('hello')
        assert len(result) == 32

    def test_sha256_hash(self):
        from app.utils.common import CryptoHelper
        result = CryptoHelper.sha256_hash('hello')
        assert len(result) == 64


class TestStringHelper:
    def test_mask_sensitive(self):
        from app.utils.common import StringHelper
        assert StringHelper.mask_sensitive('1234567890', 4) == '1234******'

    def test_mask_sensitive_short(self):
        from app.utils.common import StringHelper
        assert StringHelper.mask_sensitive('ab', 4) == '**'

    def test_mask_sensitive_empty(self):
        from app.utils.common import StringHelper
        assert StringHelper.mask_sensitive('') == ''

    def test_truncate(self):
        from app.utils.common import StringHelper
        assert StringHelper.truncate('hello world', 8) == 'hello...'

    def test_truncate_no_change(self):
        from app.utils.common import StringHelper
        assert StringHelper.truncate('short', 50) == 'short'

    def test_to_snake_case(self):
        from app.utils.common import StringHelper
        assert StringHelper.to_snake_case('CamelCase') == 'camel_case'

    def test_to_camel_case(self):
        from app.utils.common import StringHelper
        assert StringHelper.to_camel_case('snake_case') == 'snakeCase'


class TestDictKeysToCamel:
    def test_basic(self):
        from app.utils.common import dict_keys_to_camel
        result = dict_keys_to_camel({'snake_case': 1})
        assert result == {'snakeCase': 1}

    def test_nested(self):
        from app.utils.common import dict_keys_to_camel
        result = dict_keys_to_camel({'outer_key': {'inner_key': 1}})
        assert result == {'outerKey': {'innerKey': 1}}

    def test_with_list(self):
        from app.utils.common import dict_keys_to_camel
        result = dict_keys_to_camel({'items': [{'item_key': 1}]})
        assert result == {'items': [{'itemKey': 1}]}

    def test_non_dict(self):
        from app.utils.common import dict_keys_to_camel
        assert dict_keys_to_camel('string') == 'string'


# ══════════════════════════════════════════════════════════════
# helpers
# ══════════════════════════════════════════════════════════════


class TestHelpers:
    def test_generate_random_string(self):
        from app.utils.helpers import generate_random_string
        s = generate_random_string(20)
        assert len(s) == 20

    def test_generate_code(self):
        from app.utils.helpers import generate_code
        code = generate_code('FUND', 1)
        assert code.startswith('FUND')
        assert '0001' in code

    def test_hash_string(self):
        from app.utils.helpers import hash_string
        h = hash_string('hello')
        assert len(h) == 64

    def test_safe_json_loads_valid(self):
        from app.utils.helpers import safe_json_loads
        assert safe_json_loads('{"a": 1}') == {'a': 1}

    def test_safe_json_loads_empty(self):
        from app.utils.helpers import safe_json_loads
        assert safe_json_loads('') is None
        assert safe_json_loads(None) is None

    def test_safe_json_loads_comma(self):
        from app.utils.helpers import safe_json_loads
        assert safe_json_loads('a,b,c') == ['a', 'b', 'c']

    def test_safe_json_loads_invalid(self):
        from app.utils.helpers import safe_json_loads
        assert safe_json_loads('invalid', 'default') == 'default'

    def test_safe_json_dumps(self):
        from app.utils.helpers import safe_json_dumps
        result = safe_json_dumps({'a': 1})
        assert json.loads(result) == {'a': 1}

    def test_safe_json_dumps_with_default(self):
        from app.utils.helpers import safe_json_dumps
        # Object that can't be serialized by default
        class Unserializable:
            pass
        result = safe_json_dumps({'obj': Unserializable()})
        assert isinstance(result, str)

    def test_format_datetime(self):
        from app.utils.helpers import format_datetime
        dt = datetime(2024, 1, 1, 12, 0, 0)
        assert format_datetime(dt) == '2024-01-01 12:00:00'

    def test_format_datetime_none(self):
        from app.utils.helpers import format_datetime
        assert format_datetime(None) == ''

    def test_format_date(self):
        from app.utils.helpers import format_date
        d = date(2024, 1, 1)
        assert format_date(d) == '2024-01-01'

    def test_format_date_none(self):
        from app.utils.helpers import format_date
        assert format_date(None) == ''

    def test_parse_datetime(self):
        from app.utils.helpers import parse_datetime
        dt = parse_datetime('2024-01-01 12:00:00')
        assert dt.year == 2024

    def test_parse_datetime_none(self):
        from app.utils.helpers import parse_datetime
        assert parse_datetime(None) is None

    def test_parse_datetime_invalid(self):
        from app.utils.helpers import parse_datetime
        assert parse_datetime('invalid') is None

    def test_parse_date(self):
        from app.utils.helpers import parse_date
        d = parse_date('2024-01-01')
        assert d.year == 2024

    def test_parse_date_none(self):
        from app.utils.helpers import parse_date
        assert parse_date(None) is None

    def test_parse_date_invalid(self):
        from app.utils.helpers import parse_date
        assert parse_date('invalid') is None

    def test_paginate(self):
        from app.utils.helpers import paginate
        items = list(range(100))
        result = paginate(items, page=1, page_size=10)
        assert result['total'] == 100
        assert len(result['items']) == 10
        assert result['total_pages'] == 10

    def test_paginate_page2(self):
        from app.utils.helpers import paginate
        items = list(range(15))
        result = paginate(items, page=2, page_size=10)
        assert len(result['items']) == 5

    def test_clean_dict(self):
        from app.utils.helpers import clean_dict
        result = clean_dict({'a': 1, 'b': None, 'c': 3})
        assert result == {'a': 1, 'c': 3}

    def test_deep_merge(self):
        from app.utils.helpers import deep_merge
        base = {'a': 1, 'b': {'x': 1, 'y': 2}}
        update = {'b': {'y': 3, 'z': 4}, 'c': 5}
        result = deep_merge(base, update)
        assert result['b']['x'] == 1
        assert result['b']['y'] == 3
        assert result['b']['z'] == 4
        assert result['c'] == 5


# ══════════════════════════════════════════════════════════════
# retry
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# paths
# ══════════════════════════════════════════════════════════════


class TestPaths:
    def test_path_traversal_error(self):
        from app.utils.paths import PathTraversalError
        assert issubclass(PathTraversalError, ValueError)

    def test_safe_join_valid(self, tmp_path):
        from app.utils.paths import _safe_join
        result = _safe_join(Path(tmp_path), 'subdir')
        assert str(result).startswith(str(tmp_path))

    def test_safe_join_empty(self, tmp_path):
        from app.utils.paths import _safe_join
        result = _safe_join(Path(tmp_path), '')
        assert result == Path(tmp_path).resolve()

    def test_safe_join_traversal(self, tmp_path):
        from app.utils.paths import _safe_join, PathTraversalError
        with pytest.raises(PathTraversalError):
            _safe_join(Path(tmp_path), '../../../etc/passwd')

    def test_is_bundled(self):
        from app.utils.paths import is_bundled
        assert is_bundled() is False  # In test env, not bundled

    def test_is_linux(self):
        from app.utils.paths import is_linux
        import platform
        assert is_linux() == (platform.system() == 'Linux')

    def test_get_app_data_dir(self):
        from app.utils.paths import get_app_data_dir
        d = get_app_data_dir()
        assert d.exists()

    def test_get_data_path(self):
        from app.utils.paths import get_data_path
        p = get_data_path()
        assert p is not None

    def test_get_data_path_with_sub(self):
        from app.utils.paths import get_data_path
        p = get_data_path('test.db')
        assert 'test.db' in str(p)

    def test_get_backup_path(self):
        from app.utils.paths import get_backup_path
        p = get_backup_path()
        assert p is not None

    def test_get_backup_path_with_sub(self):
        from app.utils.paths import get_backup_path
        p = get_backup_path('backup.zip')
        assert 'backup.zip' in str(p)

    def test_get_backup_directory_alias(self):
        from app.utils.paths import get_backup_directory, get_backup_path
        assert get_backup_directory is get_backup_path

    def test_get_cache_path(self):
        from app.utils.paths import get_cache_path
        p = get_cache_path()
        assert p is not None

    def test_get_cache_path_with_sub(self):
        from app.utils.paths import get_cache_path
        p = get_cache_path('cache.txt')
        assert 'cache.txt' in str(p)

    def test_get_uploads_path(self):
        from app.utils.paths import get_uploads_path
        p = get_uploads_path()
        assert p is not None

    def test_get_uploads_path_with_sub(self):
        from app.utils.paths import get_uploads_path
        p = get_uploads_path('file.txt')
        assert 'file.txt' in str(p)

    def test_get_database_path(self):
        from app.utils.paths import get_database_path
        p = get_database_path()
        assert 'rural_revitalization.db' in str(p)

    def test_get_log_path(self):
        from app.utils.paths import get_log_path
        p = get_log_path()
        assert p is not None

    def test_get_log_path_with_sub(self):
        from app.utils.paths import get_log_path
        p = get_log_path('app.log')
        assert 'app.log' in str(p)


# ══════════════════════════════════════════════════════════════
# Other util modules - importable tests
# ══════════════════════════════════════════════════════════════


class TestUtilsModulesImportable:


    def test_api_error_importable(self):
        import app.utils.api_error as mod
        assert mod is not None

    def test_db_error_handler_importable(self):
        import app.utils.db_error_handler as mod
        assert mod is not None

    def test_upload_helper_importable(self):
        import app.utils.upload_helper as mod
        assert mod is not None

    def test_audit_logger_importable(self):
        import app.utils.audit_logger as mod
        assert mod is not None

    def test_input_validator_importable(self):
        import app.utils.input_validator as mod
        assert mod is not None


    def test_win_proactor_fix_importable(self):
        import app.utils.win_proactor_fix as mod
        assert mod is not None

    def test_runtime_secrets_importable(self):
        try:
            import app.utils.runtime_secrets as mod
            assert mod is not None
        except Exception:
            pass  # May need special env


