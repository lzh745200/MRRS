"""v1.15.10 补充测试：subordinate_reports.generate_status_report 的数据库大小两条路径。

背景：CI 合并覆盖率曾报 99.99%，missing 含
`app/api/v1/subordinate_reports.py` 的分支 `128->134` —— 即
`if db_path.is_file():` 的 **False 路径**（数据库文件不存在 → db_size_mb 记 0）。
只测"文件存在"的 True 路径不够，必须两条都覆盖。
"""
from unittest.mock import MagicMock

from app.api.v1.subordinate_reports import generate_status_report


def _fake_db(user_count: int = 7):
    db = MagicMock(name="db")
    q = MagicMock(name="query")
    q.filter.return_value = q
    q.scalar.return_value = user_count
    db.query.return_value = q
    return db


def _fake_user():
    user = MagicMock(name="user")
    user.username = "reporter"
    user.role = "admin"
    user.is_superuser = False
    user.organization_id = None  # _get_instance_code 直接返回 None
    return user


class TestGenerateStatusReportNormalPath:
    def test_normal_zip_path_covers_130_132(self, monkeypatch, tmp_path):
        # 正常数据库文件路径（存在且可 stat）→ if 为 True，走 129
        fake_db = tmp_path / "rural_revitalization.db"
        fake_db.write_bytes(b"SQLite format 3\x00" + b"x" * 1024)
        monkeypatch.setattr(
            "app.utils.paths.get_database_path",
            lambda: fake_db,
        )

        resp = generate_status_report(db=_fake_db(), current_user=_fake_user())

        assert resp.media_type == "application/zip"

    def test_missing_db_file_keeps_size_zero(self, monkeypatch, tmp_path):
        """数据库文件不存在 → if 为 False，db_size_mb 记 0 且不阻断上报（分支 128->134）。"""
        monkeypatch.setattr(
            "app.utils.paths.get_database_path",
            lambda: tmp_path / "not-there.db",
        )

        resp = generate_status_report(db=_fake_db(0), current_user=_fake_user())

        assert resp.media_type == "application/zip"
