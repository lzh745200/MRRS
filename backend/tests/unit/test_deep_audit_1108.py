"""深度审计补测（R61，2026-11-08）：数据包导入的 datetime 启发式收敛。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from app.models.project import Project
from app.services.data_package_service import DataPackageService


def _service() -> DataPackageService:
    return DataPackageService(db=MagicMock())


def test_text_with_T_is_not_coerced_to_datetime():
    """含字母 T 的普通文本（如 PART-TIME）必须保持字符串。"""
    out = _service()._clean_import_record(
        {"remarks": "PART-TIME"},
        {"remarks"},
        org_id=1,
        i=0,
        model=Project,
    )
    assert out["remarks"] == "PART-TIME"


def test_strict_iso_datetime_with_T_is_parsed():
    """严格 ISO 形态（yyyy-mm-ddThh:mm...）仍按 datetime 解析。"""
    out = _service()._clean_import_record(
        {"created_at": "2024-01-02T03:04:05"},
        {"created_at"},
        org_id=1,
        i=0,
        model=Project,
    )
    assert out["created_at"] == datetime(2024, 1, 2, 3, 4, 5)
