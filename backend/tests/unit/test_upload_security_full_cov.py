"""app.core.upload_security 全覆盖补充测试。

针对 39% 覆盖率缺口，补齐 validate_extension / validate_mime_type /
validate_file_size / validate_content_safety / validate_excel_upload /
sanitize_filename 的全部分支。
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core import upload_security as us


class TestValidateExtension:
    def test_empty_filename(self):
        ok, msg = us.validate_extension("")
        assert ok is False and "文件名不能为空" in msg

    def test_forbidden_extension(self):
        ok, msg = us.validate_extension("malware.exe")
        assert ok is False and "不允许的文件类型" in msg

    def test_not_allowed_extension(self):
        ok, msg = us.validate_extension("archive.zip")
        assert ok is False and "不支持的文件类型" in msg

    def test_allowed_extension(self):
        ok, msg = us.validate_extension("report.xlsx")
        assert ok is True and msg == ""

    def test_uppercase_extension_normalized(self):
        ok, _ = us.validate_extension("PHOTO.PNG")
        assert ok is True

    def test_custom_allowed_set(self):
        ok, _ = us.validate_extension("data.custom", allowed_extensions={".custom"})
        assert ok is True


class TestValidateMimeType:
    def test_empty_mime(self):
        ok, msg = us.validate_mime_type("")
        assert ok is False and "无法检测文件类型" in msg

    def test_not_allowed(self):
        ok, msg = us.validate_mime_type("application/x-msdownload")
        assert ok is False and "不允许的文件类型" in msg

    def test_allowed(self):
        ok, msg = us.validate_mime_type("image/png")
        assert ok is True and msg == ""

    def test_custom_allowed(self):
        ok, _ = us.validate_mime_type("custom/type", allowed_mimes={"custom/type"})
        assert ok is True


class TestValidateFileSize:
    def test_zero_size(self):
        ok, msg = us.validate_file_size(0)
        assert ok is False and "文件大小为0" in msg

    def test_negative_size(self):
        ok, _ = us.validate_file_size(-5)
        assert ok is False

    def test_too_large(self):
        ok, msg = us.validate_file_size(60 * 1024 * 1024, max_bytes=50 * 1024 * 1024)
        assert ok is False and "文件过大" in msg

    def test_within_limit(self):
        ok, msg = us.validate_file_size(1024)
        assert ok is True and msg == ""


class TestValidateContentSafety:
    def test_empty_content(self):
        ok, msg = us.validate_content_safety(b"")
        assert ok is False and "文件内容为空" in msg

    def test_mz_executable(self):
        ok, msg = us.validate_content_safety(b"MZ\x90\x00")
        assert ok is False and "可执行文件" in msg

    def test_shell_script_bin(self):
        ok, msg = us.validate_content_safety(b"#!/bin/bash\necho hi")
        assert ok is False and "脚本文件" in msg

    def test_shell_script_usr(self):
        ok, _ = us.validate_content_safety(b"#!/usr/local/bin/tool")
        assert ok is False

    def test_php_tag(self):
        ok, _ = us.validate_content_safety(b"<?php echo 1; ?>")
        assert ok is False

    def test_asp_tag(self):
        ok, _ = us.validate_content_safety(b"<% Response.Write(1) %>")
        assert ok is False

    def test_python_shebang(self):
        ok, _ = us.validate_content_safety(b"#!/usr/bin/env python\nprint(1)")
        assert ok is False

    def test_safe_content(self):
        ok, msg = us.validate_content_safety(b"plain,csv,content\n1,2,3")
        assert ok is True and msg == ""


class TestValidateExcelUpload:
    def test_none_file(self):
        assert us.validate_excel_upload(None) is False

    def test_no_file_attr(self):
        assert us.validate_excel_upload(SimpleNamespace()) is False

    def test_xls_magic(self):
        f = MagicMock()
        f.file.read.return_value = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
        assert us.validate_excel_upload(f) is True
        f.file.seek.assert_called_once_with(0)

    def test_xlsx_magic(self):
        f = MagicMock()
        f.file.read.return_value = b"PK\x03\x04rest"
        assert us.validate_excel_upload(f) is True

    def test_non_excel_header(self):
        f = MagicMock()
        f.file.read.return_value = b"plain text"
        assert us.validate_excel_upload(f) is False

    def test_read_raises_exception(self):
        f = MagicMock()
        f.file.read.side_effect = OSError("boom")
        assert us.validate_excel_upload(f) is False


class TestSanitizeFilename:
    def test_replaces_invalid_chars(self):
        assert us.sanitize_filename('a<b>c:d"e|f?g*h') == "a_b_c_d_e_f_g_h"

    def test_keeps_safe_chars(self):
        assert us.sanitize_filename("report_2026.final.xlsx") == "report_2026.final.xlsx"
