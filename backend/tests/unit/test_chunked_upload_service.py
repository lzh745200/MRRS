"""Tests for chunked upload service — 100% coverage."""

import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chunked_upload_service import (
    ChunkInfo,
    ChunkUploadStatus,
    ChunkedUploadConfig,
    ChunkedUploadService,
    UploadSession,
    get_chunked_upload_service,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_ORIGINAL_SINGLETON = "app.services.chunked_upload_service._chunked_upload_service"


def _make_session(**overrides) -> UploadSession:
    """Convenience — build an UploadSession with sensible defaults."""
    defaults = dict(
        session_id="sess-1",
        file_name="test.bin",
        file_size=1000,
        chunk_size=500,
        total_chunks=2,
        file_hash=None,
        user_id=1,
        status=ChunkUploadStatus.PENDING,
        chunks={0: ChunkInfo(index=0, size=500), 1: ChunkInfo(index=1, size=500)},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        merged_file_path=None,
        error_message=None,
    )
    defaults.update(overrides)
    return UploadSession(**defaults)


# ===================================================================
# ChunkUploadStatus
# ===================================================================


class TestChunkUploadStatus:
    def test_members(self):
        assert ChunkUploadStatus.PENDING.value == "pending"
        assert ChunkUploadStatus.UPLOADING.value == "uploading"
        assert ChunkUploadStatus.COMPLETED.value == "completed"
        assert ChunkUploadStatus.MERGING.value == "merging"
        assert ChunkUploadStatus.MERGED.value == "merged"
        assert ChunkUploadStatus.FAILED.value == "failed"
        assert ChunkUploadStatus.EXPIRED.value == "expired"


# ===================================================================
# ChunkInfo
# ===================================================================


class TestChunkInfo:
    def test_defaults(self):
        info = ChunkInfo(index=0, size=100)
        assert info.index == 0
        assert info.size == 100
        assert info.hash is None
        assert info.uploaded is False
        assert info.uploaded_at is None


# ===================================================================
# UploadSession
# ===================================================================


class TestUploadSession:
    def test_uploaded_chunks(self):
        s = _make_session(
            chunks={
                0: ChunkInfo(index=0, size=500, uploaded=True),
                1: ChunkInfo(index=1, size=500, uploaded=False),
            }
        )
        assert s.uploaded_chunks == 1

    def test_uploaded_chunks_all(self):
        s = _make_session(
            chunks={
                0: ChunkInfo(index=0, size=500, uploaded=True),
                1: ChunkInfo(index=1, size=500, uploaded=True),
            }
        )
        assert s.uploaded_chunks == 2

    def test_progress_zero_when_total_chunks_zero(self):
        s = _make_session(total_chunks=0, chunks={})
        assert s.progress == 0

    def test_progress_partial(self):
        s = _make_session(
            total_chunks=4,
            chunks={
                0: ChunkInfo(index=0, size=250, uploaded=True),
                1: ChunkInfo(index=1, size=250, uploaded=False),
                2: ChunkInfo(index=2, size=250, uploaded=True),
                3: ChunkInfo(index=3, size=250, uploaded=False),
            },
        )
        assert s.progress == 50.0

    def test_is_complete_true(self):
        s = _make_session(
            chunks={
                0: ChunkInfo(index=0, size=500, uploaded=True),
                1: ChunkInfo(index=1, size=500, uploaded=True),
            }
        )
        assert s.is_complete is True

    def test_is_complete_false(self):
        s = _make_session(
            chunks={
                0: ChunkInfo(index=0, size=500, uploaded=True),
                1: ChunkInfo(index=1, size=500, uploaded=False),
            }
        )
        assert s.is_complete is False

    def test_is_expired_true(self):
        s = _make_session(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
        assert s.is_expired is True

    def test_is_expired_false(self):
        s = _make_session(expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
        assert s.is_expired is False

    def test_to_dict(self):
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=24)
        s = _make_session(
            session_id="s-1",
            file_name="f.bin",
            file_size=1000,
            chunk_size=500,
            total_chunks=2,
            status=ChunkUploadStatus.UPLOADING,
            created_at=now,
            expires_at=expires,
            merged_file_path="/some/path",
        )
        d = s.to_dict()
        assert d["session_id"] == "s-1"
        assert d["file_name"] == "f.bin"
        assert d["file_size"] == 1000
        assert d["chunk_size"] == 500
        assert d["total_chunks"] == 2
        assert d["uploaded_chunks"] == 0
        assert d["progress"] == 0
        assert d["status"] == "uploading"
        assert d["created_at"] == now.isoformat()
        assert d["expires_at"] == expires.isoformat()
        assert d["merged_file_path"] == "/some/path"


# ===================================================================
# ChunkedUploadConfig
# ===================================================================


class TestChunkedUploadConfig:
    def test_constants(self):
        assert ChunkedUploadConfig.DEFAULT_CHUNK_SIZE == 5 * 1024 * 1024
        assert ChunkedUploadConfig.MIN_CHUNK_SIZE == 1 * 1024 * 1024
        assert ChunkedUploadConfig.MAX_CHUNK_SIZE == 20 * 1024 * 1024
        assert ChunkedUploadConfig.MAX_FILE_SIZE == 2 * 1024 * 1024 * 1024
        assert ChunkedUploadConfig.SESSION_EXPIRE_HOURS == 24


# ===================================================================
# ChunkedUploadService
# ===================================================================


class TestChunkedUploadService:
    """Every method, every branch, every exception handler."""

    # -- __init__ -----------------------------------------------------------

    def test_init_with_custom_paths(self, tmp_path):
        """Direct string paths → no import of get_uploads_path."""
        t = str(tmp_path / "c")
        f = str(tmp_path / "d")
        service = ChunkedUploadService(temp_dir=t, final_dir=f)
        assert str(service.temp_dir) == t
        assert str(service.final_dir) == f

    def test_init_with_defaults(self, tmp_path):
        """temp_dir=None, final_dir=None → import succeeds (happy path)."""
        with patch(
            "app.utils.paths.get_uploads_path",
            side_effect=[tmp_path / "chunks", tmp_path / "files"],
        ):
            service = ChunkedUploadService()
        assert service.temp_dir == tmp_path / "chunks"
        assert service.final_dir == tmp_path / "files"

    def test_init_with_defaults_import_try_fails(self, tmp_path):
        """First get_uploads_path call in try raises → except handles it."""
        mock = MagicMock(side_effect=[
            Exception("fail"),            # try temp_dir
            tmp_path / "chunks",           # except temp_dir
            Exception("fail"),            # try final_dir
            tmp_path / "files",            # except final_dir
        ])
        with patch("app.utils.paths.get_uploads_path", mock):
            service = ChunkedUploadService()
        assert service.temp_dir == tmp_path / "chunks"
        assert service.final_dir == tmp_path / "files"

    def test_init_creates_directories(self, tmp_path):
        t = tmp_path / "chunks"
        f = tmp_path / "files"
        service = ChunkedUploadService(temp_dir=str(t), final_dir=str(f))
        assert t.exists()
        assert f.exists()

    def test_init_default_chunk_size(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        assert service.default_chunk_size == ChunkedUploadConfig.DEFAULT_CHUNK_SIZE

    # -- _generate_session_id -----------------------------------------------

    def test_generate_session_id(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        sid = service._generate_session_id()
        # valid uuid4
        uuid.UUID(sid, version=4)

    # -- _get_chunk_path ----------------------------------------------------

    def test_get_chunk_path_creates_dir(self, tmp_path):
        service = ChunkedUploadService(temp_dir=str(tmp_path / "c"), final_dir=".")
        p = service._get_chunk_path("sess-1", 0)
        assert p.name == "chunk_000000"
        assert (tmp_path / "c" / "sess-1").exists()

    # -- _get_final_path ----------------------------------------------------

    def test_get_final_path(self, tmp_path):
        service = ChunkedUploadService(temp_dir=".", final_dir=str(tmp_path / "f"))
        p = service._get_final_path("sess-abc", "myfile.txt", 42)
        assert p.name == "sess-abc.txt"
        assert p.parent == tmp_path / "f" / "42"
        assert (tmp_path / "f" / "42").exists()

    def test_get_final_path_no_extension(self, tmp_path):
        service = ChunkedUploadService(temp_dir=".", final_dir=str(tmp_path / "f"))
        p = service._get_final_path("sess-xyz", "noext", 7)
        assert p.name == "sess-xyz"
        assert p.parent == tmp_path / "f" / "7"

    # -- _calculate_md5 -----------------------------------------------------

    def test_calculate_md5(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        data = b"hello"
        expected = hashlib.md5(data, usedforsecurity=False).hexdigest()
        assert service._calculate_md5(data) == expected

    # -- create_session -----------------------------------------------------

    def test_create_session_file_size_zero(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        with pytest.raises(ValueError, match="must be positive"):
            service.create_session("f.bin", 0, 1)

    def test_create_session_file_size_negative(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        with pytest.raises(ValueError, match="must be positive"):
            service.create_session("f.bin", -1, 1)

    def test_create_session_file_size_too_large(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        with pytest.raises(ValueError, match="exceeds maximum limit"):
            service.create_session("f.bin", ChunkedUploadConfig.MAX_FILE_SIZE + 1, 1)

    def test_create_session_default_chunk_size(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 10_000_000, 1)
        assert session.file_name == "f.bin"
        assert session.file_size == 10_000_000
        assert session.user_id == 1
        assert session.chunk_size == ChunkedUploadConfig.DEFAULT_CHUNK_SIZE
        assert session.total_chunks == 2  # ceil(10MB / 5MB)
        assert len(session.chunks) == 2
        assert session.status == ChunkUploadStatus.PENDING
        assert session.session_id is not None

    def test_create_session_custom_chunk_size(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 3_000_000, 1, chunk_size=2_000_000)
        assert session.chunk_size == 2_000_000
        assert session.total_chunks == 2  # ceil(3MB / 2MB)

    def test_create_session_chunk_size_clampled_to_min(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1, chunk_size=1)
        assert session.chunk_size == ChunkedUploadConfig.MIN_CHUNK_SIZE
        assert session.total_chunks == 1

    def test_create_session_chunk_size_clampled_to_max(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1, chunk_size=100_000_000)
        assert session.chunk_size == ChunkedUploadConfig.MAX_CHUNK_SIZE
        assert session.total_chunks == 1

    def test_create_session_last_chunk_smaller(self):
        """Last chunk's size should be the remainder."""
        service = ChunkedUploadService(
            temp_dir=".", final_dir=".",
            default_chunk_size=ChunkedUploadConfig.MIN_CHUNK_SIZE,
        )
        fs = ChunkedUploadConfig.MIN_CHUNK_SIZE + 1
        session = service.create_session("f.bin", fs, 1)
        assert session.total_chunks == 2
        assert session.chunks[0].size == ChunkedUploadConfig.MIN_CHUNK_SIZE
        assert session.chunks[1].size == 1

    def test_create_session_single_chunk(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        assert session.total_chunks == 1
        assert session.chunks[0].size == 100

    def test_create_session_with_file_hash(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1, file_hash="abc123")
        assert session.file_hash == "abc123"

    def test_create_session_stores_in_sessions_dict(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        assert service._sessions[session.session_id] is session

    # -- get_session --------------------------------------------------------

    def test_get_session_found(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        assert service.get_session(session.session_id) is session

    def test_get_session_not_found(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        assert service.get_session("no-such-id") is None

    def test_get_session_expired_sets_status(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        result = service.get_session(session.session_id)
        assert result.status == ChunkUploadStatus.EXPIRED

    # -- delete_session -----------------------------------------------------

    def test_delete_session_not_found(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        assert service.delete_session("no-such-id") is False

    def test_delete_session_dir_exists(self, tmp_path):
        t = tmp_path / "chunks"
        service = ChunkedUploadService(temp_dir=str(t), final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        # create the temp dir so it exists
        (t / session.session_id).mkdir(parents=True)
        assert service.delete_session(session.session_id) is True
        assert session.session_id not in service._sessions

    def test_delete_session_dir_missing(self, tmp_path):
        t = tmp_path / "chunks"
        service = ChunkedUploadService(temp_dir=str(t), final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        # dir was never created → cleanup should skip
        assert service.delete_session(session.session_id) is True
        assert session.session_id not in service._sessions

    # -- upload_chunk (async) -----------------------------------------------

    @pytest.mark.asyncio
    async def test_upload_chunk_session_not_found(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        with pytest.raises(ValueError, match="Session not found"):
            await service.upload_chunk("no-such", 0, b"data")

    @pytest.mark.asyncio
    async def test_upload_chunk_session_expired(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        # get_session marks it expired
        with pytest.raises(ValueError, match="Session has expired"):
            await service.upload_chunk(session.session_id, 0, b"data")

    @pytest.mark.asyncio
    async def test_upload_chunk_session_merged(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        session.status = ChunkUploadStatus.MERGED
        with pytest.raises(ValueError, match="already merged or merging"):
            await service.upload_chunk(session.session_id, 0, b"data")

    @pytest.mark.asyncio
    async def test_upload_chunk_session_merging(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        session.status = ChunkUploadStatus.MERGING
        with pytest.raises(ValueError, match="already merged or merging"):
            await service.upload_chunk(session.session_id, 0, b"data")

    @pytest.mark.asyncio
    async def test_upload_chunk_invalid_index_negative(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        with pytest.raises(ValueError, match="Invalid chunk index"):
            await service.upload_chunk(session.session_id, -1, b"x" * 100)

    @pytest.mark.asyncio
    async def test_upload_chunk_invalid_index_too_high(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        with pytest.raises(ValueError, match="Invalid chunk index"):
            await service.upload_chunk(session.session_id, 99, b"x" * 100)

    @pytest.mark.asyncio
    async def test_upload_chunk_chunk_info_not_found(self):
        """chunk_index is valid range but chunk missing from dict (shouldn't
        happen in normal flow, but the branch exists)."""
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        session.chunks.pop(0, None)
        with pytest.raises(ValueError, match="Chunk info not found"):
            await service.upload_chunk(session.session_id, 0, b"x" * 100)

    @pytest.mark.asyncio
    async def test_upload_chunk_size_mismatch(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        with pytest.raises(ValueError, match="Chunk size mismatch"):
            await service.upload_chunk(session.session_id, 0, b"x" * 50)

    @pytest.mark.asyncio
    async def test_upload_chunk_hash_mismatch(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        with pytest.raises(ValueError, match="Chunk hash mismatch"):
            await service.upload_chunk(session.session_id, 0, b"x" * 100, chunk_hash="bad")

    @pytest.mark.asyncio
    async def test_upload_chunk_success(self, tmp_path):
        service = ChunkedUploadService(temp_dir=str(tmp_path / "c"), final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        data = b"x" * 100
        with patch("aiofiles.open", new_callable=MagicMock) as mock_aio:
            mock_file = AsyncMock()
            cm = MagicMock()
            cm.__aenter__ = AsyncMock(return_value=mock_file)
            mock_aio.return_value = cm

            result = await service.upload_chunk(session.session_id, 0, data)

        assert result["session_id"] == session.session_id
        assert result["chunk_index"] == 0
        assert result["uploaded_chunks"] == 1
        assert result["total_chunks"] == 1
        assert result["progress"] == 100.0
        assert result["is_complete"] is True
        assert session.chunks[0].uploaded is True
        assert session.chunks[0].uploaded_at is not None
        assert session.chunks[0].hash == service._calculate_md5(data)
        assert session.status == ChunkUploadStatus.UPLOADING

    @pytest.mark.asyncio
    async def test_upload_chunk_with_hash_match(self, tmp_path):
        service = ChunkedUploadService(temp_dir=str(tmp_path / "c"), final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        data = b"x" * 100
        expected_hash = service._calculate_md5(data)
        with patch("aiofiles.open", new_callable=MagicMock) as mock_aio:
            mock_file = AsyncMock()
            cm = MagicMock()
            cm.__aenter__ = AsyncMock(return_value=mock_file)
            mock_aio.return_value = cm

            result = await service.upload_chunk(session.session_id, 0, data, chunk_hash=expected_hash)

        assert result["is_complete"] is True
        # hash from parameter is stored, not recalculated
        assert session.chunks[0].hash == expected_hash

    # -- get_missing_chunks -------------------------------------------------

    def test_get_missing_chunks_session_not_found(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        assert service.get_missing_chunks("no-such") == []

    def test_get_missing_chunks(self):
        service = ChunkedUploadService(
            temp_dir=".", final_dir=".",
            default_chunk_size=ChunkedUploadConfig.MIN_CHUNK_SIZE,
        )
        session = service.create_session("f.bin", ChunkedUploadConfig.MIN_CHUNK_SIZE * 4, 1)
        assert session.total_chunks == 4
        missing = service.get_missing_chunks(session.session_id)
        assert missing == [0, 1, 2, 3]
        # mark one uploaded
        session.chunks[1].uploaded = True
        missing = service.get_missing_chunks(session.session_id)
        assert missing == [0, 2, 3]

    # -- merge_chunks (async) -----------------------------------------------

    @pytest.mark.asyncio
    async def test_merge_chunks_session_not_found(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        with pytest.raises(ValueError, match="Session not found"):
            await service.merge_chunks("no-such")

    @pytest.mark.asyncio
    async def test_merge_chunks_not_complete(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 1000, 1, chunk_size=500)
        with pytest.raises(ValueError, match="Upload not complete"):
            await service.merge_chunks(session.session_id)

    @pytest.mark.asyncio
    async def test_merge_chunks_already_merged(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        session.chunks[0].uploaded = True
        session.status = ChunkUploadStatus.MERGED
        session.merged_file_path = "/already/merged.bin"
        result = await service.merge_chunks(session.session_id)
        assert result == "/already/merged.bin"

    @pytest.mark.asyncio
    async def test_merge_chunks_rejects_merging_state(self):
        """深审 #2：MERGING 状态重入必须拒绝，不得并发写同一 final_path。"""
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        session.chunks[0].uploaded = True
        session.status = ChunkUploadStatus.MERGING
        with pytest.raises(ValueError, match="already merging"):
            await service.merge_chunks(session.session_id)

    @pytest.mark.asyncio
    async def test_merge_chunks_rejects_when_lock_held(self):
        """锁被占用（并发调用）时同样拒绝。"""
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        session.chunks[0].uploaded = True
        lock = service._get_session_lock(session.session_id)
        lock.acquire()
        try:
            with pytest.raises(ValueError, match="already merging"):
                await service.merge_chunks(session.session_id)
        finally:
            lock.release()

    @pytest.mark.asyncio
    async def test_merge_chunks_returns_first_call_result_when_merged_while_waiting(self):
        """并发场景：第二个调用拿到锁时首个调用已完成合并 → 直接返回其路径（483）。

        进入时 status 仍是 UPLOADING（通过 474 的状态判断），但在等待/获取锁期间
        状态被首个调用置为 MERGED —— _acquire_merge_lock 的锁内二次检查返回
        (None, merged_file_path)，merge_chunks 必须返回该路径而非重复合并。
        """
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        session.chunks[0].uploaded = True
        session.merged_file_path = "/done/first.zip"

        # 用可控锁：acquire 成功后把状态翻成 MERGED，精确命中锁内二次检查
        class _MergeOnAcquireLock:
            def acquire(self_, blocking=True):
                session.status = ChunkUploadStatus.MERGED
                return True

            def release(self_):
                return None

        with patch.object(service, "_get_session_lock", lambda _sid: _MergeOnAcquireLock()):
            result = await service.merge_chunks(session.session_id)
        assert result == "/done/first.zip"

    @pytest.mark.asyncio
    async def test_merge_lock_released_after_failure(self, tmp_path):
        """失败路径必须释放锁，否则该会话永久无法重试。"""
        t = tmp_path / "c"
        f = tmp_path / "d"
        service = ChunkedUploadService(temp_dir=str(t), final_dir=str(f))
        session = service.create_session("out.txt", 4, 1, chunk_size=4)
        session.chunks[0].uploaded = True
        session.file_hash = "deadbeef"  # 触发 hash 不匹配失败
        # 分片文件必须真实存在，才能走到 hash 校验分支
        (t / session.session_id).mkdir(parents=True, exist_ok=True)
        (t / session.session_id / "chunk_000000").write_bytes(b"abcd")

        with pytest.raises(ValueError):
            await service.merge_chunks(session.session_id)

        assert service._get_session_lock(session.session_id).locked() is False

    def test_delete_session_releases_lock_entry(self):
        """删除会话时同步回收锁对象，避免无界增长。"""
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        service._get_session_lock(session.session_id)
        assert session.session_id in service._merge_locks
        service.delete_session(session.session_id)
        assert session.session_id not in service._merge_locks

    @pytest.mark.asyncio
    async def test_merge_chunks_success(self, tmp_path):
        """Happy path — all chunks merged, size verified, cleanup runs."""
        t = tmp_path / "c"
        f = tmp_path / "d"
        service = ChunkedUploadService(temp_dir=str(t), final_dir=str(f))
        session = service.create_session("out.txt", 12, 1, chunk_size=6)

        for i in range(session.total_chunks):
            await service.upload_chunk(session.session_id, i, b"x" * session.chunks[i].size)

        result = await service.merge_chunks(session.session_id)

        assert session.status == ChunkUploadStatus.MERGED
        assert result is not None
        assert session.merged_file_path == result
        merged = Path(result)
        assert merged.exists()
        assert merged.stat().st_size == 12

    @pytest.mark.asyncio
    async def test_merge_chunks_verify_file_hash(self, tmp_path):
        """file_hash provided and matches → success."""
        t = tmp_path / "c"
        f = tmp_path / "d"
        service = ChunkedUploadService(temp_dir=str(t), final_dir=str(f))
        data = b"test data 123"
        file_hash = service._calculate_md5(data)
        session = service.create_session("out.bin", len(data), 1, chunk_size=len(data), file_hash=file_hash)

        await service.upload_chunk(session.session_id, 0, data)
        result = await service.merge_chunks(session.session_id)

        assert session.status == ChunkUploadStatus.MERGED
        assert result is not None

    @pytest.mark.asyncio
    async def test_merge_chunks_file_hash_mismatch(self, tmp_path):
        """file_hash provided but doesn't match → ValueError + FAILED."""
        t = tmp_path / "c"
        f = tmp_path / "d"
        service = ChunkedUploadService(temp_dir=str(t), final_dir=str(f))
        session = service.create_session("out.bin", 12, 1, chunk_size=12, file_hash="wronghash")

        await service.upload_chunk(session.session_id, 0, b"x" * 12)

        with pytest.raises(ValueError, match="File hash mismatch"):
            await service.merge_chunks(session.session_id)

        assert session.status == ChunkUploadStatus.FAILED
        assert session.error_message is not None

    @pytest.mark.asyncio
    async def test_merge_chunks_size_mismatch(self, tmp_path):
        """Session file_size differs from actual → ValueError + FAILED."""
        t = tmp_path / "c"
        f = tmp_path / "d"
        service = ChunkedUploadService(temp_dir=str(t), final_dir=str(f))
        session = service.create_session("out.bin", 12, 1, chunk_size=12)

        await service.upload_chunk(session.session_id, 0, b"x" * 12)

        session.file_size = 999  # make it mismatch
        with pytest.raises(ValueError, match="Merged file size mismatch"):
            await service.merge_chunks(session.session_id)

        assert session.status == ChunkUploadStatus.FAILED

    @pytest.mark.asyncio
    async def test_merge_chunks_io_error_during_merge(self, tmp_path):
        """Exception during file operations → caught → FAILED + re-raise."""
        t = tmp_path / "c"
        f = tmp_path / "d"
        service = ChunkedUploadService(temp_dir=str(t), final_dir=str(f))
        session = service.create_session("out.bin", 12, 1, chunk_size=12)

        with patch("aiofiles.open", new_callable=MagicMock) as mock_aio:
            mf = AsyncMock()
            cm = MagicMock()
            cm.__aenter__ = AsyncMock(return_value=mf)
            mock_aio.return_value = cm
            await service.upload_chunk(session.session_id, 0, b"x" * 12)

        with patch("aiofiles.open", side_effect=IOError("Disk failure")):
            with pytest.raises(IOError, match="Disk failure"):
                await service.merge_chunks(session.session_id)

        assert session.status == ChunkUploadStatus.FAILED
        assert session.error_message == "Disk failure"

    @pytest.mark.asyncio
    async def test_merge_chunks_dir_cleanup_skipped_when_missing(self, tmp_path):
        """session_dir.exists() is False → skip shutil.rmtree."""
        t = tmp_path / "c"
        f = tmp_path / "d"
        service = ChunkedUploadService(temp_dir=str(t), final_dir=str(f))
        session = service.create_session("out.bin", 6, 1, chunk_size=6)

        with patch("aiofiles.open", new_callable=MagicMock) as mock_aio:
            mf = AsyncMock()
            cm = MagicMock()
            cm.__aenter__ = AsyncMock(return_value=mf)
            mock_aio.return_value = cm
            await service.upload_chunk(session.session_id, 0, b"x" * 6)

        # delete the session dir before merging
        import shutil
        sess_dir = t / session.session_id
        if sess_dir.exists():
            shutil.rmtree(sess_dir)

        with patch("aiofiles.open", new_callable=MagicMock) as mock_aio:
            write_cm = MagicMock()
            write_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
            read_cm = MagicMock()
            read_file = AsyncMock()
            read_file.read = AsyncMock(return_value=b"x" * 6)
            read_cm.__aenter__ = AsyncMock(return_value=read_file)
            mock_aio.side_effect = [write_cm, read_cm]

            with patch.object(Path, "stat", return_value=MagicMock(st_size=6)):
                result = await service.merge_chunks(session.session_id)

        assert session.status == ChunkUploadStatus.MERGED

    # -- cleanup_expired_sessions -------------------------------------------

    def test_cleanup_expired_sessions_no_expired(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        service.create_session("f.bin", 100, 1)
        assert service.cleanup_expired_sessions() == 0

    def test_cleanup_expired_sessions_with_expired(self, tmp_path):
        t = tmp_path / "c"
        service = ChunkedUploadService(temp_dir=str(t), final_dir=".")
        session = service.create_session("f.bin", 100, 1)
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert service.cleanup_expired_sessions() == 1
        assert session.session_id not in service._sessions

    def test_cleanup_expired_sessions_multiple(self, tmp_path):
        t = tmp_path / "c"
        service = ChunkedUploadService(temp_dir=str(t), final_dir=".")
        s1 = service.create_session("a.bin", 100, 1)
        s2 = service.create_session("b.bin", 100, 1)
        s3 = service.create_session("c.bin", 100, 1)
        s1.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        s3.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert service.cleanup_expired_sessions() == 2
        assert s1.session_id not in service._sessions
        assert s2.session_id in service._sessions
        assert s3.session_id not in service._sessions

    # -- get_all_sessions ---------------------------------------------------

    def test_get_all_sessions_no_filter(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        s1 = service.create_session("a.bin", 100, 1)
        s2 = service.create_session("b.bin", 100, 2)
        all_sessions = service.get_all_sessions()
        assert len(all_sessions) == 2
        assert s1 in all_sessions
        assert s2 in all_sessions

    def test_get_all_sessions_filtered(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        s1 = service.create_session("a.bin", 100, 1)
        s2 = service.create_session("b.bin", 100, 2)
        s3 = service.create_session("c.bin", 100, 1)
        user1 = service.get_all_sessions(user_id=1)
        assert len(user1) == 2
        assert s1 in user1
        assert s3 in user1
        assert s2 not in user1

    def test_get_all_sessions_empty(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        assert service.get_all_sessions() == []

    # -- get_stats ----------------------------------------------------------

    def test_get_stats_empty(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        stats = service.get_stats()
        assert stats["total_sessions"] == 0
        for status in ChunkUploadStatus:
            assert stats["status_counts"][status.value] == 0

    def test_get_stats_multiple_statuses(self):
        service = ChunkedUploadService(temp_dir=".", final_dir=".")
        s1 = service.create_session("a.bin", 100, 1)
        s2 = service.create_session("b.bin", 100, 2)
        s3 = service.create_session("c.bin", 100, 3)
        s1.status = ChunkUploadStatus.UPLOADING
        s2.status = ChunkUploadStatus.COMPLETED
        s3.status = ChunkUploadStatus.FAILED
        stats = service.get_stats()
        assert stats["total_sessions"] == 3
        assert stats["status_counts"]["pending"] == 0
        assert stats["status_counts"]["uploading"] == 1
        assert stats["status_counts"]["completed"] == 1
        assert stats["status_counts"]["failed"] == 1
        assert stats["temp_dir"] == "."
        assert stats["final_dir"] == "."

    # -- get_chunked_upload_service (singleton) -----------------------------

    def test_get_chunked_upload_service_singleton(self):
        # reset
        import app.services.chunked_upload_service as mod
        mod._chunked_upload_service = None

        s1 = get_chunked_upload_service(temp_dir=".", final_dir=".")
        s2 = get_chunked_upload_service(temp_dir=".", final_dir=".")
        assert s1 is s2

    def test_get_chunked_upload_service_creates_if_none(self):
        import app.services.chunked_upload_service as mod
        mod._chunked_upload_service = None

        s = get_chunked_upload_service(temp_dir=".", final_dir=".")
        assert s is not None
        assert s is mod._chunked_upload_service
