"""app.api.v1.subordinate_reports 覆盖补全 — 获取数据库文件大小失败的静默降级 (lines 97-98)."""
from unittest.mock import MagicMock

from app.api.v1.subordinate_reports import generate_status_report


class TestGenerateStatusReport:
    def test_db_size_failure_silently_ignored(self, monkeypatch):
        db = MagicMock(name="db")
        q = MagicMock(name="query")
        q.filter.return_value = q
        q.scalar.return_value = 4
        db.query.return_value = q

        user = MagicMock(name="user")
        user.username = "reporter"
        user.role = "admin"  # 生成上报包需管理员（深审：导出 PII 不能仅凭登录）
        user.is_superuser = False
        user.organization_id = None  # _get_instance_code 直接返回 None

        def _boom(path):
            raise RuntimeError("fs error")

        monkeypatch.setattr("os.path.exists", _boom)
        resp = generate_status_report(db=db, current_user=user)

        # 异常被吞掉 (lines 97-98)，报告仍正常生成
        assert resp.media_type == "application/zip"
