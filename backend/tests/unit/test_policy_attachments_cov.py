"""app.api.v1.policy 附件链路覆盖：_apply_attachments / create|update 附件映射 /
write_work_log 异常降级 / _attachment_urls_of 路径归一化 / 多附件与清空。
"""

import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import app.api.v1.policy as m
from app.models.policy import Policy


def _admin():
    return SimpleNamespace(id=1, role="super_admin", is_superuser=True, username="admin")


def _policy(**kw):
    p = MagicMock(spec=Policy)
    p.id = 1
    p.title = "测试政策"
    p.level = "national"
    p.status = "draft"
    p.category = "military"
    p.file_path = None
    p.file_type = None
    p.file_size = 0
    p.attachment_urls = None
    p.issue_date = None
    p.effective_date = None
    p.summary = "s"
    p.keywords = "k"
    p.created_by = 1
    p.organization_id = 1
    for k, v in kw.items():
        setattr(p, k, v)
    p.to_dict.return_value = {"id": 1, "title": "测试政策"}
    return p


def _make_db(first=None):
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.all.return_value = []
    q.first.return_value = first
    db = MagicMock()
    db.query.return_value = q
    return db


class TestApplyAttachments:
    def test_empty_urls_noop(self):
        p = _policy()
        m._apply_attachments(p, None)
        m._apply_attachments(p, [])
        m._apply_attachments(p, ["", "  "])
        assert p.file_path is None

    def test_uploads_url_maps_to_local_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
        sub = os.path.join(str(tmp_path), "policies", "a.pdf")
        os.makedirs(os.path.dirname(sub), exist_ok=True)
        with open(sub, "w") as f:
            f.write("pdf")
        p = _policy()
        m._apply_attachments(p, ["/uploads/policies/a.pdf"])
        assert p.file_path == sub
        assert p.file_type == "pdf"
        assert p.file_size == 3

    def test_absolute_path_kept_as_is(self, tmp_path):
        f = os.path.join(str(tmp_path), "b.docx")
        with open(f, "w") as fh:
            fh.write("x")
        p = _policy()
        m._apply_attachments(p, [f])
        assert p.file_path == f
        assert p.file_type == "docx"

    def test_missing_file_size_zero(self):
        p = _policy()
        m._apply_attachments(p, ["/uploads/nope/nope.pdf"])
        assert p.file_size == 0

    def test_getsize_oserror_size_zero(self):
        p = _policy()
        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", side_effect=OSError("denied")):
            m._apply_attachments(p, ["/uploads/x/y.pdf"])
        assert p.file_size == 0

    def test_multi_urls_stored_all_first_is_main(self, tmp_path, monkeypatch):
        """多附件：attachment_urls 落库全部，首个映射到主文件字段。"""
        monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
        a = os.path.join(str(tmp_path), "policies", "a.pdf")
        os.makedirs(os.path.dirname(a), exist_ok=True)
        with open(a, "w") as f:
            f.write("pdf")
        p = _policy()
        urls = ["/uploads/policies/a.pdf", "/uploads/policies/b.docx"]
        m._apply_attachments(p, urls)
        assert json.loads(p.attachment_urls) == urls
        assert p.file_path == a
        assert p.file_type == "pdf"
        assert m._attachment_urls_of(p) == urls

    def test_empty_urls_clears_attachments(self):
        """清空：None / [] / 全空白 输入均清空全部附件字段。"""
        p = _policy(file_path="/uploads/policies/a.pdf", file_type="pdf", file_size=3)
        p.attachment_urls = '["/uploads/policies/a.pdf"]'
        m._apply_attachments(p, [])
        assert p.attachment_urls is None
        assert p.file_path is None
        assert p.file_type is None
        assert p.file_size == 0
        assert m._attachment_urls_of(p) == []

        p2 = _policy(file_path="/uploads/policies/c.pdf", file_type="pdf", file_size=9)
        p2.attachment_urls = '["/uploads/policies/c.pdf"]'
        m._apply_attachments(p2, ["", "   "])
        assert p2.attachment_urls is None
        assert p2.file_path is None
        assert p2.file_size == 0

    def test_whitespace_filtered_in_multi_urls(self):
        """多附件中的空白/非字符串项被过滤，仅保留有效 URL。"""
        p = _policy()
        m._apply_attachments(p, ["/uploads/policies/a.pdf", "", "  ", None, "/uploads/policies/b.pdf"])
        assert json.loads(p.attachment_urls) == [
            "/uploads/policies/a.pdf",
            "/uploads/policies/b.pdf",
        ]
        assert m._attachment_urls_of(p) == [
            "/uploads/policies/a.pdf",
            "/uploads/policies/b.pdf",
        ]


class TestAttachmentUrlsOf:
    def test_no_file_path_returns_empty(self):
        assert m._attachment_urls_of(_policy(file_path=None)) == []

    def test_under_upload_dir_returns_uploads_url(self, monkeypatch, tmp_path):
        monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
        sub = os.path.join(str(tmp_path), "policies", "c.pdf")
        result = m._attachment_urls_of(_policy(file_path=sub))
        assert result == ["/uploads/policies/c.pdf"]

    def test_outside_upload_dir_returns_raw_path(self):
        result = m._attachment_urls_of(_policy(file_path="C:/elsewhere/d.pdf"))
        assert result == ["C:/elsewhere/d.pdf"]

    def test_attachment_urls_json_takes_priority(self, monkeypatch, tmp_path):
        monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
        p = _policy(file_path=os.path.join(str(tmp_path), "policies", "a.pdf"))
        p.attachment_urls = json.dumps(["/uploads/policies/a.pdf", "/uploads/policies/b.docx"])
        assert m._attachment_urls_of(p) == ["/uploads/policies/a.pdf", "/uploads/policies/b.docx"]

    def test_invalid_json_falls_back_to_file_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
        sub = os.path.join(str(tmp_path), "policies", "c.pdf")
        p = _policy(file_path=sub)
        p.attachment_urls = "{not-json}"
        assert m._attachment_urls_of(p) == ["/uploads/policies/c.pdf"]

    def test_non_list_json_falls_back_to_file_path(self):
        p = _policy(file_path="C:/elsewhere/d.pdf")
        p.attachment_urls = '{"a": 1}'
        assert m._attachment_urls_of(p) == ["C:/elsewhere/d.pdf"]


class TestCreatePolicyWithAttachments:
    async def test_create_with_attachment_urls(self, monkeypatch, tmp_path):
        monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
        sub = os.path.join(str(tmp_path), "policies", "a.pdf")
        os.makedirs(os.path.dirname(sub), exist_ok=True)
        with open(sub, "w") as f:
            f.write("data")

        db = _make_db()
        db.refresh.side_effect = lambda obj: setattr(obj, "id", 1)
        payload = {
            "title": "新政策",
            "level": "national",
            "status": "draft",
            "category": "military",
            "summary": "摘要",
            "attachment_urls": ["/uploads/policies/a.pdf"],
        }
        with patch("app.api.v1.policy.cache_manager.delete", AsyncMock()), \
             patch("app.services.policy_fts_service.sync_policy_to_fts") as sync, \
             patch("app.api.v1.policy.write_work_log") as wl:
            from app.api.v1.policy import create_policy, PolicyCreateRequest
            req = PolicyCreateRequest(**payload)
            result = await create_policy(req, current_user=_admin(), db=db)
        assert result["data"]["title"] == "新政策"  # 信封格式 data 字段
        sync.assert_called_once()
        wl.assert_called_once()

    async def test_create_work_log_exception_degrades(self):
        db = _make_db()
        db.refresh.side_effect = lambda obj: setattr(obj, "id", 2)
        payload = {
            "title": "新政策2",
            "level": "national",
            "status": "draft",
            "category": "military",
            "summary": "摘要",
        }
        with patch("app.api.v1.policy.cache_manager.delete", AsyncMock()), \
             patch("app.services.policy_fts_service.sync_policy_to_fts"), \
             patch("app.api.v1.policy.write_work_log", side_effect=RuntimeError("log fail")):
            from app.api.v1.policy import create_policy, PolicyCreateRequest
            req = PolicyCreateRequest(**payload)
            result = await create_policy(req, current_user=_admin(), db=db)
        assert result["data"]["title"] == "新政策2"


class TestUpdatePolicyWithAttachments:
    async def test_update_with_attachment_urls_and_worklog_failure(self, monkeypatch, tmp_path):
        monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
        sub = os.path.join(str(tmp_path), "policies", "a.pdf")
        os.makedirs(os.path.dirname(sub), exist_ok=True)
        with open(sub, "w") as f:
            f.write("data")

        policy = _policy()
        db = _make_db(first=policy)
        with patch("app.api.v1.policy.cache_manager.delete", AsyncMock()), \
             patch("app.services.policy_fts_service.sync_policy_to_fts"), \
             patch("app.api.v1.policy.write_work_log", side_effect=RuntimeError("boom")):
            from app.api.v1.policy import update_policy, PolicyUpdateRequest
            req = PolicyUpdateRequest(title="改标题", attachment_urls=["/uploads/policies/a.pdf"])
            result = await update_policy(1, req, current_user=_admin(), db=db)
        assert result["data"]["title"] == "改标题"  # 信封格式 data 字段
        assert policy.file_path == sub

    async def test_update_worklog_failure_degrades(self):
        policy = _policy()
        db = _make_db(first=policy)
        with patch("app.api.v1.policy.cache_manager.delete", AsyncMock()), \
             patch("app.services.policy_fts_service.sync_policy_to_fts"), \
             patch("app.api.v1.policy.write_work_log", side_effect=RuntimeError("boom")):
            from app.api.v1.policy import update_policy, PolicyUpdateRequest
            req = PolicyUpdateRequest(description="新描述")
            result = await update_policy(1, req, current_user=_admin(), db=db)
        assert result["data"]["title"] == "测试政策"  # 信封格式 data 字段

    async def test_update_multi_attachments_persist_all(self, monkeypatch, tmp_path):
        """多附件保存：policy.attachment_urls 含全部 2 条，前端输出含全部 2 条。"""
        monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
        sub = os.path.join(str(tmp_path), "policies", "a.pdf")
        os.makedirs(os.path.dirname(sub), exist_ok=True)
        with open(sub, "w") as f:
            f.write("data")
        policy = _policy()
        db = _make_db(first=policy)
        urls = ["/uploads/policies/a.pdf", "/uploads/policies/b.docx"]
        with patch("app.api.v1.policy.cache_manager.delete", AsyncMock()), \
             patch("app.services.policy_fts_service.sync_policy_to_fts"), \
             patch("app.api.v1.policy.write_work_log"):
            from app.api.v1.policy import update_policy, PolicyUpdateRequest
            req = PolicyUpdateRequest(title="改标题", attachment_urls=urls)
            result = await update_policy(1, req, current_user=_admin(), db=db)
        assert json.loads(policy.attachment_urls) == urls
        assert result["data"]["attachment_urls"] == urls

    async def test_update_empty_list_clears_attachments(self):
        """清空保存：请求携带 [] → file_path/file_type 为 None、file_size 为 0。"""
        policy = _policy(file_path="/uploads/policies/a.pdf", file_type="pdf", file_size=3)
        policy.attachment_urls = '["/uploads/policies/a.pdf"]'
        db = _make_db(first=policy)
        with patch("app.api.v1.policy.cache_manager.delete", AsyncMock()), \
             patch("app.services.policy_fts_service.sync_policy_to_fts"), \
             patch("app.api.v1.policy.write_work_log"):
            from app.api.v1.policy import update_policy, PolicyUpdateRequest
            req = PolicyUpdateRequest(title="改标题", attachment_urls=[])
            result = await update_policy(1, req, current_user=_admin(), db=db)
        assert policy.attachment_urls is None
        assert policy.file_path is None
        assert policy.file_type is None
        assert policy.file_size == 0
        assert result["data"]["attachment_urls"] == []


class TestDeletePolicyWorkLogDegrade:
    async def test_delete_worklog_exception_degrades(self):
        policy = _policy()
        db = _make_db(first=policy)
        with patch("app.api.v1.policy.cache_manager.delete", AsyncMock()), \
             patch("app.services.policy_fts_service.remove_policy_from_fts"), \
             patch("app.api.v1.policy.write_work_log", side_effect=ValueError("boom")):
            from app.api.v1.policy import delete_policy
            result = await delete_policy(1, current_user=_admin(), db=db)
        assert result["success"] is True
