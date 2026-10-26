"""办公文档格式的单一事实源（WPS 兼容改造 P0，2026-10-26）。

## 为什么必须集中

改造前的事实分散且互相矛盾：

1. **附件白名单**只在 `api/v1/files.py` 的 `_ALLOWED_EXTS` 里，最远只到
   `doc/docx/xls/xlsx/ppt/pptx` —— WPS Office（政务现场主流套件）的原生
   `.et/.wps/.dps` 一律被拒；
2. **导入白名单**散落在多个端点各自的 `filename.endswith((".xlsx", ".xls"))`，
   但解析一律走 openpyxl —— `.xls`（OLE2 容器）能传进来却读不了；
3. **格式判定方式错了**：WPS 的 `.et` 既可能是 OOXML(zip)，也可能是旧版
   OLE2，**只看扩展名判不出来**，只能看文件头魔数。

本模块只放"事实与判定"（纯函数、无 IO、无第三方依赖），真正的读取实现见
`app/services/office_reader.py`；两者共同替代散落的扩展名判断。
"""

from __future__ import annotations

from typing import Optional

# ── 容器魔数（前 8 字节即可判定）──
ZIP_MAGIC = b"PK\x03\x04"
OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

CONTAINER_ZIP = "zip"
CONTAINER_OLE2 = "ole2"
CONTAINER_UNKNOWN = "unknown"

# ── 表格：能解析内容的扩展名（导入用）──
#   xlsx = OOXML(zip)；xls = Excel 97-2003(OLE2)；et = WPS 表格（两种容器都可能）
SPREADSHEET_EXTS = frozenset({"xlsx", "xls", "et"})

# ── WPS 原生格式 ──
#   et/ett = 表格（et 可能可解析，见 office_reader）；wps/wpt = 文字；dps/dpt = 演示
WPS_NATIVE_EXTS = frozenset({"et", "ett", "wps", "wpt", "dps", "dpt"})
# 只能存、不能解析的 WPS 原生格式（文字/演示/模板）
WPS_STORAGE_ONLY_EXTS = frozenset({"wps", "wpt", "dps", "dpt", "ett"})

# ── 附件（documents 组）白名单：标准格式 + WPS 原生格式 ──
DOCUMENT_UPLOAD_EXTS = frozenset(
    {
        "pdf",
        "doc",
        "docx",
        "wps",
        "wpt",
        "ppt",
        "pptx",
        "dps",
        "dpt",
        "xls",
        "xlsx",
        "et",
        "ett",
        "txt",
        "csv",
    }
)

# ── 导出格式白名单（WPS/Excel 均可打开的标准格式）──
EXPORT_FORMATS = frozenset({"xlsx", "csv", "docx", "pdf"})


def file_ext(filename: Optional[str]) -> str:
    """取小写扩展名（不带点）；无扩展名/空名返回空串。

    同时兼容 Windows 反斜杠路径与前端可能带来的完整路径。
    """
    if not filename:
        return ""
    name = str(filename).strip().replace("\\", "/").rsplit("/", 1)[-1]
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def sniff_container(content: bytes) -> str:
    """按文件头魔数判定容器：zip / ole2 / unknown（不看扩展名）。"""
    if not content:
        return CONTAINER_UNKNOWN
    if content.startswith(ZIP_MAGIC):
        return CONTAINER_ZIP
    if content.startswith(OLE2_MAGIC):
        return CONTAINER_OLE2
    return CONTAINER_UNKNOWN


def is_spreadsheet_upload(filename: Optional[str]) -> bool:
    """上传名是否属于"可解析表格"（.xlsx/.xls/.et，含 WPS 表格）。"""
    return file_ext(filename) in SPREADSHEET_EXTS


def spreadsheet_upload_hint() -> str:
    """导入端点统一错误文案（含 WPS 场景指引）。"""
    return (
        "不支持的文件格式：请上传 .xlsx / .xls / .et（WPS 表格）文件；"
        "如为 WPS 的 .wps/.dps，请先在 WPS 中「另存为」.docx / .pptx 再上传"
    )


def wps_save_as_message(filename: Optional[str] = None) -> str:
    """针对 WPS 原生格式（不能直接解析）的可读提示。"""
    ext = file_ext(filename)
    if ext:
        return (
            f"暂不支持直接解析 WPS 原生格式 .{ext}：请在 WPS 中「另存为」"
            ".xlsx（表格）/ .docx（文字）/ .pptx（演示）后重新上传"
        )
    return (
        "暂不支持直接解析 WPS 原生格式：请在 WPS 中「另存为」"
        ".xlsx / .docx / .pptx 后重新上传"
    )
