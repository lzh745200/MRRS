# -*- coding: utf-8 -*-
"""data_sync._save_upload_file 的端点级上传上限（2026-10-29 审计）。"""
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException


def _fake_upload(payload: bytes, filename: str = "pkg.zip"):
    """构造一个按 chunk 吐出 payload 的 UploadFile 替身。"""
    from io import BytesIO

    class _Upload:
        def __init__(self):
            self.filename = filename
            self._buf = BytesIO(payload)

        async def read(self, size: int = -1):
            return self._buf.read(size)

    return _Upload()


@pytest.mark.asyncio
async def test_oversize_upload_raises_413_and_cleans_up(tmp_path, monkeypatch):
    """超过端点上限必须 413，且不留下半成品文件。"""
    from app.api.v1 import data_sync as ds

    monkeypatch.setattr(ds, "CHUNK_SIZE", 4)
    monkeypatch.setattr(ds, "MAX_UPLOAD_BYTES", 8)

    upload = _fake_upload(b"0123456789abcdef")  # 16 字节 > 8
    with pytest.raises(HTTPException) as ei:
        await ds._save_upload_file(upload, tmp_path, "pkg.zip")

    assert ei.value.status_code == 413
    assert "MB" in ei.value.detail
    # 半成品必须被清理
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_within_limit_succeeds(tmp_path, monkeypatch):
    """未超限时正常落盘，内容完整。"""
    from app.api.v1 import data_sync as ds

    monkeypatch.setattr(ds, "CHUNK_SIZE", 4)
    monkeypatch.setattr(ds, "MAX_UPLOAD_BYTES", 1024)

    payload = b"hello-world"
    upload = _fake_upload(payload)
    path = await ds._save_upload_file(upload, tmp_path, "pkg.zip")

    assert path.exists()
    assert path.read_bytes() == payload
    assert path.name.endswith("pkg.zip")