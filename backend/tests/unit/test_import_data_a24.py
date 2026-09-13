"""app.api.v1.import_export.import_data 覆盖补充测试（a24）

缺口：230（导入文件名为空）、304/306（示例行/空行跳过）、335-339（实体校验错误分组）、
362（校验文件名为空）、435-438（school 预览分支）、457（错误转换）、
486（预览文件名为空）、502（预览文件过大）、521（预览无效行计数）。
"""
import io

import pytest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, UploadFile

import app.api.v1.import_export.import_data as id_module
from app.api.v1.import_export.import_data import (
    _import_entities,
    _parse_excel_rows,
    _setup_preview_entity,
    preview_import_data,
    validate_import_data,
)
from app.services.entity_import_validator import EntityImportValidator


def _make_xlsx(rows) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(content: bytes, filename):
    return UploadFile(file=io.BytesIO(content), filename=filename)


class TestImportEntitiesValidation:
    @pytest.mark.asyncio
    async def test_empty_filename_rejected(self):
        file = _upload(b"data", None)
        with pytest.raises(HTTPException) as exc_info:
            await _import_entities(
                file=file,
                mode="incremental",
                entity_type="supported_village",
                current_user=MagicMock(id=1),
                db=MagicMock(),
            )
        assert exc_info.value.status_code == 400
        assert "文件名不能为空" in exc_info.value.detail


class TestParseExcelRows:
    def test_example_row_and_blank_row_skipped(self):
        content = _make_xlsx([
            ["村庄名称"],
            ["某某部门"],   # 第2行示例标记 -> 跳过（304）
            [None],          # 全空行 -> 跳过（306）
            ["真实村"],
        ])
        rows = _parse_excel_rows(content, lambda headers: {0: "village_name"}, ["某某部门", "示例部门"])
        assert rows == [{"village_name": "真实村"}]


class TestValidateImportData:
    @pytest.mark.asyncio
    async def test_empty_filename_rejected(self):
        file = _upload(b"data", None)
        with pytest.raises(HTTPException) as exc_info:
            await validate_import_data(
                file=file,
                entity_type="supported_village",
                validate_county=True,
                validate_tiered_level=True,
                current_user=MagicMock(),
            )
        assert exc_info.value.status_code == 400
        assert "文件名不能为空" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_entity_validation_summary_with_errors(self):
        """非村庄实体校验出错时构建错误分组统计（335-339）"""
        error = MagicMock()
        error.error_code.value = "REQUIRED_FIELD"
        error.field_name = "name"
        error.to_dict.return_value = {"row_number": 2, "field_name": "name"}

        result = MagicMock()
        result.is_valid = False
        result.total_rows = 1
        result.valid_rows = 0
        result.errors = [error]
        result.warnings = []

        validator = MagicMock()
        validator.validate_file_format.return_value = (True, "")
        validator.validate_file_size.return_value = (True, "")
        validator.validate_batch.return_value = result
        validator._get_field_label.return_value = "名称"

        file = _upload(_make_xlsx([["名称"], ["项目A"]]), "projects.xlsx")
        with patch.object(id_module, "_resolve_validator", return_value=(validator, lambda h: {0: "name"}, [])):
            resp = await validate_import_data(
                file=file,
                entity_type="project",
                validate_county=True,
                validate_tiered_level=True,
                current_user=MagicMock(),
            )

        assert resp.is_valid is False
        assert resp.invalid_rows == 1
        assert resp.errors_by_type == {"REQUIRED_FIELD": 1}
        assert resp.errors_by_field == {"名称": 1}
        assert resp.first_errors == [{"row_number": 2, "field_name": "name"}]


class TestSetupPreviewEntity:
    def test_school_branch(self):
        db = MagicMock()
        db.query.return_value.all.return_value = [("阳光小学",), (None,)]
        validator, duplicate_field, existing_names = _setup_preview_entity("school", db)
        assert isinstance(validator, EntityImportValidator)
        assert duplicate_field == validator.config.get("duplicate_key", "name")
        assert existing_names == {"阳光小学"}

    def test_fund_branch(self):
        db = MagicMock()
        db.query.return_value.all.return_value = [("专项资金",)]
        validator, duplicate_field, existing_names = _setup_preview_entity("fund", db)
        assert isinstance(validator, EntityImportValidator)
        assert duplicate_field == validator.config.get("duplicate_key", "name")
        assert existing_names == {"专项资金"}


class TestPreviewImportData:
    @pytest.mark.asyncio
    async def test_empty_filename_rejected(self):
        file = _upload(b"data", None)
        with pytest.raises(HTTPException) as exc_info:
            await preview_import_data(
                file=file,
                entity_type="supported_village",
                current_user=MagicMock(),
                db=MagicMock(),
            )
        assert exc_info.value.status_code == 400
        assert "文件名不能为空" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_file_too_large_rejected(self):
        """R2：体积闸门由「分块读取上限」承担（原 validator.validate_file_size
        的事后校验已被前移，避免先整包入内存再拒绝）。"""
        validator = MagicMock()
        validator.validate_file_format.return_value = (True, "")

        file = _upload(b"x" * 64, "projects.xlsx")
        with patch.object(id_module, "_IMPORT_MAX_FILE_SIZE", 16), \
                patch.object(id_module, "_IMPORT_MAX_FILE_SIZE_MSG", "文件大小超过限制"):
            with patch.object(id_module, "_setup_preview_entity", return_value=(validator, "name", set())):
                with pytest.raises(HTTPException) as exc_info:
                    await preview_import_data(
                        file=file,
                        entity_type="project",
                        current_user=MagicMock(),
                        db=MagicMock(),
                    )
        assert exc_info.value.status_code == 400
        assert "文件大小超过限制" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_preview_with_invalid_and_duplicate_rows(self):
        """行校验失败计数（521）+ 错误对象转换（457）+ 重复提示"""
        error = MagicMock()
        error.row_number = 2
        error.field_name = "name"
        error.error_code.value = "REQUIRED_FIELD"
        error.message = "名称为必填项"
        error.value = None

        validator = MagicMock()
        validator.validate_file_format.return_value = (True, "")
        validator.validate_file_size.return_value = (True, "")
        validator.validate_row.side_effect = lambda row, idx: [] if idx == 1 else [error]
        validator._generate_warnings.return_value = []

        importer = MagicMock()
        importer.parse_excel.return_value = ([{"name": "已有"}, {"name": ""}], ["名称"])

        file = _upload(_make_xlsx([["名称"], ["已有"], [""]]), "projects.xlsx")
        with patch.object(id_module, "_setup_preview_entity", return_value=(validator, "name", {"已有"})), \
             patch.object(id_module, "ExcelImporterService", return_value=importer):
            resp = await preview_import_data(
                file=file,
                entity_type="project",
                current_user=MagicMock(),
                db=MagicMock(),
            )

        assert resp.total_rows == 2
        assert resp.valid_rows == 1
        assert resp.invalid_rows == 1
        assert resp.duplicate_in_db_rows == 1
        assert resp.rows[0].is_duplicate_in_db is True
        assert resp.rows[0].has_error is False
        assert resp.rows[1].has_error is True
        assert resp.rows[1].errors[0].error_code == "REQUIRED_FIELD"
        assert resp.rows[1].errors[0].value is None
        assert "重复" in resp.warnings[0]
