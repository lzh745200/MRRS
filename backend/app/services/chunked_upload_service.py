"""
分片上传服务

实现大文件分片上传功能，优化文件上传性能。

Task 11.3: 实施性能优化 - 优化文件上传（分片上传）
Requirements: 10.4 - 实现文件上传优化（分片上传）
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import timezone, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles

logger = logging.getLogger(__name__)


class ChunkUploadStatus(str, Enum):
    """分片上传状态"""

    PENDING = "pending"  # 等待上传
    UPLOADING = "uploading"  # 上传中
    COMPLETED = "completed"  # 上传完成
    MERGING = "merging"  # 合并中
    MERGED = "merged"  # 合并完成
    FAILED = "failed"  # 上传失败
    EXPIRED = "expired"  # 已过期


@dataclass
class ChunkInfo:
    """分片信息"""

    index: int  # 分片索引（从0开始）
    size: int  # 分片大小
    hash: Optional[str] = None  # 分片MD5哈希
    uploaded: bool = False  # 是否已上传
    uploaded_at: Optional[datetime] = None


@dataclass
class UploadSession:
    """上传会话"""

    session_id: str  # 会话ID
    file_name: str  # 原始文件名
    file_size: int  # 文件总大小
    chunk_size: int  # 分片大小
    total_chunks: int  # 总分片数
    file_hash: Optional[str]  # 文件MD5哈希（可选，用于校验）
    user_id: int  # 上传用户ID
    status: ChunkUploadStatus  # 上传状态
    chunks: Dict[int, ChunkInfo] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=24))
    merged_file_path: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def uploaded_chunks(self) -> int:
        """已上传分片数"""
        return sum(1 for c in self.chunks.values() if c.uploaded)

    @property
    def progress(self) -> float:
        """上传进度（0 - 100）"""
        if self.total_chunks == 0:
            return 0
        return round(self.uploaded_chunks / self.total_chunks * 100, 2)

    @property
    def is_complete(self) -> bool:
        """是否所有分片都已上传"""
        return self.uploaded_chunks == self.total_chunks

    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "chunk_size": self.chunk_size,
            "total_chunks": self.total_chunks,
            "uploaded_chunks": self.uploaded_chunks,
            "progress": self.progress,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "merged_file_path": self.merged_file_path,
        }


class ChunkedUploadConfig:
    """分片上传配置"""

    # 默认分片大小：5MB
    DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024

    # 最小分片大小：1MB
    MIN_CHUNK_SIZE = 1 * 1024 * 1024

    # 最大分片大小：20MB
    MAX_CHUNK_SIZE = 20 * 1024 * 1024

    # 最大文件大小：2GB
    MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024

    # 会话过期时间：24小时
    SESSION_EXPIRE_HOURS = 24

    # 内存会话数量上限（R4）：超限淘汰最早创建的会话，防异常客户端循环 init
    MAX_SESSIONS = 200


class ChunkedUploadService:
    """
    分片上传服务

    支持大文件分片上传，提供以下功能：
    - 创建上传会话
    - 上传单个分片
    - 查询上传进度
    - 合并分片
    - 清理过期会话

    Requirements: 10.4
    """

    def __init__(
        self,
        temp_dir: str = None,
        final_dir: str = None,
        default_chunk_size: int = ChunkedUploadConfig.DEFAULT_CHUNK_SIZE,
    ):
        """
        初始化分片上传服务

        Args:
            temp_dir: 临时文件目录
            final_dir: 最终文件目录
            default_chunk_size: 默认分片大小
        """
        if temp_dir is None:
            try:
                from app.utils.paths import get_uploads_path

                temp_dir = str(get_uploads_path("chunks"))
            except Exception:
                from app.utils.paths import get_uploads_path

                temp_dir = str(get_uploads_path("chunks"))
        if final_dir is None:
            try:
                from app.utils.paths import get_uploads_path

                final_dir = str(get_uploads_path("files"))
            except Exception:
                from app.utils.paths import get_uploads_path

                final_dir = str(get_uploads_path("files"))
        self.temp_dir = Path(temp_dir)
        self.final_dir = Path(final_dir)
        self.default_chunk_size = default_chunk_size

        # 内存中的会话存储（生产环境应使用Redis）
        self._sessions: Dict[str, UploadSession] = {}
        # R4：会话数量上限——异常客户端循环 init 会让 _sessions 无限增长；
        # 超限时淘汰最早创建的会话（连同其分片文件）
        self.max_sessions = ChunkedUploadConfig.MAX_SESSIONS

        # 确保目录存在
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.final_dir.mkdir(parents=True, exist_ok=True)

    def _generate_session_id(self) -> str:
        """生成会话ID"""
        return str(uuid.uuid4())

    def _enforce_session_limit(self) -> None:
        """会话数量上限保护（R4）：超限时淘汰最早创建的会话（含分片文件）。"""
        overflow = len(self._sessions) - self.max_sessions
        if overflow <= 0:
            return
        oldest_ids = sorted(self._sessions, key=lambda sid: self._sessions[sid].created_at)[
            :overflow
        ]
        for sid in oldest_ids:
            logger.warning("上传会话数超上限（%d），淘汰最早会话: %s", self.max_sessions, sid)
            self.delete_session(sid)

    def _get_chunk_path(self, session_id: str, chunk_index: int) -> Path:
        """获取分片文件路径"""
        session_dir = self.temp_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir / f"chunk_{chunk_index:06d}"

    def _get_final_path(self, session_id: str, file_name: str, user_id: int) -> Path:
        """获取最终文件路径"""
        user_dir = self.final_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        ext = Path(file_name).suffix
        unique_name = f"{session_id}{ext}"
        return user_dir / unique_name

    def _calculate_md5(self, data: bytes) -> str:
        """计算MD5哈希"""
        return hashlib.md5(data, usedforsecurity=False).hexdigest()

    # ==================== 会话管理 ====================

    def create_session(
        self,
        file_name: str,
        file_size: int,
        user_id: int,
        chunk_size: Optional[int] = None,
        file_hash: Optional[str] = None,
    ) -> UploadSession:
        """
        创建上传会话

        Args:
            file_name: 文件名
            file_size: 文件大小
            user_id: 用户ID
            chunk_size: 分片大小（可选）
            file_hash: 文件MD5哈希（可选，用于校验）

        Returns:
            UploadSession: 上传会话

        Raises:
            ValueError: 参数无效
        """
        # 验证文件大小
        if file_size <= 0:
            raise ValueError("File size must be positive")
        if file_size > ChunkedUploadConfig.MAX_FILE_SIZE:
            raise ValueError(
                "File size exceeds maximum limit of " f"{ChunkedUploadConfig.MAX_FILE_SIZE / 1024 / 1024 / 1024:.1f}GB"
            )

        # 确定分片大小
        chunk_size = chunk_size or self.default_chunk_size
        chunk_size = max(
            ChunkedUploadConfig.MIN_CHUNK_SIZE,
            min(chunk_size, ChunkedUploadConfig.MAX_CHUNK_SIZE),
        )

        # 计算分片数
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        # 创建会话
        session_id = self._generate_session_id()
        session = UploadSession(
            session_id=session_id,
            file_name=file_name,
            file_size=file_size,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            file_hash=file_hash,
            user_id=user_id,
            status=ChunkUploadStatus.PENDING,
        )

        # 初始化分片信息
        for i in range(total_chunks):
            # 计算每个分片的大小
            if i == total_chunks - 1:
                # 最后一个分片可能小于chunk_size
                size = file_size - i * chunk_size
            else:
                size = chunk_size

            session.chunks[i] = ChunkInfo(index=i, size=size)

        # 保存会话
        self._sessions[session_id] = session
        self._enforce_session_limit()

        logger.info(
            f"Created upload session: {session_id}, " f"file={file_name}, size={file_size}, chunks={total_chunks}"
        )

        return session

    def get_session(self, session_id: str) -> Optional[UploadSession]:
        """获取上传会话"""
        session = self._sessions.get(session_id)
        if session and session.is_expired:
            session.status = ChunkUploadStatus.EXPIRED
        return session

    def delete_session(self, session_id: str) -> bool:
        """删除上传会话"""
        if session_id not in self._sessions:
            return False

        # 清理临时文件
        session_dir = self.temp_dir / session_id
        if session_dir.exists():
            import shutil

            shutil.rmtree(session_dir, ignore_errors=True)

        del self._sessions[session_id]
        logger.info(f"Deleted upload session: {session_id}")
        return True

    # ==================== 分片上传 ====================

    async def upload_chunk(
        self,
        session_id: str,
        chunk_index: int,
        chunk_data: bytes,
        chunk_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        上传单个分片

        Args:
            session_id: 会话ID
            chunk_index: 分片索引
            chunk_data: 分片数据
            chunk_hash: 分片MD5哈希（可选，用于校验）

        Returns:
            Dict: 上传结果

        Raises:
            ValueError: 参数无效或会话不存在
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if session.status == ChunkUploadStatus.EXPIRED:
            raise ValueError("Session has expired")

        if session.status in [ChunkUploadStatus.MERGED, ChunkUploadStatus.MERGING]:
            raise ValueError("Session is already merged or merging")

        if chunk_index < 0 or chunk_index >= session.total_chunks:
            raise ValueError(f"Invalid chunk index: {chunk_index}")

        chunk_info = session.chunks.get(chunk_index)
        if not chunk_info:
            raise ValueError(f"Chunk info not found: {chunk_index}")

        # 验证分片大小
        if len(chunk_data) != chunk_info.size:
            raise ValueError(f"Chunk size mismatch: expected {chunk_info.size}, got {len(chunk_data)}")

        # 验证分片哈希（如果提供）
        if chunk_hash:
            actual_hash = self._calculate_md5(chunk_data)
            if actual_hash != chunk_hash:
                raise ValueError("Chunk hash mismatch")

        # 保存分片
        chunk_path = self._get_chunk_path(session_id, chunk_index)
        async with aiofiles.open(chunk_path, "wb") as f:
            await f.write(chunk_data)

        # 更新分片信息
        chunk_info.uploaded = True
        chunk_info.uploaded_at = datetime.now(timezone.utc)
        chunk_info.hash = chunk_hash or self._calculate_md5(chunk_data)

        # 更新会话状态
        session.status = ChunkUploadStatus.UPLOADING
        session.updated_at = datetime.now(timezone.utc)

        logger.debug(f"Uploaded chunk {chunk_index}/{session.total_chunks} " f"for session {session_id}")

        return {
            "session_id": session_id,
            "chunk_index": chunk_index,
            "uploaded_chunks": session.uploaded_chunks,
            "total_chunks": session.total_chunks,
            "progress": session.progress,
            "is_complete": session.is_complete,
        }

    def get_missing_chunks(self, session_id: str) -> List[int]:
        """获取未上传的分片索引列表"""
        session = self.get_session(session_id)
        if not session:
            return []

        return [i for i, chunk in session.chunks.items() if not chunk.uploaded]

    # ==================== 分片合并 ====================

    async def merge_chunks(self, session_id: str) -> str:
        """
        合并所有分片

        Args:
            session_id: 会话ID

        Returns:
            str: 合并后的文件路径

        Raises:
            ValueError: 会话不存在或分片未完成
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if not session.is_complete:
            missing = self.get_missing_chunks(session_id)
            raise ValueError(f"Upload not complete, missing chunks: {missing}")

        if session.status == ChunkUploadStatus.MERGED:
            return session.merged_file_path

        # 更新状态
        session.status = ChunkUploadStatus.MERGING
        session.updated_at = datetime.now(timezone.utc)

        try:
            # 确定最终文件路径
            final_path = self._get_final_path(session_id, session.file_name, session.user_id)

            # 合并分片
            async with aiofiles.open(final_path, "wb") as outfile:
                for i in range(session.total_chunks):
                    chunk_path = self._get_chunk_path(session_id, i)
                    async with aiofiles.open(chunk_path, "rb") as infile:
                        chunk_data = await infile.read()
                        await outfile.write(chunk_data)

            # 验证文件大小
            actual_size = final_path.stat().st_size
            if actual_size != session.file_size:
                raise ValueError("Merged file size mismatch: " f"expected {session.file_size}, got {actual_size}")

            # 验证文件哈希（如果提供）
            if session.file_hash:
                async with aiofiles.open(final_path, "rb") as f:
                    file_data = await f.read()
                    actual_hash = self._calculate_md5(file_data)
                    if actual_hash != session.file_hash:
                        raise ValueError("File hash mismatch")

            # 更新会话状态
            session.status = ChunkUploadStatus.MERGED
            session.merged_file_path = str(final_path)
            session.updated_at = datetime.now(timezone.utc)

            # 清理临时分片
            session_dir = self.temp_dir / session_id
            if session_dir.exists():
                import shutil

                shutil.rmtree(session_dir, ignore_errors=True)

            logger.info(f"Merged chunks for session {session_id}, " f"file={final_path}")

            return str(final_path)

        except Exception as e:
            session.status = ChunkUploadStatus.FAILED
            session.error_message = str(e)
            session.updated_at = datetime.now(timezone.utc)
            logger.error(f"Failed to merge chunks for session {session_id}: {e}")
            raise

    # ==================== 清理 ====================

    def cleanup_expired_sessions(self) -> int:
        """清理过期会话"""
        expired_sessions = [sid for sid, session in self._sessions.items() if session.is_expired]

        for session_id in expired_sessions:
            self.delete_session(session_id)

        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

        return len(expired_sessions)

    def get_all_sessions(self, user_id: Optional[int] = None) -> List[UploadSession]:
        """获取所有会话（可按用户筛选）"""
        sessions = list(self._sessions.values())
        if user_id is not None:
            sessions = [s for s in sessions if s.user_id == user_id]
        return sessions

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取服务统计信息"""
        sessions = list(self._sessions.values())

        status_counts = {}
        for status in ChunkUploadStatus:
            status_counts[status.value] = sum(1 for s in sessions if s.status == status)

        return {
            "total_sessions": len(sessions),
            "status_counts": status_counts,
            "temp_dir": str(self.temp_dir),
            "final_dir": str(self.final_dir),
            "default_chunk_size": self.default_chunk_size,
        }


# 全局服务实例
_chunked_upload_service: Optional[ChunkedUploadService] = None


def get_chunked_upload_service(
    temp_dir: str = None,
    final_dir: str = None,
) -> ChunkedUploadService:
    """获取分片上传服务实例（单例）"""
    global _chunked_upload_service
    if _chunked_upload_service is None:
        _chunked_upload_service = ChunkedUploadService(
            temp_dir=temp_dir,
            final_dir=final_dir,
        )
    return _chunked_upload_service
