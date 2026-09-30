"""app.api.v1.import_export.chunked_upload 覆盖率攻坚测试

覆盖 5 个端点的全部分支：
- POST /init：创建会话
- POST /chunk/{sid}/{idx}：404 无会话 / 403 他人会话 / 成功 / 服务返回失败→400
- GET /progress/{sid}：404 / 403 / 成功
- POST /merge/{sid}：404 / 403 / 成功 / 服务返回空→400
- DELETE /{sid}：404 / 403 / 成功 / delete_session 失败→404
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.v1.import_export.chunked_upload as cu
from app.core.security import get_current_user
from app.services.chunked_upload_service import ChunkUploadStatus, get_chunked_upload_service

BASE = "/api/v1/chunked-upload"


def _session(user_id=1, sid="sess-1"):
    return SimpleNamespace(
        session_id=sid,
        file_name="big.zip",
        file_size=10 * 1024 * 1024,
        chunk_size=5 * 1024 * 1024,
        total_chunks=2,
        uploaded_chunks=1,
        progress=50.0,
        status=ChunkUploadStatus.UPLOADING,
        user_id=user_id,
    )


@pytest.fixture
def client():
    from app.main import app

    original = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")
    svc = MagicMock()
    svc.upload_chunk = AsyncMock(return_value={"ok": True})
    svc.merge_chunks = AsyncMock(return_value="/files/1/sess-1.zip")
    app.dependency_overrides[get_chunked_upload_service] = lambda: svc
    yield TestClient(app, raise_server_exceptions=False), svc
    app.dependency_overrides = original


# ==================== /init ====================


class TestInitUpload:
    def test_init_success(self, client):
        c, svc = client
        svc.create_session.return_value = _session()
        resp = c.post(f"{BASE}/init", json={"file_name": "big.zip", "file_size": 10 * 1024 * 1024})
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess-1"
        assert data["total_chunks"] == 2
        assert data["status"] == "uploading"
        svc.create_session.assert_called_once()

    def test_init_value_error_returns_400(self, client):
        """深审 LIVE：服务层超限抛 ValueError，未捕获时冒泡为 500。"""
        c, svc = client
        svc.create_session.side_effect = ValueError("File size exceeds maximum limit of 2.0GB")
        resp = c.post(f"{BASE}/init", json={"file_name": "big.zip", "file_size": 3 * 1024 * 1024 * 1024})
        assert resp.status_code == 400
        assert "2.0GB" in resp.json()["detail"]


# ==================== /chunk ====================


class TestUploadChunk:
    def test_session_not_found_404(self, client):
        c, svc = client
        svc.get_session.return_value = None
        resp = c.post(f"{BASE}/chunk/nope/0", files={"file": ("c0", b"data")})
        assert resp.status_code == 404

    def test_other_user_session_403(self, client):
        c, svc = client
        svc.get_session.return_value = _session(user_id=999)
        resp = c.post(f"{BASE}/chunk/sess-1/0", files={"file": ("c0", b"data")})
        assert resp.status_code == 403

    def test_upload_success(self, client):
        c, svc = client
        svc.get_session.return_value = _session()
        resp = c.post(f"{BASE}/chunk/sess-1/0", files={"file": ("c0", b"data")})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        svc.upload_chunk.assert_awaited_once()

    def test_upload_failure_400(self, client):
        c, svc = client
        svc.get_session.return_value = _session()
        svc.upload_chunk = AsyncMock(return_value=None)
        resp = c.post(f"{BASE}/chunk/sess-1/0", files={"file": ("c0", b"data")})
        assert resp.status_code == 400

    def test_upload_value_error_400(self, client):
        """会话过期/序号越界/大小或哈希不匹配 → 400（原为 500）。"""
        c, svc = client
        svc.get_session.return_value = _session()
        svc.upload_chunk = AsyncMock(side_effect=ValueError("Session has expired"))
        resp = c.post(f"{BASE}/chunk/sess-1/0", files={"file": ("c0", b"data")})
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"]


# ==================== /progress ====================


class TestGetProgress:
    def test_not_found_404(self, client):
        c, svc = client
        svc.get_session.return_value = None
        assert c.get(f"{BASE}/progress/nope").status_code == 404

    def test_forbidden_403(self, client):
        c, svc = client
        svc.get_session.return_value = _session(user_id=999)
        assert c.get(f"{BASE}/progress/sess-1").status_code == 403

    def test_progress_success(self, client):
        c, svc = client
        svc.get_session.return_value = _session()
        resp = c.get(f"{BASE}/progress/sess-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["uploaded_chunks"] == 1
        assert data["progress"] == 50.0


# ==================== /merge ====================


class TestMergeChunks:
    def test_not_found_404(self, client):
        c, svc = client
        svc.get_session.return_value = None
        assert c.post(f"{BASE}/merge/nope").status_code == 404

    def test_forbidden_403(self, client):
        c, svc = client
        svc.get_session.return_value = _session(user_id=999)
        assert c.post(f"{BASE}/merge/sess-1").status_code == 403

    def test_merge_success(self, client):
        c, svc = client
        svc.get_session.return_value = _session()
        resp = c.post(f"{BASE}/merge/sess-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_path"] == "/files/1/sess-1.zip"
        assert data["status"] == "merged"

    def test_merge_failure_400(self, client):
        c, svc = client
        svc.get_session.return_value = _session()
        svc.merge_chunks = AsyncMock(return_value=None)
        assert c.post(f"{BASE}/merge/sess-1").status_code == 400

    def test_merge_value_error_400(self, client):
        """分片未传完 / 合并后大小或哈希不匹配 → 400（原为 500）。"""
        c, svc = client
        svc.get_session.return_value = _session()
        svc.merge_chunks = AsyncMock(side_effect=ValueError("Upload not complete, missing chunks: [1]"))
        resp = c.post(f"{BASE}/merge/sess-1")
        assert resp.status_code == 400
        assert "missing chunks" in resp.json()["detail"]


# ==================== DELETE ====================


class TestCancelUpload:
    def test_not_found_404(self, client):
        c, svc = client
        svc.get_session.return_value = None
        assert c.delete(f"{BASE}/nope").status_code == 404

    def test_forbidden_403(self, client):
        c, svc = client
        svc.get_session.return_value = _session(user_id=999)
        assert c.delete(f"{BASE}/sess-1").status_code == 403

    def test_cancel_success(self, client):
        c, svc = client
        svc.get_session.return_value = _session()
        svc.delete_session.return_value = True
        resp = c.delete(f"{BASE}/sess-1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_cancel_delete_failed_404(self, client):
        c, svc = client
        svc.get_session.return_value = _session()
        svc.delete_session.return_value = False
        assert c.delete(f"{BASE}/sess-1").status_code == 404
