"""Upload security validation.

Provides checks for uploaded files: extension allow-listing, MIME type
verification, content inspection for known malware patterns, and
filename sanitization.
"""

import logging
import re
from pathlib import Path
from typing import Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default allow lists
# ---------------------------------------------------------------------------

DEFAULT_ALLOWED_EXTENSIONS: Set[str] = {
    ".xlsx", ".xls", ".csv", ".pdf",
    ".jpg", ".jpeg", ".png", ".gi", ".webp", ".bmp",
    ".doc", ".docx", ".ppt", ".pptx",
    ".txt", ".json",
}

DEFAULT_ALLOWED_MIME_TYPES: Set[str] = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "application/pdf",
    "text/csv",
    "text/plain",
    "application/json",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/msword",
}

# Extensions that are always forbidden (executables, scripts, etc.)
FORBIDDEN_EXTENSIONS: Set[str] = {
    ".exe", ".dll", ".so", ".sh", ".bat", ".cmd", ".ps1",
    ".vbs", ".js", ".py", ".rb", ".pl",
    ".php", ".jsp", ".asp", ".aspx",
    ".html", ".htm", ".svg",
}

# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------


def validate_extension(
    filename: str,
    *,
    allowed_extensions: Optional[Set[str]] = None,
) -> Tuple[bool, str]:
    """Validate the file extension of an uploaded file.

    Args:
        filename: The original filename (e.g. ``"report.xlsx"``).
        allowed_extensions: Optional custom set of allowed extensions.
            Defaults to :data:`DEFAULT_ALLOWED_EXTENSIONS`.

    Returns:
        ``(True, "")`` if valid, otherwise ``(False, error_message)``.
    """
    if not filename:
        return False, "文件名不能为空"

    ext = Path(filename).suffix.lower()

    if ext in FORBIDDEN_EXTENSIONS:
        return False, f"不允许的文件类型: {ext}"

    allowed = allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS
    if ext not in allowed:
        return False, f"不支持的文件类型: {ext}（允许: {', '.join(sorted(allowed))}）"

    return True, ""


def validate_mime_type(
    mime_type: str,
    *,
    allowed_mimes: Optional[Set[str]] = None,
) -> Tuple[bool, str]:
    """Validate the MIME type of an uploaded file.

    Args:
        mime_type: Detected MIME type (e.g. ``"image/png"``).
        allowed_mimes: Optional custom set. Defaults to :data:`DEFAULT_ALLOWED_MIME_TYPES`.

    Returns:
        ``(True, "")`` if valid, otherwise ``(False, error_message)``.
    """
    if not mime_type:
        return False, "无法检测文件类型"

    allowed = allowed_mimes or DEFAULT_ALLOWED_MIME_TYPES
    if mime_type not in allowed:
        return False, f"不允许的文件类型: {mime_type}"

    return True, ""


def validate_file_size(file_size: int, max_bytes: int = 50 * 1024 * 1024) -> Tuple[bool, str]:
    """Validate the size of an uploaded file.

    Args:
        file_size: File size in bytes.
        max_bytes: Maximum allowed size in bytes (default: 50 MB).

    Returns:
        ``(True, "")`` if valid, otherwise ``(False, error_message)``.
    """
    if file_size <= 0:
        return False, "文件大小为0"
    if file_size > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        return False, f"文件过大 ({actual_mb:.1f} MB)，最大允许 {max_mb:.0f} MB"
    return True, ""


def validate_content_safety(
    content: bytes,
) -> Tuple[bool, str]:
    """Check file content for known risky patterns.

    Inspects for binary executable signatures and obvious
    shell script patterns at the start of the content.

    Args:
        content: The file content as bytes.

    Returns:
        ``(True, "")`` if safe, otherwise ``(False, error_message)``.
    """
    if not content:
        return False, "文件内容为空"

    # Check for known executable signatures
    if content[:2] == b"MZ":
        return False, "不允许上传可执行文件"

    # Check for script-like patterns at the start
    first_bytes = content[:100].decode("utf-8", errors="ignore").lower()
    script_patterns = [
        "#!/bin/", "#!/usr/", "<?php", "<%", "#!/usr/bin/env python",
    ]
    for pat in script_patterns:
        if pat in first_bytes:
            return False, "不允许上传脚本文件"

    return True, ""


# ---------------------------------------------------------------------------
# Full validation
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Filename sanitization
# ---------------------------------------------------------------------------

_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._\-一-鿿]")


def validate_excel_upload(file):
    """Validate uploaded file is a genuine Excel file by checking magic bytes."""
    EXCEL_MAGICS = {
        b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1": "xls",
        b"PK\x03\x04": "xlsx",
    }
    if not file or not hasattr(file, "file"):
        return False
    try:
        header = file.file.read(8)
        file.file.seek(0)
        return any(header.startswith(m) for m in EXCEL_MAGICS)
    except Exception as e:
        logger.debug("Excel 文件头检测失败: %s", e)
        return False


def sanitize_filename(name):
    import re
    return re.sub(r'[<>:/"|?*]', "_", name)
