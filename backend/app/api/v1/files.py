"""
通用文件上传 API
提供无业务绑定的文件上传端点，返回可直接访问的 /uploads 静态 URL。
"""

import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.core.config import settings
from app.core.security import get_current_user
from app.core.response import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["文件上传"])

# 分块落盘粒度（8MB，与备份 upload-restore 约定一致）
_UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024

# 允许的文件扩展名（按类别分组）
# 注意: svg 不在白名单（可含脚本导致存储型 XSS）
_ALLOWED_EXTS = {
    "image": {"jpg", "jpeg", "png", "gif", "bmp", "webp", "ico"},
    "document": {"pdf", "doc", "docx", "ppt", "pptx", "txt", "xls", "xlsx", "csv"},
    "archive": {"zip", "rar", "7z", "tar", "gz"},
    "audio": {"mp3", "wav", "ogg"},
    "video": {"mp4", "avi", "mov", "mkv", "webm"},
}


def _remove_quietly(path: str) -> None:
    """尽力删除拒绝路径上已写出的文件残片（零磁盘残留）。"""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:  # pragma: no cover - 删除失败不影响拒绝语义
        logger.warning("清理上传残片失败: %s", path, exc_info=True)


def _safe_extension(filename: str) -> str:
    """提取文件扩展名（小写、去点）"""
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


@router.post("/upload", summary="通用文件上传")
async def upload_file(
    file: UploadFile = File(...),
    category: Optional[str] = Query(None, description="存储子目录（查询参数）"),
    category_form: Optional[str] = Form(None, alias="category"),
    current_user=Depends(get_current_user),
):
    """上传任意业务模块的附件文件

    Args:
        file: 上传文件
        category: 存储子目录（可选，如 policies/villages/schools）。
            查询参数与 multipart 表单字段**都接受** —— 元素上传组件
            （el-upload 的 `data`/`:data`）天然走表单字段，只认查询参数会让
            调用方"传了却静默落到 generic/"（R26 实测；与 R14 经费附件
            `category` 走 FormData 而后端只认 Query 的坑同类）。
        category_form: 同上，multipart 表单字段形态（对外线名仍是 category）。

    Returns:
        url: 可通过 /uploads/... 静态访问的相对 URL
    """
    # 只接受真正的字符串：**直接调用**本函数（非 FastAPI 依赖解析，见
    # tests/unit/test_security_hardening.py 的 setup 失败用例）时，带默认值的
    # `category_form` 会是 `Form(...)` 哨兵对象本身，参与拼接会抛
    # `'Form' object has no attribute 'strip'`。
    _cat = category if isinstance(category, str) else ""
    if not _cat and isinstance(category_form, str):
        _cat = category_form
    category = _cat.strip() or None

    # 类型校验（可选扩展名白名单）——先校验再落盘，避免无谓写盘
    ext = _safe_extension(file.filename or "")
    if ext:
        allowed = set()
        for _exts in _ALLOWED_EXTS.values():
            allowed |= _exts
        if ext not in allowed:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: .{ext}")

    # 存储目录：uploads/generic[/category]
    base_upload = os.path.abspath(settings.UPLOAD_DIR)
    sub_dir = "generic"
    if category:
        clean_category = category.strip().strip("/").replace("\\", "/")
        # 安全校验：仅允许字母/数字/下划线/连字符/斜杠，禁止路径遍历
        if (
            clean_category
            and ".." not in clean_category.split("/")
            and all(c.isalnum() or c in "-_/" for c in clean_category)
        ):
            sub_dir = os.path.join(sub_dir, *clean_category.split("/"))
    upload_dir = os.path.join(base_upload, sub_dir)
    os.makedirs(upload_dir, exist_ok=True)

    # 唯一文件名（保留原始扩展名）
    unique_name = f"{uuid.uuid4().hex[:16]}{('.' + ext) if ext else ''}"
    file_path = os.path.join(upload_dir, unique_name)

    # 分块流式落盘 + 滚动大小校验（R26）：此前 `await file.read()` 一次性读全量，
    # 50MB 上限在**读完之后**才判 —— 超大文件会先把内存吃满再被拒（OOM）。
    # 对齐 backup upload-restore 的既有约定：8MB 分块 + 超限即删残片。
    written = 0
    head = b""
    try:
        with open(file_path, "wb") as fh:
            while True:
                chunk = await file.read(_UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                if not head:
                    head = chunk[:16]
                written += len(chunk)
                if written > settings.MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件大小超过限制({settings.MAX_FILE_SIZE // 1048576}MB)",
                    )
                fh.write(chunk)
    except HTTPException:
        _remove_quietly(file_path)
        raise

    # 内容嗅探: 图片扩展名必须匹配真实文件头(防改名绕过)
    _MAGIC = {
        "jpg": [b"\xff\xd8\xff"],
        "png": [b"\x89PNG\r\n\x1a\n"],
        "gif": [b"GIF87a", b"GIF89a"],
        "bmp": [b"BM"],
        "webp": [b"RIFF"],
    }
    if ext in _MAGIC and not any(head.startswith(magic) for magic in _MAGIC[ext]):
        _remove_quietly(file_path)
        raise HTTPException(status_code=400, detail=f"文件内容与扩展名 .{ext} 不匹配")

    # 相对 URL（静态挂载在 /uploads 下）
    rel_path = os.path.relpath(file_path, base_upload).replace("\\", "/")
    url = f"/uploads/{rel_path}"

    logger.info(
        "文件上传成功: user=%s, file=%s, url=%s, size=%d",
        getattr(current_user, 'username', 'unknown'),
        file.filename or unique_name,
        url,
        written,
    )

    return success_response(
        data={
            "url": url,
            "file_name": file.filename or unique_name,
            "file_size": written,
            "file_type": file.content_type or "application/octet-stream",
        },
        message="上传成功",
    )
