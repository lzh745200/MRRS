"""v1.15.10 补充测试 1：subordinate_reports.generate_status_report 正常路径（覆盖 zip 写入分支 130-132 / branch 128->134）。

背景：v1.15.7/1.15.8 的 8 段 CI 合并覆盖率 99.99%，missing 包含
`app/api/v1/subordinate_reports.py` 行 130-132 与分支 128->134（status 上报包的 zip 写入路径），
本用例以正常 db_size 路径覆盖之。
"""
from unittest.mock import MagicMock

from app.api.v1.subordinate_reports import generate_status_report


class TestGenerateStatusReportNormalPath:
    def test_normal_zip_path_covers_130_132(self, monkeypatch, tmp_path):
        db = MagicMock(name="db")
        q = MagicMock(name="query")
        q.filter.return_value = q
        q.scalar.return_value = 7
        db.query.return_value = q

        user = MagicMock(name="user")
        user.username = "reporter"
        user.role = "admin"
        user.is_superuser = False
        user.organization_id = None  # _get_instance_code 直接返回 None

        # 正常数据库文件路径（存在且可 stat），走 zip 写入分支
        fake_db = tmp_path / "rural_revitalization.db"
        fake_db.write_bytes(b"SQLite format 3\x00" + b"x" * 1024)
        monkeypatch.setattr(
            "app.utils.paths.get_database_path",
            lambda: fake_db,
        )

        resp = generate_status_report(db=db, current_user=user)

        assert resp.media_type == "application/zip"
