"""W22：数据包导出值归一化（enum / datetime / Decimal / 非 JSON 原生）覆盖率补齐。

背景：数据上报链路断点修复（枚举名→枚举值）后，导出链路新增枚举归一与通用 JSON
归一化；本文件直接对模块级 helper 做单元断言（补齐全量覆盖率缺口行）。
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum


class _DemoEnum(Enum):
    PRIMARY = "primary"
    INACTIVE = "inactive"


def test_enum_name_normalized_to_value():
    from app.services.data_package_service import _normalize_enum_export_value

    assert _normalize_enum_export_value("PRIMARY", _DemoEnum) == "primary"


def test_enum_value_passthrough_via_value_lookup():
    from app.services.data_package_service import _normalize_enum_export_value

    assert _normalize_enum_export_value("inactive", _DemoEnum) == "inactive"


def test_enum_unknown_string_returned_as_is():
    from app.services.data_package_service import _normalize_enum_export_value

    assert _normalize_enum_export_value("legacy_status", _DemoEnum) == "legacy_status"


def test_enum_none_class_and_non_string_passthrough():
    from app.services.data_package_service import _normalize_enum_export_value

    assert _normalize_enum_export_value("PRIMARY", None) == "PRIMARY"
    assert _normalize_enum_export_value(1, _DemoEnum) == 1


def test_enum_column_map_collects_enum_columns():
    from app.services.data_package_service import _enum_column_map
    from app.models.school import School

    mapping = _enum_column_map(School)
    assert isinstance(mapping, dict)


def test_normalize_datetime_to_iso():
    from app.services.data_package_service import _normalize_export_data_value

    value = datetime(2026, 10, 18, 12, 30, 45)
    assert _normalize_export_data_value(value) == "2026-10-18T12:30:45"


def test_normalize_decimal_to_float():
    from app.services.data_package_service import _normalize_export_data_value

    assert _normalize_export_data_value(Decimal("12.50")) == 12.5


def test_normalize_unknown_object_to_str():
    from app.services.data_package_service import _normalize_export_data_value

    class _Custom:
        def __str__(self):
            return "custom-value"

    assert _normalize_export_data_value(_Custom()) == "custom-value"


def test_normalize_json_native_values_passthrough():
    from app.services.data_package_service import _normalize_export_data_value

    for value in (None, "text", 1, 1.5, True, [1, 2], {"k": "v"}):
        assert _normalize_export_data_value(value) == value
