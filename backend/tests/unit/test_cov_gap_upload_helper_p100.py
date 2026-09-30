"""app.utils.upload_helper 缺口补口（.coveragerc fail_under=100）。

缺失行：
- 133：_sanitize_file_name 净化后为空、或只剩 "." / ".." 时回退 fallback
  （客户端可控 filename，如 "..."/".."/纯空白 → 不得落盘成空名或父目录名）；
- 370：save_upload_file 的纵深防御守卫 —— 落盘路径若不在上传根目录内，
  一律 400 "非法的文件名"（即便 _sanitize_file_name 被绕过或回归也不放行）。
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

import app.utils.upload_helper as uh
from app.utils.upload_helper import _sanitize_file_name, save_upload_file


@pytest.fixture
def upload_settings(tmp_path):
    settings = MagicMock(name="settings")
    settings.MAX_FILE_SIZE = 1024
    settings.UPLOAD_DIR = str(tmp_path)
    settings.allowed_file_types_list = ["txt"]
    with patch.object(uh, "settings", settings):
        yield settings


def _upload(content: bytes, filename):
    return UploadFile(file=io.BytesIO(content), filename=filename)


class TestSanitizeFileNameFallback:
    def test_dot_only_and_blank_names_fall_back(self):
        """133 行：净化后为空/只剩点 → fallback（默认 "upload"）。"""
        assert _sanitize_file_name("...") == "upload"
        assert _sanitize_file_name("..") == "upload"
        assert _sanitize_file_name(".") == "upload"
        assert _sanitize_file_name("") == "upload"
        assert _sanitize_file_name("   ") == "upload"
        assert _sanitize_file_name(None) == "upload"

    def test_custom_fallback_is_used(self):
        assert _sanitize_file_name("...", fallback="unnamed") == "unnamed"
        assert _sanitize_file_name(None, fallback="unnamed") == "unnamed"

    def test_normal_name_survives_without_fallback(self):
        """对照组：正常名字（含前导点）仍按净化结果返回，不走 fallback。"""
        assert _sanitize_file_name("report.txt") == "report.txt"
        assert _sanitize_file_name(".hidden.txt") == "hidden.txt"
        assert _sanitize_file_name("dir\\report.txt") == "report.txt"


class TestPathEscapeGuard:
    async def test_escaping_name_rejected(self, upload_settings, tmp_path):
        """370 行：净化器被绕过（模拟回归）时，落盘守卫仍拒绝越界路径。"""
        file = _upload(b"data", "../../evil.txt")

        with patch.object(
            uh, "_sanitize_file_name", side_effect=lambda name, fallback="upload": name
        ):
            with pytest.raises(HTTPException) as exc:
                await save_upload_file(
                    file,
                    sub_dir="attachments",
                    allowed_extensions={"txt"},
                    name_generator=lambda orig, ext: "../../evil.txt",
                )

        assert exc.value.status_code == 400
        assert exc.value.detail == "非法的文件名"
        assert not (tmp_path.parent / "evil.txt").exists()   # 未写出越界文件
        saved = list((tmp_path / "attachments").glob("*"))
        assert saved == []                                   # 上传目录内也没有残片

    async def test_control_normal_name_is_saved(self, upload_settings, tmp_path):
        """对照组：正常文件名仍正常落盘（守门不误杀）。"""
        file = _upload(b"data", "report.txt")

        info = await save_upload_file(file, sub_dir="attachments", allowed_extensions={"txt"})

        assert info["file_size"] == 4
        assert info["file_path"].startswith(str(tmp_path))
        assert (tmp_path / "attachments").is_dir()
