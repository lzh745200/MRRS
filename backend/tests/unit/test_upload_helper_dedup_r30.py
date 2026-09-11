"""P2-2 统一上传收口 + 内容 hash 去重 + 引用计数删除 全覆盖测试。

覆盖：
- ``save_upload_file`` 的分块流式 / 大小状态码 / magic / 自定义命名 / sub_dir 归一化；
- ``_register_or_reuse_blob`` 的插入、复用、物理文件缺失修复、并发冲突分支；
- ``FileBlob`` 内容去重（命中复用 path、ref_count 累加）；
- ``delete_attachment_file(db=...)`` 的引用计数递减 / 归零删除 / 路径归一化兜底。
"""

import io
import os
from unittest.mock import patch

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.utils.upload_helper as uh
from app.models.base import Base
from app.models.file_blob import FileBlob
from app.utils.upload_helper import (
    _normalize_path,
    _register_or_reuse_blob,
    _sanitize_sub_dir,
    delete_attachment_file,
    save_upload_file,
)


def _upload(content: bytes, filename):
    return UploadFile(file=io.BytesIO(content), filename=filename)


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    from app.core.config import settings

    target = tmp_path / "uploads"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(target))
    target.mkdir(parents=True, exist_ok=True)
    return target


@pytest.fixture
def real_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[FileBlob.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


# ─────────────────────────────────────────────────────────────
# sub_dir 归一化 / 路径安全
# ─────────────────────────────────────────────────────────────


class TestSanitizeSubDir:
    def test_plain_nested_kept(self):
        assert _sanitize_sub_dir("funds/123") == "funds/123"

    def test_backslash_normalized(self):
        assert _sanitize_sub_dir("funds\\123") == "funds/123"

    def test_traversal_segments_dropped(self):
        # 覆盖 `continue` 分支：空段 / "." / ".." 均被丢弃
        assert _sanitize_sub_dir("../evil/./sub") == "evil/sub"
        assert _sanitize_sub_dir("") == ""
        assert _sanitize_sub_dir(None) == ""

    def test_fully_cleaned_segment_dropped(self):
        # 覆盖 `cleaned` 为空的 False 分支（非法字符段整段丢弃）
        assert _sanitize_sub_dir("!!!valid") == "valid"
        assert _sanitize_sub_dir("!!!") == ""


class TestSaveUploadFileUnified:
    @pytest.mark.asyncio
    async def test_returns_url_and_sha256(self, upload_dir):
        payload = b"hello unified"
        info = await save_upload_file(_upload(payload, "a.txt"), "generic/a")
        assert info["url"].startswith("/uploads/generic/a/")
        assert info["sha256"] == uh.hashlib.sha256(payload).hexdigest()
        assert info["file_size"] == len(payload)
        assert os.path.isfile(info["file_path"])

    @pytest.mark.asyncio
    async def test_traversal_sub_dir_neutralized(self, upload_dir):
        info = await save_upload_file(_upload(b"x", "a.txt"), "../evil")
        assert "evil" in info["url"]
        assert ".." not in info["url"]
        assert not (upload_dir.parent / "evil").exists()

    @pytest.mark.asyncio
    async def test_size_status_code_413(self, upload_dir):
        with pytest.raises(HTTPException) as ei:
            await save_upload_file(
                _upload(b"x" * 100, "a.txt"), "a", max_size=10, size_status_code=413
            )
        assert ei.value.status_code == 413
        assert [p for p in upload_dir.rglob("*") if p.is_file()] == []

    @pytest.mark.asyncio
    async def test_type_status_code_custom(self, upload_dir):
        with pytest.raises(HTTPException) as ei:
            await save_upload_file(
                _upload(b"x", "a.exe"), "a", allowed_extensions={"pdf"}, type_status_code=422
            )
        assert ei.value.status_code == 422

    @pytest.mark.asyncio
    async def test_magic_mismatch_and_match(self, upload_dir):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
        info = await save_upload_file(
            _upload(png, "ok.png"), "img", enforce_image_magic=True
        )
        assert os.path.isfile(info["file_path"])
        with pytest.raises(HTTPException) as ei:
            await save_upload_file(
                _upload(b"not-png", "bad.png"), "img", enforce_image_magic=True
            )
        assert ei.value.status_code == 400
        assert "不匹配" in ei.value.detail

    @pytest.mark.asyncio
    async def test_custom_chunk_size_and_name_generator(self, upload_dir):
        payload = b"0123456789" * 5

        def namer(_orig, ext):
            return f"fixed.{ext}" if ext else "fixed"

        info = await save_upload_file(
            _upload(payload, "x.txt"), "multi", chunk_size=4, name_generator=namer
        )
        assert os.path.basename(info["file_path"]) == "fixed.txt"
        assert open(info["file_path"], "rb").read() == payload


# ─────────────────────────────────────────────────────────────
# 内容去重（FileBlob）
# ─────────────────────────────────────────────────────────────


class TestContentDedup:
    @pytest.mark.asyncio
    async def test_first_upload_registers_blob(self, upload_dir, real_db):
        payload = b"dedup-content"
        info = await save_upload_file(_upload(payload, "a.txt"), "dedup", db=real_db)
        blob = real_db.query(FileBlob).filter(FileBlob.sha256 == info["sha256"]).first()
        assert blob is not None
        assert blob.ref_count == 1
        assert blob.path == info["file_path"]
        assert blob.created_at is not None  # 触发 _utcnow 默认值

    @pytest.mark.asyncio
    async def test_second_upload_reuses_physical_file(self, upload_dir, real_db):
        payload = b"same-bytes-reuse"
        first = await save_upload_file(_upload(payload, "a.txt"), "dedup", db=real_db)
        second = await save_upload_file(_upload(payload, "b.txt"), "dedup", db=real_db)

        # 复用同一物理文件（不新增副本）
        assert second["file_path"] == first["file_path"]
        assert second["url"] == first["url"]
        assert second["sha256"] == first["sha256"]
        on_disk = [p for p in upload_dir.rglob("*") if p.is_file()]
        assert len(on_disk) == 1, f"同内容应只有一份物理文件，实际 {on_disk}"
        blob = real_db.query(FileBlob).filter(FileBlob.sha256 == first["sha256"]).first()
        assert blob.ref_count == 2

    @pytest.mark.asyncio
    async def test_missing_physical_file_repaired(self, upload_dir, real_db):
        payload = b"repair-me"
        sha = uh.hashlib.sha256(payload).hexdigest()
        stale = FileBlob(
            sha256=sha, path=str(upload_dir / "gone" / "missing.txt"), size=0, ref_count=1
        )
        real_db.add(stale)
        real_db.commit()

        info = await save_upload_file(_upload(payload, "a.txt"), "repair", db=real_db)
        blob = real_db.query(FileBlob).filter(FileBlob.sha256 == sha).first()
        assert blob.ref_count == 2
        assert blob.path == info["file_path"]
        assert os.path.isfile(blob.path)


class _StubQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):  # noqa: D102
        return self

    def first(self):  # noqa: D102
        return self._result


class _StubDB:
    """模拟 Session：按顺序返回 first() 结果；可选让首次 commit 抛错。"""

    def __init__(self, results, commit_error=None):
        self._results = list(results)
        self._commit_error = commit_error
        self.committed = 0
        self.rolled_back = 0
        self.added = []

    def query(self, *args, **kwargs):  # noqa: D102
        return _StubQuery(self._results.pop(0) if self._results else None)

    def add(self, obj):  # noqa: D102
        self.added.append(obj)

    def commit(self):  # noqa: D102
        if self._commit_error is not None:
            err, self._commit_error = self._commit_error, None
            raise err
        self.committed += 1

    def rollback(self):  # noqa: D102
        self.rolled_back += 1


class TestRegisterOrReuseBlobConflict:
    def test_integrity_error_recovers_existing_winner(self):
        winner = FileBlob(sha256="a" * 64, path="/x/a.bin", size=1, ref_count=1)
        err = IntegrityError("INSERT", {}, Exception("dup"))
        db = _StubDB(results=[None, winner], commit_error=err)

        result = _register_or_reuse_blob(db, "a" * 64, "/x/fresh.bin", 5)
        assert result is winner
        assert db.rolled_back == 1

    def test_integrity_error_without_winner_returns_none(self):
        err = IntegrityError("INSERT", {}, Exception("dup"))
        db = _StubDB(results=[None, None], commit_error=err)
        assert _register_or_reuse_blob(db, "b" * 64, "/x/fresh.bin", 5) is None


# ─────────────────────────────────────────────────────────────
# 引用计数删除
# ─────────────────────────────────────────────────────────────


class TestRefcountDelete:
    def test_delete_with_remaining_refs_keeps_file(self, upload_dir, real_db):
        f = upload_dir / "shared.txt"
        f.write_bytes(b"shared")
        blob = FileBlob(sha256="c" * 64, path=str(f), size=6, ref_count=2)
        real_db.add(blob)
        real_db.commit()

        assert delete_attachment_file(str(f), db=real_db) is False
        assert f.exists()
        assert real_db.query(FileBlob).filter(FileBlob.sha256 == "c" * 64).first().ref_count == 1

    def test_delete_at_zero_refs_removes_file_and_row(self, upload_dir, real_db):
        f = upload_dir / "solo.txt"
        f.write_bytes(b"solo")
        real_db.add(FileBlob(sha256="d" * 64, path=str(f), size=4, ref_count=1))
        real_db.commit()

        assert delete_attachment_file(str(f), db=real_db) is True
        assert not f.exists()
        assert real_db.query(FileBlob).filter(FileBlob.sha256 == "d" * 64).first() is None

    def test_normalized_path_fallback(self, upload_dir, real_db):
        f = upload_dir / "norm.txt"
        f.write_bytes(b"norm")
        real_db.add(FileBlob(sha256="e" * 64, path=_normalize_path(str(f)), size=4, ref_count=1))
        real_db.commit()

        # 传入带冗余分隔符的路径 → 精确匹配失败 → 归一化兜底命中
        weird = os.path.join(str(upload_dir), ".", "norm.txt")
        assert delete_attachment_file(weird, db=real_db) is True
        assert not f.exists()

    def test_no_db_keeps_legacy_behavior(self, upload_dir):
        f = upload_dir / "legacy.txt"
        f.write_bytes(b"legacy")
        assert delete_attachment_file(str(f)) is True
        assert not f.exists()

    def test_non_blob_row_falls_back_to_legacy(self, upload_dir, real_db):
        # 表内无匹配 → 维持直接删除
        f = upload_dir / "unregistered.txt"
        f.write_bytes(b"x")
        assert delete_attachment_file(str(f), db=real_db) is True
        assert not f.exists()
