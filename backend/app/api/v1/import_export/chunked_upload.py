"""
分片上传API

实现大文件分片上传功能的API端点。
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User
from app.utils.upload_helper import read_upload_with_limit
from app.services.chunked_upload_service import (
    ChunkedUploadConfig,
    ChunkedUploadService,
    ChunkUploadStatus,
    get_chunked_upload_service,
)

router = APIRouter(prefix="/chunked-upload", tags=["分片上传"])


class InitUploadRequest(BaseModel):
    """初始化上传请求"""

    file_name: str = Field(..., description="文件名")
    file_size: int = Field(..., gt=0, description="文件大小(字节)")
    chunk_size: int = Field(default=5 * 1024 * 1024, description="分片大小(字节)")
    file_hash: Optional[str] = Field(None, description="文件MD5哈希")


class InitUploadResponse(BaseModel):
    """初始化上传响应"""

    session_id: str
    file_name: str
    file_size: int
    chunk_size: int
    total_chunks: int
    status: str


class UploadProgressResponse(BaseModel):
    """上传进度响应"""

    session_id: str
    file_name: str
    total_chunks: int
    uploaded_chunks: int
    progress: float
    status: str


class MergeResponse(BaseModel):
    """合并响应"""

    session_id: str
    file_path: str
    file_name: str
    status: str


@router.post("/init", response_model=InitUploadResponse)
async def init_upload(
    request: InitUploadRequest,
    current_user: User = Depends(get_current_user),
    upload_service: ChunkedUploadService = Depends(get_chunked_upload_service),
):
    """初始化分片上传会话"""
    session = upload_service.create_session(
        file_name=request.file_name,
        file_size=request.file_size,
        user_id=current_user.id,
        chunk_size=request.chunk_size,
        file_hash=request.file_hash,
    )
    return InitUploadResponse(
        session_id=session.session_id,
        file_name=session.file_name,
        file_size=session.file_size,
        chunk_size=session.chunk_size,
        total_chunks=session.total_chunks,
        status=session.status.value,
    )


@router.post("/chunk/{session_id}/{chunk_index}")
async def upload_chunk(
    session_id: str,
    chunk_index: int,
    file: UploadFile = File(...),
    chunk_hash: Optional[str] = Query(None, description="分片MD5哈希"),
    current_user: User = Depends(get_current_user),
    upload_service: ChunkedUploadService = Depends(get_chunked_upload_service),
):
    """上传单个分片"""
    # 用户隔离：验证 session 属于当前用户
    session = upload_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="上传会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此上传会话")

    # R2 第二层：原先 await file.read() 把任意大小的"分片"整包读进内存
    # （声明分片大小在服务层才校验，校验只能拒绝请求，挡不住内存峰值）。
    # 会话 chunk_size 已由 ChunkedUploadConfig 夹到 MAX_CHUNK_SIZE 以内。
    content = await read_upload_with_limit(
        file,
        ChunkedUploadConfig.MAX_CHUNK_SIZE,
        limit_label="单个分片",
    )
    success = await upload_service.upload_chunk(
        session_id=session_id,
        chunk_index=chunk_index,
        chunk_data=content,
        chunk_hash=chunk_hash,
    )
    if not success:
        raise HTTPException(status_code=400, detail="分片上传失败")
    return {"success": True, "chunk_index": chunk_index}


@router.get("/progress/{session_id}", response_model=UploadProgressResponse)
async def get_progress(
    session_id: str,
    current_user: User = Depends(get_current_user),
    upload_service: ChunkedUploadService = Depends(get_chunked_upload_service),
):
    """获取上传进度"""
    session = upload_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="上传会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看此上传会话")
    return UploadProgressResponse(
        session_id=session.session_id,
        file_name=session.file_name,
        total_chunks=session.total_chunks,
        uploaded_chunks=session.uploaded_chunks,
        progress=session.progress,
        status=session.status.value,
    )


@router.post("/merge/{session_id}", response_model=MergeResponse)
async def merge_chunks(
    session_id: str,
    current_user: User = Depends(get_current_user),
    upload_service: ChunkedUploadService = Depends(get_chunked_upload_service),
):
    """合并所有分片"""
    # 用户隔离验证
    session = upload_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="上传会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此上传会话")

    file_path = await upload_service.merge_chunks(session_id)
    if not file_path:
        raise HTTPException(status_code=400, detail="合并失败")
    session = upload_service.get_session(session_id)
    return MergeResponse(
        session_id=session_id,
        file_path=file_path,
        file_name=session.file_name if session else "",
        status=ChunkUploadStatus.MERGED.value,
    )


@router.delete("/{session_id}")
async def cancel_upload(
    session_id: str,
    current_user: User = Depends(get_current_user),
    upload_service: ChunkedUploadService = Depends(get_chunked_upload_service),
):
    """取消上传并清理"""
    # 用户隔离验证
    session = upload_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="上传会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权取消此上传会话")

    success = upload_service.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="上传会话不存在")
    return {"success": True, "message": "上传已取消"}
