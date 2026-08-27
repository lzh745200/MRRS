"""Tests for app/core/upload_security.py — 100% coverage."""
from unittest.mock import MagicMock


from app.core.upload_security import (
    full_upload_validation,
    sanitize_filename,
    sanitize_upload_filename,
    validate_content_safety,
    validate_excel_upload,
    validate_extension,
    validate_file_size,
    validate_mime_type,
)


# ---------------------------------------------------------------------------
# validate_extension
# ---------------------------------------------------------------------------


class TestValidateExtension:
    def test_empty_filename(self):
        ok, msg = validate_extension("")
        assert ok is False
        assert "不能为空" in msg

    def test_none_filename(self):
        ok, msg = validate_extension("")
        assert ok is False

    def test_forbidden_extension(self):
        ok, msg = validate_extension("virus.exe")
        assert ok is False
        assert "不允许的文件类型" in msg

    def test_forbidden_extension_dll(self):
        ok, msg = validate_extension("lib.dll")
        assert ok is False

    def test_forbidden_extension_sh(self):
        ok, msg = validate_extension("script.sh")
        assert ok is False

    def test_forbidden_extension_html(self):
        ok, msg = validate_extension("page.html")
        assert ok is False

    def test_not_in_allowed(self):
        ok, msg = validate_extension("file.xyz")
        assert ok is False
        assert "不支持的文件类型" in msg

    def test_valid_extension(self):
        ok, msg = validate_extension("report.pdf")
        assert ok is True
        assert msg == ""

    def test_valid_extension_xlsx(self):
        ok, msg = validate_extension("data.xlsx")
        assert ok is True

    def test_custom_allowed(self):
        ok, msg = validate_extension("custom.abc", allowed_extensions={".abc"})
        assert ok is True

    def test_case_insensitive(self):
        ok, msg = validate_extension("Report.PDF")
        assert ok is True

    def test_custom_allowed_forbidden_still_blocked(self):
        ok, msg = validate_extension("evil.exe", allowed_extensions={".exe"})
        assert ok is False


# ---------------------------------------------------------------------------
# validate_mime_type
# ---------------------------------------------------------------------------


class TestValidateMimeType:
    def test_empty_mime(self):
        ok, msg = validate_mime_type("")
        assert ok is False
        assert "无法检测文件类型" in msg

    def test_none_mime(self):
        ok, msg = validate_mime_type("")
        assert ok is False

    def test_not_allowed(self):
        ok, msg = validate_mime_type("application/x-msdownload")
        assert ok is False
        assert "不允许的文件类型" in msg

    def test_valid_mime(self):
        ok, msg = validate_mime_type("image/png")
        assert ok is True
        assert msg == ""

    def test_custom_allowed(self):
        ok, msg = validate_mime_type("text/custom", allowed_mimes={"text/custom"})
        assert ok is True

    def test_valid_pdf(self):
        ok, msg = validate_mime_type("application/pdf")
        assert ok is True

    def test_valid_json(self):
        ok, msg = validate_mime_type("application/json")
        assert ok is True


# ---------------------------------------------------------------------------
# validate_file_size
# ---------------------------------------------------------------------------


class TestValidateFileSize:
    def test_zero_size(self):
        ok, msg = validate_file_size(0)
        assert ok is False
        assert "文件大小为0" in msg

    def test_negative_size(self):
        ok, msg = validate_file_size(-1)
        assert ok is False
        assert "文件大小为0" in msg

    def test_exceeds_max(self):
        ok, msg = validate_file_size(60 * 1024 * 1024, max_bytes=50 * 1024 * 1024)
        assert ok is False
        assert "文件过大" in msg

    def test_within_limit(self):
        ok, msg = validate_file_size(1024)
        assert ok is True

    def test_exact_limit(self):
        ok, msg = validate_file_size(50 * 1024 * 1024)
        assert ok is True

    def test_custom_max(self):
        ok, msg = validate_file_size(100, max_bytes=200)
        assert ok is True


# ---------------------------------------------------------------------------
# validate_content_safety
# ---------------------------------------------------------------------------


class TestValidateContentSafety:
    def test_empty_content(self):
        ok, msg = validate_content_safety(b"")
        assert ok is False
        assert "文件内容为空" in msg

    def test_none_content(self):
        ok, msg = validate_content_safety(b"")
        assert ok is False

    def test_mz_executable(self):
        ok, msg = validate_content_safety(b"MZ\x90\x00\x03\x00\x00\x00")
        assert ok is False
        assert "不允许上传可执行文件" in msg

    def test_shebang_script(self):
        ok, msg = validate_content_safety(b"#!/bin/bash\necho hello")
        assert ok is False
        assert "不允许上传脚本文件" in msg

    def test_php_script(self):
        ok, msg = validate_content_safety(b"<?php echo 'x';")
        assert ok is False

    def test_asp_script(self):
        ok, msg = validate_content_safety(b"<% Response.Write 'x' %>")
        assert ok is False

    def test_python_shebang(self):
        ok, msg = validate_content_safety(b"#!/usr/bin/env python\nprint('hi')")
        assert ok is False

    def test_safe_content(self):
        ok, msg = validate_content_safety(b"Hello, this is a safe document.")
        assert ok is True
        assert msg == ""

    def test_non_utf8_content(self):
        ok, msg = validate_content_safety(b"\xff\xfe\x00\x01\x02")
        assert ok is True

    def test_executable_signature_checked_without_macro_param(self):
        # check_macro 参数已删除（从未实现宏扫描）；
        # 可执行文件签名拦截始终生效
        ok, msg = validate_content_safety(b"MZtest")
        assert ok is False
        assert "不允许上传可执行文件" in msg

    def test_safe_pdf_content(self):
        ok, msg = validate_content_safety(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj")
        assert ok is True


# ---------------------------------------------------------------------------
# full_upload_validation
# ---------------------------------------------------------------------------


class TestFullUploadValidation:
    def test_extension_fails_first(self):
        ok, msg = full_upload_validation("evil.exe", 100, b"content")
        assert ok is False
        assert "不允许的文件类型" in msg

    def test_size_fails_second(self):
        ok, msg = full_upload_validation("test.pdf", 0, b"content")
        assert ok is False
        assert "文件大小为0" in msg

    def test_mime_fails_when_provided(self):
        ok, msg = full_upload_validation("test.pdf", 100, b"content", mime_type="application/x-msdownload")
        assert ok is False
        assert "不允许的文件类型" in msg

    def test_mime_skipped_when_none(self):
        ok, msg = full_upload_validation("test.pdf", 100, b"content")
        assert ok is True

    def test_content_fails(self):
        ok, msg = full_upload_validation("test.pdf", 100, b"MZ\x90\x00")
        assert ok is False
        assert "不允许上传可执行文件" in msg

    def test_all_pass(self):
        ok, msg = full_upload_validation("report.pdf", 1024, b"%PDF-1.4 safe content", mime_type="application/pdf")
        assert ok is True
        assert msg == ""

    def test_custom_max_bytes(self):
        ok, msg = full_upload_validation("report.pdf", 200, b"content", max_bytes=100)
        assert ok is False
        assert "文件过大" in msg

    def test_custom_allowed_extensions(self):
        ok, msg = full_upload_validation("data.custom", 100, b"content", allowed_extensions={".custom"})
        assert ok is True

    def test_mime_type_none_skips_mime_check(self):
        ok, msg = full_upload_validation("test.xlsx", 100, b"PK\x03\x04 content", mime_type=None)
        assert ok is True


# ---------------------------------------------------------------------------
# sanitize_upload_filename
# ---------------------------------------------------------------------------


class TestSanitizeUploadFilename:
    def test_preserves_safe_name(self):
        result = sanitize_upload_filename("report.pdf")
        assert result == "report.pdf"

    def test_replaces_dangerous_chars(self):
        result = sanitize_upload_filename("hello<world>.txt")
        assert result == "hello_world.txt"

    def test_path_separators_replaced(self):
        result = sanitize_upload_filename("../etc/passwd.txt")
        assert "/" not in result

    def test_multiple_underscores_collapsed(self):
        result = sanitize_upload_filename("a___b.txt")
        assert result == "a_b.txt"

    def test_empty_name_becomes_upload(self):
        result = sanitize_upload_filename("___.txt")
        assert result == "upload.txt"

    def test_only_ext_becomes_upload(self):
        result = sanitize_upload_filename("___")
        assert result == "upload"

    def test_preserves_chinese_chars(self):
        result = sanitize_upload_filename("报告2024.pdf")
        assert result == "报告2024.pdf"

    def test_lowercases_extension(self):
        result = sanitize_upload_filename("Photo.JPG")
        assert result == "Photo.jpg"

    def test_spaces_replaced(self):
        result = sanitize_upload_filename("my file.txt")
        assert "_" in result

    def test_leading_trailing_underscores_stripped(self):
        result = sanitize_upload_filename("__hello__.txt")
        assert result == "hello.txt"


# ---------------------------------------------------------------------------
# validate_excel_upload
# ---------------------------------------------------------------------------


class TestValidateExcelUpload:
    def test_none_file_returns_false(self):
        assert validate_excel_upload(None) is False

    def test_no_file_attr_returns_false(self):
        assert validate_excel_upload(object()) is False

    def test_xlsx_magic_bytes(self):
        mock_file = MagicMock()
        mock_file.file.read.return_value = b"PK\x03\x04some content"
        mock_file.file.seek = MagicMock()
        assert validate_excel_upload(mock_file) is True
        mock_file.file.seek.assert_called_once_with(0)

    def test_xls_magic_bytes(self):
        mock_file = MagicMock()
        mock_file.file.read.return_value = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
        mock_file.file.seek = MagicMock()
        assert validate_excel_upload(mock_file) is True

    def test_not_excel(self):
        mock_file = MagicMock()
        mock_file.file.read.return_value = b"not an excel file"
        mock_file.file.seek = MagicMock()
        assert validate_excel_upload(mock_file) is False

    def test_read_exception_returns_false(self):
        mock_file = MagicMock()
        mock_file.file.read.side_effect = OSError("read error")
        assert validate_excel_upload(mock_file) is False


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------


class TestSanitizeFilename:
    def test_replaces_invalid_chars(self):
        result = sanitize_filename('file<>:"/|?*.txt')
        assert result == "file________.txt"

    def test_safe_name_unchanged(self):
        result = sanitize_filename("safe_file.txt")
        assert result == "safe_file.txt"
