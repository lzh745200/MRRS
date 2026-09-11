"""统一文件上传/下载工具 — 消除各模块重复的附件处理逻辑。

所有模块（经费、学校、帮扶村、政策、通用上传等）的附件上传下载统一使用
此模块，确保安全校验、路径处理、审计日志、内容去重的一致性。

三套历史实现已收口到本模块（P2-2）：
1. ``app/api/v1/files.py``（``POST /files/upload``）：分块流式 + 413 + 图片
   magic 嗅探 + 扩展名白名单；
2. 本模块 ``save_upload_file``：一次性读全量 + 400；
3. ``app/api/v1/policy.py``（``POST /policies/{id}/upload``）：一次性读全量。

统一后的核心能力（``save_upload_file``）：
- **分块流式落盘**（默认 8MB/块）：超大文件不会先把内存吃满再被拒；
- **滚动大小校验**：超限立即停写并删除残片（零磁盘残留）；
- **图片 magic 头嗅探**（可选，``enforce_image_magic``）：防改名绕过；
- **路径安全**：``sub_dir`` 归一化，禁止 ``..`` 路径穿越；
- **内容去重**（可选，传 ``db`` 时启用）：边写边算 SHA-256，命中
  ``FileBlob`` 则复用物理文件并累加引用计数。

使用方式：
    from app.utils.upload_helper import save_upload_file, get_attachment_response

    # 上传（无业务绑定，仅落盘）
    file_info = await save_upload_file(
        file=upload_file,
        sub_dir="funds/123",
        allowed_extensions=["pdf", "doc", "docx"],
    )
    # file_info = {"file_name", "file_path", "file_size", "file_type", "url", "sha256"}

    # 上传（启用内容去重，需传入 DB 会话）
    file_info = await save_upload_file(file, "funds/1", db=db)

    # 删除（引用计数感知；无 db 时维持原有直接删除语义）
    delete_attachment_file(file_info["file_path"], db=db)

    # 下载
    return get_attachment_response(file_path=file_info["file_path"], filename=file_info["file_name"])
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from typing import Callable, Iterable, Optional, Set

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.transaction import safe_commit
from app.models.file_blob import FileBlob

logger = logging.getLogger(__name__)

# ── 分块落盘粒度（8MB，与 backup upload-restore / files.py 约定一致）──
UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024

# ── 默认允许的文件扩展名 ──
DEFAULT_ALLOWED_EXTENSIONS: Set[str] = {
    "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx",
    "txt", "zip", "rar", "jpg", "jpeg", "png", "gif", "bmp",
}

# ── 图片 magic 头（防改名绕过；取自历史 files.py，逐字节等价）──
# 注意: svg 不在白名单（可含脚本导致存储型 XSS），故此处不含 svg 规则。
_IMAGE_MAGIC = {
    "jpg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "gif": [b"GIF87a", b"GIF89a"],
    "bmp": [b"BM"],
    "webp": [b"RIFF"],
}


def _safe_extension(filename: str) -> str:
    """提取文件扩展名（小写、去点）；无扩展名返回空串。"""
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _remove_quietly(path: str) -> None:
    """尽力删除拒绝路径上已写出的文件残片（零磁盘残留）。"""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:  # pragma: no cover - 删除失败不影响拒绝语义
        logger.warning("清理上传残片失败: %s", path, exc_info=True)


def _sanitize_sub_dir(sub_dir: str) -> str:
    """归一化上传子目录，禁止路径穿越（``..``）。

    逐段清洗：丢弃空段、``.``、``..``，仅保留字母/数字/下划线/连字符/点。
    """
    parts = []
    for seg in (sub_dir or "").replace("\\", "/").split("/"):
        seg = seg.strip()
        if not seg or seg in (".", ".."):
            continue
        cleaned = "".join(c for c in seg if c.isalnum() or c in "-_.")
        if cleaned and cleaned not in (".", ".."):
            parts.append(cleaned)
    return "/".join(parts)


def _normalize_path(path: str) -> str:
    """归一化为绝对路径（用于 FileBlob 路径比对）。"""
    return os.path.normpath(os.path.abspath(path))


def _register_or_reuse_blob(
    db: Session,
    sha256: str,
    file_path: str,
    size: int,
) -> Optional[FileBlob]:
    """登记或复用 ``FileBlob`` 记录，返回权威 blob。

    行为：
    - 命中且物理文件仍存在 → ``ref_count += 1``，返回既有记录（调用方复用其 path）；
    - 命中但物理文件缺失 → 以本次写入为准修复 ``path``/``size`` 并 ``ref_count += 1``；
    - 未命中 → 插入新记录（``ref_count=1``）；
    - 并发插入冲突（唯一约束） → 回滚后重查复用；
    - DB 异常 → 返回 ``None``（调用方保留本次写入的文件，不因去重失败而整体失败）。

    Returns:
        命中/新建的 ``FileBlob``；无法登记时返回 ``None``。
    """
    try:
        existing = db.query(FileBlob).filter(FileBlob.sha256 == sha256).first()
    except Exception:  # pragma: no cover - 防御性兜底（正常 SQLAlchemy 不抛）
        logger.warning("查询 FileBlob 失败，跳过去重: sha256=%s", sha256, exc_info=True)
        return None

    if isinstance(existing, FileBlob):
        # 命中：物理文件仍在 → 复用既有路径；缺失 → 以本次写入为准修复路径
        if not (existing.path and os.path.exists(existing.path)):
            existing.path = file_path
            existing.size = size
        existing.ref_count = (existing.ref_count or 0) + 1
        safe_commit(db)
        return existing

    blob = FileBlob(sha256=sha256, path=file_path, size=size, ref_count=1)
    db.add(blob)
    try:
        safe_commit(db)
        return blob
    except IntegrityError:
        # 并发插入同一内容：safe_commit 已 rollback，重查复用已存在记录
        winner = db.query(FileBlob).filter(FileBlob.sha256 == sha256).first()
        if isinstance(winner, FileBlob):
            return winner
        return None


async def save_upload_file(
    file: UploadFile,
    sub_dir: str,
    *,
    allowed_extensions: Optional[Iterable[str]] = None,
    max_size: Optional[int] = None,
    size_status_code: int = status.HTTP_400_BAD_REQUEST,
    type_status_code: int = status.HTTP_400_BAD_REQUEST,
    enforce_image_magic: bool = False,
    chunk_size: Optional[int] = None,
    name_generator: Optional[Callable[[str, str], str]] = None,
    db: Optional[Session] = None,
) -> dict:
    """统一的文件上传保存逻辑（分块流式 + 去重）。

    Args:
        file: FastAPI ``UploadFile`` 对象
        sub_dir: 上传子目录（如 ``"funds/123"``、``"generic/policies"``、``"policies"``）
        allowed_extensions: 允许的扩展名集合；``None`` 则使用
            ``settings.allowed_file_types_list + DEFAULT_ALLOWED_EXTENSIONS``
        max_size: 最大文件大小（字节）；``None`` 则使用 ``settings.MAX_FILE_SIZE``
        size_status_code: 大小超限时返回的状态码（默认 400；``/files/upload`` 传 413）
        type_status_code: 类型不允许 / magic 不匹配时的状态码（默认 400）
        enforce_image_magic: 是否对图片扩展名做真实文件头嗅探（默认关闭以兼容历史调用方）
        chunk_size: 分块粒度；``None`` 则使用本模块 ``UPLOAD_CHUNK_SIZE``
        name_generator: 自定义唯一文件名生成器 ``(原始文件名, 扩展名) -> 文件名``；
            ``None`` 则使用 ``"{uuid12}_{原始文件名}"``
        db: DB 会话。提供时启用内容去重（``FileBlob`` 登记 / 复用）；``None`` 时仅落盘

    Returns:
        dict: ``{"file_name", "file_path", "file_size", "file_type", "url", "sha256"}``

    Raises:
        HTTPException: 文件大小超限 / 类型不允许 / 内容与扩展名不匹配 / 写入失败
    """
    _max_size = max_size if max_size is not None else settings.MAX_FILE_SIZE
    _chunk = chunk_size if chunk_size else UPLOAD_CHUNK_SIZE

    orig_name = file.filename or "unknown"
    ext = _safe_extension(file.filename or "")

    # 1. 类型校验（先校验再落盘，避免无谓写盘）——无扩展名时跳过（向后兼容）
    if allowed_extensions is None:
        _allowed = list(settings.allowed_file_types_list) + list(DEFAULT_ALLOWED_EXTENSIONS)
    else:
        _allowed = list(allowed_extensions)
    _allowed_set = {e.lower().lstrip(".") for e in _allowed}
    if ext and ext not in _allowed_set:
        raise HTTPException(
            status_code=type_status_code,
            detail=f"不支持的文件类型: .{ext}",
        )

    # 2. 存储目录（归一化 + 绝对路径，防路径遍历）
    base_upload = os.path.abspath(settings.UPLOAD_DIR)
    safe_dir = _sanitize_sub_dir(sub_dir)
    upload_dir = os.path.join(base_upload, safe_dir) if safe_dir else base_upload
    os.makedirs(upload_dir, exist_ok=True)

    # 3. 唯一文件名（保留原始扩展名 / 允许调用方自定义命名）
    if name_generator is not None:
        unique_name = name_generator(orig_name, ext)
    else:
        unique_name = f"{uuid.uuid4().hex[:12]}_{orig_name}"
    file_path = os.path.join(upload_dir, unique_name)

    # 4. 分块流式落盘 + 滚动大小校验 + 边写边算 sha256
    written = 0
    head = b""
    digest = hashlib.sha256()
    try:
        with open(file_path, "wb") as fh:
            while True:
                chunk = await file.read(_chunk)
                if not chunk:
                    break
                if not head:
                    head = chunk[:16]
                written += len(chunk)
                if written > _max_size:
                    raise HTTPException(
                        status_code=size_status_code,
                        detail=f"文件大小超过限制({_max_size // 1048576}MB)",
                    )
                digest.update(chunk)
                fh.write(chunk)
    except HTTPException:
        _remove_quietly(file_path)
        raise
    except OSError as e:
        _remove_quietly(file_path)
        logger.error("文件写入失败: %s, 原因: %s", file_path, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件上传失败，请重试",
        )

    # 5. 内容嗅探: 图片扩展名必须匹配真实文件头(防改名绕过)
    if enforce_image_magic and ext in _IMAGE_MAGIC:
        if not any(head.startswith(magic) for magic in _IMAGE_MAGIC[ext]):
            _remove_quietly(file_path)
            raise HTTPException(
                status_code=type_status_code,
                detail=f"文件内容与扩展名 .{ext} 不匹配",
            )

    sha256 = digest.hexdigest()

    # 6. 内容去重（仅在提供 DB 会话时启用）
    if db is not None:
        reused = _register_or_reuse_blob(db, sha256, file_path, written)
        if reused is not None and _normalize_path(reused.path) != _normalize_path(file_path):
            # 命中已有内容：丢弃本次写入的副本，复用既有物理文件
            _remove_quietly(file_path)
            file_path = reused.path
            written = reused.size if reused.size is not None else written

    # 7. 相对 URL（静态挂载在 /uploads 下）
    rel_path = os.path.relpath(file_path, base_upload).replace(os.sep, "/")
    url = f"/uploads/{rel_path}"

    return {
        "file_name": orig_name,
        "file_path": file_path,
        "file_size": written,
        "file_type": file.content_type or "application/octet-stream",
        "url": url,
        "sha256": sha256,
    }


def get_attachment_response(
    file_path: str,
    filename: str,
    media_type: Optional[str] = None,
    *,
    inline: bool = False,
) -> FileResponse:
    """统一的文件下载响应。

    Args:
        file_path: 文件绝对路径
        filename: 下载时显示的文件名
        media_type: MIME 类型，None 则自动推断
        inline: True 则使用 inline 模式（浏览器内预览），False 则 attachment 下载

    Returns:
        FileResponse

    Raises:
        HTTPException: 文件不存在
    """
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="附件文件不存在",
        )

    import mimetypes
    if not media_type:
        media_type, _ = mimetypes.guess_type(file_path)
        if not media_type:
            media_type = "application/octet-stream"

    headers = {}
    if inline:
        headers["Content-Disposition"] = f"inline; filename*=UTF-8''{filename}"

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
        headers=headers if headers else None,
    )


def _lookup_blob(db: Session, file_path: str) -> Optional[FileBlob]:
    """按物理路径查 ``FileBlob``（精确匹配优先，归一化路径兜底）。"""
    blob = db.query(FileBlob).filter(FileBlob.path == file_path).first()
    if not isinstance(blob, FileBlob):
        # 兼容存储路径归一化差异（绝对/相对、分隔符）
        blob = db.query(FileBlob).filter(FileBlob.path == _normalize_path(file_path)).first()
    return blob if isinstance(blob, FileBlob) else None


def delete_attachment_file(file_path: str, db: Optional[Session] = None) -> bool:
    """安全删除磁盘文件（引用计数感知）。

    放在 DB commit 之后调用，即使文件删除失败也不影响数据库操作。

    引用计数语义（``db`` 提供且命中 ``FileBlob`` 时）：
    - ``ref_count > 0``（仍有引用）→ 仅递减并提交，物理文件保留，返回 ``False``；
    - ``ref_count == 0`` → 删除 ``FileBlob`` 行 + 物理文件，返回删除结果。

    未命中 ``FileBlob``（历史文件 / 未提供 ``db``）→ 维持原有「直接删物理文件」
    语义，行为与改造前完全一致。

    Args:
        file_path: 物理文件路径
        db: 可选的 DB 会话（提供时启用引用计数）

    Returns:
        True 如果物理文件被删除，False 如果文件不存在 / 保留 / 删除失败
    """
    if not file_path or not os.path.exists(file_path):
        return False

    if db is not None:
        try:
            blob = _lookup_blob(db, file_path)
        except Exception:  # pragma: no cover - 防御性兜底（DB 异常不阻塞删除）
            logger.warning("查询 FileBlob 失败，按直接删除处理: %s", file_path, exc_info=True)
            blob = None
        if blob is not None:
            blob.ref_count = (blob.ref_count or 0) - 1
            if blob.ref_count > 0:
                safe_commit(db)
                return False
            db.delete(blob)
            safe_commit(db)

    try:
        os.remove(file_path)
        return True
    except OSError as e:
        logger.warning("删除文件失败: %s, 原因: %s", file_path, e)
        return False
