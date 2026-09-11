"""
通用文件上传 API
提供无业务绑定的文件上传端点，返回可直接访问的 /uploads 静态 URL。

上传校验/落盘逻辑已统一收口到 `app.utils.upload_helper.save_upload_file`
（分块流式 + 滚动大小校验 + 图片 magic 嗅探 + 路径安全），本模块仅保留
`/files/upload` 特有的契约：category 查询参数/表单两态兼容、413 状态码、
图片魔数嗅探、返回体字段与 success_response 包装。
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.core.security import get_current_user
from app.core.response import success_response
from app.utils.upload_helper import save_upload_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["文件上传"])

# 分块落盘粒度（8MB，与 backup upload-restore 约定一致）
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


def _flatten_allowed_exts() -> set:
    """展开分组白名单为扁平集合。"""
    allowed: set = set()
    for _exts in _ALLOWED_EXTS.values():
        allowed |= _exts
    return allowed


def _files_name_generator(_orig_name: str, ext: str) -> str:
    """`/files/upload` 唯一文件名：``{uuid16}.{ext}``（保留既有命名形态）。"""
    return f"{uuid.uuid4().hex[:16]}{('.' + ext) if ext else ''}"


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

    # 存储目录：uploads/generic[/category]（category 逐段白名单化，禁止路径遍历）
    sub_dir = "generic"
    if category:
        clean_category = category.strip().strip("/").replace("\\", "/")
        if (
            clean_category
            and ".." not in clean_category.split("/")
            and all(c.isalnum() or c in "-_/" for c in clean_category)
        ):
            sub_dir = "/".join(["generic", *clean_category.split("/")])

    file_info = await save_upload_file(
        file,
        sub_dir,
        allowed_extensions=_flatten_allowed_exts(),
        size_status_code=413,
        enforce_image_magic=True,
        chunk_size=_UPLOAD_CHUNK_SIZE,
        name_generator=_files_name_generator,
    )

    logger.info(
        "文件上传成功: user=%s, file=%s, url=%s, size=%d",
        getattr(current_user, "username", "unknown"),
        file_info["file_name"],
        file_info["url"],
        file_info["file_size"],
    )

    return success_response(
        data={
            "url": file_info["url"],
            "file_name": file_info["file_name"],
            "file_size": file_info["file_size"],
            "file_type": file_info["file_type"],
        },
        message="上传成功",
    )
