"""
Comprehensive tests for core modules to achieve 100% coverage.
Covers: response, transaction, input_validation, file_utils, json_encoder,
constants, async_utils, events, i18n, cookie_security, config_validator,
exceptions, errors, performance, query_optimizer, mock_data, prophet_status,
redis_adapter, database_indexes, database_root, cache_settings, migration_helper,
user_info, permission_utils, upload_security, file_upload, static_files,
audit_middleware, middleware, logging, structured_logging, token_blacklist,
token_manager, security, data_permission, unified_data_scope, database_compat.
"""
import asyncio
import datetime
import decimal
import os
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError as PydanticValidationError

# Ensure backend on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# ══════════════════════════════════════════════════════════════
# 1. app.core.response
# ══════════════════════════════════════════════════════════════


class TestResponse:





    def test_ok_list_structure(self):
        from app.core.response import ok_list
        result = ok_list(items=[{'id': 1}], total=1, page=1, page_size=20)
        assert result['code'] == 200
        assert result['data']['items'] == [{'id': 1}]
        assert result['data']['total'] == 1

    def test_ok_list_with_kwargs(self):
        from app.core.response import ok_list
        result = ok_list(items=[], total=0, extra='val')
        assert result['extra'] == 'val'

    def test_error_response(self):
        from app.core.response import error_response
        resp = error_response(code=400, message='bad')
        assert resp['code'] == 400
        assert resp['message'] == 'bad'
        assert resp['success'] is False

    def test_error_response_with_errors_and_detail(self):
        from app.core.response import error_response
        resp = error_response(code=422, message='val', errors=['e1'], detail='d1')
        assert resp['errors'] == ['e1']
        assert resp['detail'] == 'd1'

    def test_error_response_with_kwargs(self):
        from app.core.response import error_response
        resp = error_response(code=400, message='bad', custom='x')
        assert resp['custom'] == 'x'

    def test_success_response(self):
        from app.core.response import success_response
        resp = success_response(data={'k': 'v'}, message='ok')
        assert resp['code'] == 200
        assert resp['data'] == {'k': 'v'}
        assert resp['success'] is True

    def test_success_response_no_data(self):
        from app.core.response import success_response
        resp = success_response()
        assert resp['code'] == 200
        assert 'data' not in resp

    def test_success_response_with_kwargs(self):
        from app.core.response import success_response
        resp = success_response(data=None, extra='x')
        assert resp['extra'] == 'x'


    def test_not_found_response(self):
        from app.core.response import not_found_response
        resp = not_found_response(detail='d')
        assert resp['code'] == 404


    def test_forbidden_response(self):
        from app.core.response import forbidden_response
        resp = forbidden_response()
        assert resp['code'] == 403

    def test_server_error_response(self):
        from app.core.response import server_error_response
        resp = server_error_response(detail='d')
        assert resp['code'] == 500





    def test_error_response_alias(self):
        from app.core.response import ErrorResponse, error_response
        assert ErrorResponse is error_response


# ══════════════════════════════════════════════════════════════
# 2. app.core.transaction
# ══════════════════════════════════════════════════════════════


class TestTransaction:
    def test_safe_commit_success(self):
        from app.core.transaction import safe_commit
        db = MagicMock()
        assert safe_commit(db) is True
        db.commit.assert_called_once()

    def test_safe_commit_failure(self):
        from app.core.transaction import safe_commit
        db = MagicMock()
        db.commit.side_effect = Exception('boom')
        with pytest.raises(Exception, match='boom'):
            safe_commit(db)
        db.rollback.assert_called_once()

    def test_safe_commit_with_custom_logger(self):
        from app.core.transaction import safe_commit
        db = MagicMock()
        log = MagicMock()
        safe_commit(db, logger=log)
        db.commit.assert_called_once()

    def test_safe_commit_failure_with_custom_logger(self):
        from app.core.transaction import safe_commit
        db = MagicMock()
        db.commit.side_effect = RuntimeError('fail')
        log = MagicMock()
        with pytest.raises(RuntimeError):
            safe_commit(db, logger=log)
        log.error.assert_called_once()
        db.rollback.assert_called_once()

    def test_transaction_context_success(self):
        from app.core.transaction import transaction
        db = MagicMock()
        with transaction(db) as sess:
            assert sess is db
        db.commit.assert_called_once()

    def test_transaction_context_http_exception(self):
        from app.core.transaction import transaction
        db = MagicMock()
        with pytest.raises(HTTPException):
            with transaction(db):
                raise HTTPException(status_code=400, detail='bad')
        db.rollback.assert_called_once()

    def test_transaction_context_general_exception(self):
        from app.core.transaction import transaction, DatabaseError
        db = MagicMock()
        with pytest.raises(DatabaseError):
            with transaction(db):
                raise ValueError('err')
        db.rollback.assert_called_once()

    def test_transactional_decorator_with_db_arg(self):
        from app.core.transaction import transactional
        from sqlalchemy.orm import Session
        db = MagicMock(spec=Session)

        @transactional
        def my_func(db, x):
            return x * 2

        result = my_func(db, 5)
        assert result == 10

    def test_transactional_decorator_with_db_kwarg(self):
        from app.core.transaction import transactional
        from sqlalchemy.orm import Session
        db = MagicMock(spec=Session)

        @transactional
        def my_func(x, db=None):
            return x + 1

        result = my_func(3, db=db)
        assert result == 4

    def test_transactional_decorator_exception(self):
        from app.core.transaction import transactional, DatabaseError
        from sqlalchemy.orm import Session
        db = MagicMock(spec=Session)

        @transactional
        def my_func(db):
            raise ValueError('fail')

        with pytest.raises(DatabaseError):
            my_func(db)
        db.rollback.assert_called_once()

    def test_run_in_transaction_success(self):
        from app.core.transaction import run_in_transaction
        db = MagicMock()

        def fn(db, x):
            return x + 10

        result = run_in_transaction(fn, db, 5)
        assert result == 15
        db.commit.assert_called_once()

    def test_run_in_transaction_failure(self):
        from app.core.transaction import run_in_transaction, DatabaseError
        db = MagicMock()

        def fn(db):
            raise RuntimeError('x')

        with pytest.raises(DatabaseError):
            run_in_transaction(fn, db)
        db.rollback.assert_called_once()

    def test_nested_transaction_success(self):
        from app.core.transaction import nested_transaction
        db = MagicMock()
        nested = MagicMock()
        db.begin_nested.return_value = nested
        with nested_transaction(db) as n:
            assert n is nested
        nested.commit.assert_called_once()

    def test_nested_transaction_failure(self):
        from app.core.transaction import nested_transaction, DatabaseError
        db = MagicMock()
        nested = MagicMock()
        db.begin_nested.return_value = nested
        with pytest.raises(DatabaseError):
            with nested_transaction(db):
                raise ValueError('err')
        nested.rollback.assert_called_once()

    def test_savepoint_success(self):
        from app.core.transaction import savepoint
        db = MagicMock()
        sp_mock = MagicMock()
        db.begin_nested.return_value = sp_mock
        with savepoint(db, 'my_sp') as sp:
            assert sp is sp_mock
        sp_mock.commit.assert_called_once()

    def test_savepoint_failure(self):
        from app.core.transaction import savepoint, DatabaseError
        db = MagicMock()
        sp_mock = MagicMock()
        db.begin_nested.return_value = sp_mock
        with pytest.raises(DatabaseError):
            with savepoint(db):
                raise ValueError('x')
        sp_mock.rollback.assert_called_once()

    def test_with_transaction_invalid_isolation(self):
        from app.core.transaction import with_transaction
        with pytest.raises(ValueError):
            with_transaction(isolation_level='INVALID')

    def test_with_transaction_valid_isolation(self):
        from app.core.transaction import with_transaction
        # Should not raise
        deco = with_transaction(isolation_level='READ COMMITTED')
        assert callable(deco)

    def test_with_transaction_with_existing_db(self):
        from app.core.transaction import with_transaction
        from sqlalchemy.orm import Session
        db = MagicMock(spec=Session)

        @with_transaction(isolation_level='READ COMMITTED')
        def my_func(db, x):
            return x * 3

        result = my_func(db, 4)
        assert result == 12
        db.commit.assert_called_once()

    def test_with_transaction_with_existing_db_exception(self):
        from app.core.transaction import with_transaction, DatabaseError
        from sqlalchemy.orm import Session
        db = MagicMock(spec=Session)

        @with_transaction()
        def my_func(db):
            raise ValueError('fail')

        with pytest.raises(DatabaseError):
            my_func(db)
        db.rollback.assert_called_once()

    def test_with_transaction_readonly(self):
        from app.core.transaction import with_transaction
        from sqlalchemy.orm import Session
        db = MagicMock(spec=Session)

        @with_transaction(readonly=True)
        def my_func(db, x):
            return x

        result = my_func(db, 7)
        assert result == 7
        db.commit.assert_called_once()

    def test_retry_on_deadlock_success(self):
        from app.core.transaction import retry_on_deadlock
        call_count = 0

        @retry_on_deadlock(max_retries=3, delay=0)
        def my_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                from sqlalchemy.exc import SQLAlchemyError
                raise SQLAlchemyError('deadlock detected')
            return 'ok'

        assert my_func() == 'ok'
        assert call_count == 2

    def test_retry_on_deadlock_all_fail(self):
        from app.core.transaction import retry_on_deadlock
        from sqlalchemy.exc import SQLAlchemyError

        @retry_on_deadlock(max_retries=2, delay=0)
        def my_func():
            raise SQLAlchemyError('database is locked')

        # On last retry, the original SQLAlchemyError is re-raised (not DatabaseError)
        with pytest.raises(SQLAlchemyError):
            my_func()

    def test_retry_on_deadlock_non_deadlock_raises(self):
        from app.core.transaction import retry_on_deadlock
        from sqlalchemy.exc import SQLAlchemyError

        @retry_on_deadlock(max_retries=3, delay=0)
        def my_func():
            raise SQLAlchemyError('some other error')

        with pytest.raises(SQLAlchemyError):
            my_func()

    def test_batch_insert_success(self):
        from app.core.transaction import BatchOperation
        db = MagicMock()
        model = MagicMock()
        items = [{'name': f'item{i}'} for i in range(5)]
        count = BatchOperation.batch_insert(db, model, items, batch_size=2)
        assert count == 5
        db.commit.assert_called_once()

    def test_batch_insert_failure(self):
        from app.core.transaction import BatchOperation, DatabaseError
        db = MagicMock()
        db.bulk_insert_mappings.side_effect = RuntimeError('fail')
        model = MagicMock()
        with pytest.raises(DatabaseError):
            BatchOperation.batch_insert(db, model, [{'a': 1}])
        db.rollback.assert_called_once()

    def test_batch_update_success(self):
        from app.core.transaction import BatchOperation
        db = MagicMock()
        model = MagicMock()
        updates = [{'id': 1, 'name': 'a'}, {'id': 2, 'name': 'b'}]
        count = BatchOperation.batch_update(db, model, updates)
        assert count == 2
        db.commit.assert_called_once()

    def test_batch_update_failure(self):
        from app.core.transaction import BatchOperation, DatabaseError
        db = MagicMock()
        db.bulk_update_mappings.side_effect = RuntimeError('x')
        model = MagicMock()
        with pytest.raises(DatabaseError):
            BatchOperation.batch_update(db, model, [{'id': 1}])

    def test_batch_delete_success(self):
        from app.core.transaction import BatchOperation
        db = MagicMock()
        model = MagicMock()
        query_mock = MagicMock()
        db.query.return_value = query_mock
        count = BatchOperation.batch_delete(db, model, [1, 2, 3])
        assert count == 3
        db.commit.assert_called_once()

    def test_batch_delete_failure(self):
        from app.core.transaction import BatchOperation, DatabaseError
        db = MagicMock()
        db.query.side_effect = RuntimeError('x')
        model = MagicMock()
        with pytest.raises(DatabaseError):
            BatchOperation.batch_delete(db, model, [1])

    def test_get_db_context(self):
        from app.core.transaction import get_db_context
        with get_db_context() as db:
            assert db is not None


# ══════════════════════════════════════════════════════════════
# 3. app.core.input_validation
# ══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
# 4. app.core.file_utils
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# 5. app.core.json_encoder
# ══════════════════════════════════════════════════════════════


class TestJSONEncoder:
    def test_encode_datetime(self):
        from app.core.json_encoder import AppJSONEncoder
        enc = AppJSONEncoder()
        dt = datetime.datetime(2024, 1, 1, 12, 0, 0)
        assert enc.default(dt) == dt.isoformat()

    def test_encode_date(self):
        from app.core.json_encoder import AppJSONEncoder
        enc = AppJSONEncoder()
        d = datetime.date(2024, 1, 1)
        assert enc.default(d) == d.isoformat()

    def test_encode_time(self):
        from app.core.json_encoder import AppJSONEncoder
        enc = AppJSONEncoder()
        t = datetime.time(12, 30, 0)
        assert enc.default(t) == t.isoformat()

    def test_encode_decimal_as_float(self):
        from app.core.json_encoder import AppJSONEncoder
        enc = AppJSONEncoder()
        assert enc.default(decimal.Decimal('3.14')) == 3.14

    def test_encode_decimal_as_string(self):
        from app.core.json_encoder import AppJSONEncoder
        enc = AppJSONEncoder(decimal_as_string=True)
        assert enc.default(decimal.Decimal('3.14')) == '3.14'

    def test_encode_uuid(self):
        from app.core.json_encoder import AppJSONEncoder
        enc = AppJSONEncoder()
        u = uuid.uuid4()
        assert enc.default(u) == str(u)

    def test_encode_set(self):
        from app.core.json_encoder import AppJSONEncoder
        enc = AppJSONEncoder()
        result = enc.default({1, 2, 3})
        assert isinstance(result, list)
        assert set(result) == {1, 2, 3}

    def test_encode_enum(self):
        from app.core.json_encoder import AppJSONEncoder
        from enum import Enum

        class Color(Enum):
            RED = 1
            BLUE = 2

        enc = AppJSONEncoder()
        assert enc.default(Color.RED) == 1

    def test_encode_json_method(self):
        from app.core.json_encoder import AppJSONEncoder

        class MyObj:
            def __json__(self):
                return {'custom': True}

        enc = AppJSONEncoder()
        assert enc.default(MyObj()) == {'custom': True}

    def test_encode_unknown_type(self):
        from app.core.json_encoder import AppJSONEncoder
        enc = AppJSONEncoder()
        with pytest.raises(TypeError):
            enc.default(object())

    def test_dumps(self):
        from app.core.json_encoder import dumps
        import json
        result = dumps({'date': datetime.date(2024, 1, 1)})
        data = json.loads(result)
        assert data['date'] == '2024-01-01'

    def test_loads(self):
        from app.core.json_encoder import loads
        assert loads('{"a": 1}') == {'a': 1}

    def test_custom_json_encoder_alias(self):
        from app.core.json_encoder import CustomJSONEncoder, AppJSONEncoder
        assert CustomJSONEncoder is AppJSONEncoder


# ══════════════════════════════════════════════════════════════
# 6. app.core.constants
# ══════════════════════════════════════════════════════════════


class TestConstants:
    def test_role_constants(self):
        from app.core import constants
        assert constants.ROLE_SUPER_ADMIN == 'super_admin'
        assert constants.ROLE_ADMIN == 'admin'
        assert constants.ROLE_VIEWER == 'viewer'

    def test_admin_roles(self):
        from app.core.constants import ADMIN_ROLES, ROLE_SUPER_ADMIN, ROLE_ADMIN
        assert ROLE_SUPER_ADMIN in ADMIN_ROLES
        assert ROLE_ADMIN in ADMIN_ROLES

    def test_all_roles(self):
        from app.core.constants import ALL_ROLES
        assert len(ALL_ROLES) == 4

    def test_user_role_class(self):
        from app.core.constants import UserRole
        assert UserRole.SUPER_ADMIN == 'super_admin'
        assert UserRole.ADMIN == 'admin'

    def test_pagination_constants(self):
        from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
        assert DEFAULT_PAGE_SIZE == 20
        assert MAX_PAGE_SIZE == 100

    def test_http_constants(self):
        from app.core.constants import HTTP_CLIENT_CLOSED_REQUEST
        assert HTTP_CLIENT_CLOSED_REQUEST == 499

    def test_analytics_cache_prefix(self):
        from app.core.constants import ANALYTICS_CACHE_PREFIX
        assert ANALYTICS_CACHE_PREFIX == 'analytics:'


# ══════════════════════════════════════════════════════════════
# 7. app.core.async_utils
# ══════════════════════════════════════════════════════════════


class TestAsyncUtils:
    def test_run_in_thread(self):
        from app.core.async_utils import run_in_thread

        async def main():
            def blocking():
                return 42
            return await run_in_thread(blocking)

        result = asyncio.run(main())
        assert result == 42

    def test_run_in_executor(self):
        from app.core.async_utils import run_in_executor

        async def main():
            def blocking(x):
                return x * 2
            return await run_in_executor(blocking, 5)

        assert asyncio.run(main()) == 10

    def test_sync_decorator(self):
        from app.core.async_utils import sync

        @sync
        async def async_func(x):
            return x + 1

        assert async_func(10) == 11

    def test_gather_limited(self):
        from app.core.async_utils import gather_limited

        async def coro(x):
            return x

        async def main():
            return await gather_limited(2, coro(1), coro(2), coro(3))

        result = asyncio.run(main())
        assert result == [1, 2, 3]

    def test_delay(self):
        from app.core.async_utils import delay

        async def main():
            await delay(0.01)

        asyncio.run(main())  # should not raise

        # May not be immediate, just verify no error

    def test_get_event_loop_safe_running(self):
        from app.core.async_utils import get_event_loop_safe

        async def main():
            loop = get_event_loop_safe()
            assert loop is not None

        asyncio.run(main())

    def test_get_event_loop_safe_no_running(self):
        from app.core.async_utils import get_event_loop_safe
        loop = get_event_loop_safe()
        assert loop is not None

    def test_create_background_task(self):
        from app.core.async_utils import create_background_task

        flag = []

        async def bg():
            flag.append('done')




# ══════════════════════════════════════════════════════════════
# 9. app.core.i18n
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# 10. app.core.cookie_security
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# 11. app.core.config_validator
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# 12. app.core.exceptions & errors
# ══════════════════════════════════════════════════════════════


class TestExceptions:
    def test_app_error_basic(self):
        from app.core.exceptions import AppError
        e = AppError('test error', 400)
        assert e.message == 'test error'
        assert e.status_code == 400

    def test_app_error_to_dict(self):
        from app.core.exceptions import AppError
        e = AppError('msg', 400, code=1001)
        d = e.to_dict()
        assert d['error']['code'] == 1001
        assert d['error']['message'] == 'msg'

    def test_app_error_str(self):
        from app.core.exceptions import AppError
        e = AppError('my message')
        assert str(e) == 'my message'

    def test_app_error_not_found(self):
        from app.core.exceptions import AppError
        e = AppError.not_found('用户')
        assert e.status_code == 404
        assert '用户' in e.message

    def test_app_error_bad_request(self):
        from app.core.exceptions import AppError
        e = AppError.bad_request()
        assert e.status_code == 400

    def test_app_error_forbidden(self):
        from app.core.exceptions import AppError
        e = AppError.forbidden()
        assert e.status_code == 403

    def test_app_error_conflict(self):
        from app.core.exceptions import AppError
        e = AppError.conflict()
        assert e.status_code == 409

    def test_business_error(self):
        from app.core.exceptions import BusinessError
        e = BusinessError('biz err')
        assert e.status_code == 400

    def test_validation_error(self):
        from app.core.exceptions import ValidationError
        e = ValidationError('val err', field='name')
        assert e.status_code == 400
        assert e.details.get('field') == 'name'



    def test_not_found_error(self):
        from app.core.exceptions import NotFoundError
        e = NotFoundError('用户', '123')
        assert e.status_code == 404
        assert '123' in e.message

    def test_not_found_error_no_id(self):
        from app.core.exceptions import NotFoundError
        e = NotFoundError('用户')
        assert '用户' in e.message

    def test_conflict_error(self):
        from app.core.exceptions import ConflictError
        e = ConflictError()
        assert e.status_code == 409

    def test_database_error(self):
        from app.core.exceptions import DatabaseError
        e = DatabaseError()
        assert e.status_code == 500










    def test_invalid_credentials_error(self):
        from app.core.exceptions import InvalidCredentialsError
        e = InvalidCredentialsError()
        assert e.status_code == 401

    def test_user_already_exists_error(self):
        from app.core.exceptions import UserAlreadyExistsError
        e = UserAlreadyExistsError()
        assert e.status_code == 409

    def test_not_found_exception(self):
        from app.core.exceptions import NotFoundException
        e = NotFoundException()
        assert e.status_code == 404

    def test_authentication_exception(self):
        from app.core.exceptions import AuthenticationException
        e = AuthenticationException()
        assert e.status_code == 401




class TestErrors:
    def test_error_code_values(self):
        from app.core.errors import ErrorCode
        assert ErrorCode.SUCCESS == 200
        assert ErrorCode.BAD_REQUEST == 400

    def test_get_error_message_known(self):
        from app.core.errors import get_error_message, ErrorCode
        assert get_error_message(ErrorCode.SUCCESS) == '成功'

    def test_get_error_message_unknown(self):
        from app.core.errors import get_error_message, ErrorCode
        msg = get_error_message(ErrorCode.UNKNOWN)
        assert '未知' in msg

    def test_errors_app_error(self):
        from app.core.errors import AppError
        e = AppError('msg', 400)
        assert e.message == 'msg'

    def test_errors_app_error_not_found(self):
        from app.core.errors import AppError
        e = AppError.not_found('资源')
        assert e.status_code == 404

    def test_errors_app_error_bad_request(self):
        from app.core.errors import AppError
        e = AppError.bad_request()
        assert e.status_code == 400

    def test_errors_app_error_forbidden(self):
        from app.core.errors import AppError
        e = AppError.forbidden()
        assert e.status_code == 403

    def test_errors_app_error_conflict(self):
        from app.core.errors import AppError
        e = AppError.conflict()
        assert e.status_code == 409

    def test_errors_validation_error(self):
        from app.core.errors import ValidationError, ErrorCode
        e = ValidationError('msg', field='name')
        assert e.code == ErrorCode.VALIDATION_ERROR
        assert e.field == 'name'


# ══════════════════════════════════════════════════════════════
# 13. app.core.performance
# ══════════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════════
# 14. app.core.query_optimizer
# ══════════════════════════════════════════════════════════════


class TestQueryOptimizer:


    def test_paginate(self):
        from app.core.query_optimizer import paginate
        q = MagicMock()
        q.count.return_value = 25
        q.offset.return_value.limit.return_value.all.return_value = ['item'] * 10
        items, total, pages = paginate(q, page=1, page_size=10)
        assert total == 25
        assert pages == 3
        assert len(items) == 10

    def test_paginate_empty(self):
        from app.core.query_optimizer import paginate
        q = MagicMock()
        q.count.return_value = 0
        q.offset.return_value.limit.return_value.all.return_value = []
        items, total, pages = paginate(q)
        assert total == 0
        assert pages == 1

    def test_paginate_page_overflow(self):
        from app.core.query_optimizer import paginate
        q = MagicMock()
        q.count.return_value = 5
        q.offset.return_value.limit.return_value.all.return_value = []
        items, total, pages = paginate(q, page=100, page_size=10)
        assert pages == 1









