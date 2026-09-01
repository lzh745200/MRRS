# -*- coding: utf-8 -*-
"""excel_importer_service 覆盖率补测：pandas 快速读取导入失败回退(36-37) + SQLAlchemyError 兜底(305-335)"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

import app.services.excel_importer_service as mod
from app.models.import_history import ImportMode


def test_pandas_fast_read_import_fallback():
    """batch_import_optimizer 不可导入时走 36-37 回退分支（exec 隔离执行，避免 reload 名称遮蔽）"""
    import types

    m = types.ModuleType("excel_importer_cov_exec")
    m.__file__ = mod.__file__
    with open(mod.__file__, encoding="utf-8") as _f:
        src = _f.read()
    with patch.dict(
        sys.modules,
        {"app.services.batch_import_optimizer": None, "excel_importer_cov_exec": m},
    ):
        exec(compile(src, mod.__file__, "exec"), m.__dict__)
    assert m._HAS_PANDAS_FAST_READ is False


def test_import_data_sqlalchemy_error_handler():
    db = MagicMock()
    svc = mod.ExcelImporterService(db)
    svc.parse_excel = MagicMock(return_value=([{"village_name": "幸福村"}], ["village_name"]))
    svc.validator = MagicMock()
    svc.validator.validate_batch.return_value = MagicMock(is_valid=True, errors=[])
    svc.validator.check_duplicates.return_value = []
    svc._import_full_mode = MagicMock(side_effect=SQLAlchemyError("disk io error"))

    result = svc.import_data(
        file_content=b"xlsx-bytes",
        file_name="villages.xlsx",
        file_size=100,
        user_id=1,
        mode=ImportMode.FULL,
        entity_type="supported_village",
    )

    assert result.success is False
    assert result.failed_rows == result.total_rows == 1
    assert len(result.errors) == 1
    assert "数据库错误" in result.errors[0].message
    assert "disk io error" in result.errors[0].message
    db.rollback.assert_called()
    # 历史记录创建两次：初始 PROCESSING 一次 + 回滚后重建 FAILED 一次
    assert db.add.call_count == 2
    db.commit.assert_called()
