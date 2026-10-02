"""`models.base.UtcDateTime` 与 `is_datetime_type` 契约测试。

覆盖三类语义（对应 2026-10-02 时间基准统一）：
1. 绑定：aware → 换算为 naive UTC；naive 按约定原样落库；非 datetime 值**放行**
   （不得收窄基础类型原本接受的输入 —— 早期版本在此处误伤数据包导入）。
2. 读取：naive（库中形态）→ aware UTC；aware → 统一换算 UTC；非 datetime 放行。
3. 类型识别：`is_datetime_type` 必须**穿透 TypeDecorator 包装**，否则
   「按列类型识别时间列」的代码（如数据包校验器）会静默失配。
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, Date, DateTime, Integer, String

from app.models import Base
from app.models.base import UtcDateTime, is_datetime_type


@pytest.fixture
def col_type():
    """返回一个未绑定到数据库的 UtcDateTime 实例（直接测处理器）。"""
    return UtcDateTime()


class TestBindProcessor:
    def test_aware_utc_is_stripped_to_naive(self, col_type):
        proc = col_type.bind_processor(None)
        value = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
        assert proc(value) == datetime(2026, 5, 1, 12, 0)
        assert proc(value).tzinfo is None

    def test_aware_non_utc_converted_to_utc_wall_clock(self, col_type):
        proc = col_type.bind_processor(None)
        value = datetime(2026, 5, 1, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        assert proc(value) == datetime(2026, 5, 1, 4, 0)

    def test_naive_treated_as_utc_unchanged(self, col_type):
        proc = col_type.bind_processor(None)
        value = datetime(2026, 5, 1, 12, 0)
        assert proc(value) is value

    def test_non_datetime_passthrough(self, col_type):
        """脏字符串必须原样放行 —— 由隐含类型决定如何处理，装饰器不得收窄输入。"""
        proc = col_type.bind_processor(None)
        assert proc("2024/3/5") == "2024/3/5"
        assert proc(None) is None


class TestResultProcessor:
    def test_naive_read_back_becomes_aware_utc(self, col_type):
        proc = col_type.result_processor(None, None)
        value = proc(datetime(2026, 5, 1, 12, 0))
        assert value == datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
        assert value.tzinfo is not None

    def test_aware_non_utc_normalized_to_utc(self, col_type):
        proc = col_type.result_processor(None, None)
        value = proc(datetime(2026, 5, 1, 12, 0, tzinfo=timezone(timedelta(hours=8))))
        assert value == datetime(2026, 5, 1, 4, 0, tzinfo=timezone.utc)

    def test_none_passthrough(self, col_type):
        proc = col_type.result_processor(None, None)
        assert proc(None) is None

    def test_non_datetime_passthrough(self, col_type):
        proc = col_type.result_processor(None, None)
        assert proc("raw") == "raw"


class TestConstructorCompat:
    def test_timezone_kwarg_tolerated(self):
        """兼容历史写法 UtcDateTime(timezone=True)：时区语义由本类固定，忽略该参数。"""
        assert UtcDateTime(timezone=True).impl.__class__ is DateTime


class TestIsDatetimeType:
    def test_plain_datetime_type(self):
        assert is_datetime_type(DateTime()) is True

    def test_date_type(self):
        assert is_datetime_type(Date()) is True

    def test_decorated_type_unwrapped(self):
        """核心契约：TypeDecorator 包装后仍须识别为时间列。"""
        assert is_datetime_type(UtcDateTime()) is True

    def test_non_datetime_type(self):
        assert is_datetime_type(Integer()) is False
        assert is_datetime_type(String(50)) is False

    def test_model_columns_recognized(self):
        """真实模型列：UtcDateTime 列被识别、其他列不被误判。"""

        class _Probe(Base):
            __tablename__ = "probe_utcdatetime_contract"
            id = Column(Integer, primary_key=True)
            happened_at = Column(UtcDateTime(), nullable=True)
            name = Column(String(20))

        cols = _Probe.__table__.columns
        assert is_datetime_type(cols["happened_at"].type) is True
        assert is_datetime_type(cols["name"].type) is False
        assert is_datetime_type(cols["id"].type) is False


class TestRoundTripSemantics:
    """写—读往返不变量：同一墙钟在 UTC 语义下闭合。"""

    def test_write_read_round_trip(self, col_type):
        bind = col_type.bind_processor(None)
        read = col_type.result_processor(None, None)
        original = datetime(2026, 3, 4, 5, 6, 7, tzinfo=timezone(timedelta(hours=8)))
        assert read(bind(original)) == datetime(2026, 3, 3, 21, 6, 7, tzinfo=timezone.utc)
