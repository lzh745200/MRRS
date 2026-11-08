"""政策附件孤儿回收端点：路径/引用边界。"""

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.files import delete_orphan_upload
from app.core.config import settings


class _DB:
    """模拟 ``db.query(Policy.attachment_urls).all()`` 返回的 1 元组列表。"""

    def __init__(self, urls=None):
        self._urls = urls or []

    def query(self, _model):
        return self

    def all(self):
        return [(url,) for url in self._urls]


def _user():
    return SimpleNamespace(id=1, username="tester")


def test_delete_unreferenced_policy_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    target_dir = tmp_path / "generic" / "policies"
    target_dir.mkdir(parents=True)
    name = "0123456789abcdef.pdf"
    target = target_dir / name
    target.write_bytes(b"pdf")

    result = delete_orphan_upload(
        url=f"/uploads/generic/policies/{name}", db=_DB(), current_user=_user()
    )
    assert result["success"] is True
    assert not target.exists()


def test_refuses_referenced_policy_file(tmp_path):
    raw_urls = json.dumps(["/uploads/generic/policies/0123456789abcdef.pdf"])
    with pytest.raises(HTTPException) as exc:
        delete_orphan_upload(
            url="/uploads/generic/policies/0123456789abcdef.pdf",
            db=_DB([raw_urls]),
            current_user=_user(),
        )
    assert exc.value.status_code == 409


@pytest.mark.parametrize(
    "url",
    [
        "/uploads/other/file.pdf",
        "/uploads/generic/policies/../secret.pdf",
        "/uploads/generic/policies/not-a-uuid.pdf",
    ],
)
def test_rejects_unsafe_paths(url):
    with pytest.raises(HTTPException) as exc:
        delete_orphan_upload(url=url, db=_DB(), current_user=_user())
    assert exc.value.status_code == 400


def test_missing_file_returns_404(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    with pytest.raises(HTTPException) as exc:
        delete_orphan_upload(
            url="/uploads/generic/policies/0123456789abcdef.pdf",
            db=_DB(),
            current_user=_user(),
        )
    assert exc.value.status_code == 404


def test_invalid_policy_json_is_tolerated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    target_dir = tmp_path / "generic" / "policies"
    target_dir.mkdir(parents=True)
    name = "0123456789abcdef.pdf"
    (target_dir / name).write_bytes(b"pdf")
    result = delete_orphan_upload(
        url=f"/uploads/generic/policies/{name}",
        db=_DB(["{not-json"]),
        current_user=_user(),
    )
    assert result["success"] is True
