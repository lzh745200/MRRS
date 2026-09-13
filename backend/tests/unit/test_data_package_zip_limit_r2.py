"""R2 第三层补漏：数据包（用户可控 zip）解析路径的解压后体积闸门。

背景：v1.12.7 批次的 R2 第三层只接了 control-packages / subordinate-reports /
policy-import，data_package_service 的 5 处 zip 打开点仍在裸 zf.read() ——
上传结构合法但解压后极大的包（压缩炸弹）单请求即可耗尽内存。
本文件锁定新增的 ensure_zip_within_limit + read_zip_member 行为。
"""

import json
import zipfile

import pytest


def _write_zip(path, members, compresslevel=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(path, "w", compresslevel) as zf:
        for name, payload in members.items():
            zf.writestr(name, payload)
    return str(path)


def _manifest(data_types=("schools",), record_counts=None):
    return json.dumps({
        "version": "1.0",
        "data_types": list(data_types),
        "record_counts": record_counts or {t: 1 for t in data_types},
    })


@pytest.fixture
def small_limit():
    """把解压后上限压到 1KB，用小样本触发（无需真造 200MB）。"""
    import app.utils.upload_helper as uh

    original = uh.ZIP_MAX_UNCOMPRESSED_BYTES
    uh.ZIP_MAX_UNCOMPRESSED_BYTES = 1024
    yield 1024
    uh.ZIP_MAX_UNCOMPRESSED_BYTES = original


class TestDataPackageZipLimit:
    async def test_validate_reports_bomb_as_readable_error(self, tmp_path, small_limit):
        from app.services.data_package_service import DataPackageService

        payload = json.dumps([{"name": "洪水" * 500}])  # > 1KB 解压后
        pkg = _write_zip(tmp_path / "bomb.zip", {
            "manifest.json": _manifest(),
            "data/schools.json": payload,
        })
        service = DataPackageService.__new__(DataPackageService)
        result = await DataPackageService.validate_package(service, pkg)
        assert result.is_valid is False
        assert any("压缩包解压后体积超过限制" in e.message for e in result.errors)

    async def test_validate_passes_when_within_limit(self, tmp_path):
        from app.services.data_package_service import DataPackageService

        pkg = _write_zip(tmp_path / "ok.zip", {
            "manifest.json": _manifest(),
            "data/schools.json": json.dumps([{"name": "正常学校"}]),
        })
        service = DataPackageService.__new__(DataPackageService)
        result = await DataPackageService.validate_package(service, pkg)
        assert result.is_valid is True

    async def test_preview_returns_empty_instead_of_oom(self, tmp_path, small_limit):
        from app.services.data_package_service import DataPackageService

        pkg = _write_zip(tmp_path / "bomb2.zip", {
            "manifest.json": _manifest(),
            "data/schools.json": json.dumps([{"name": "洪水" * 500}]),
        })
        service = DataPackageService.__new__(DataPackageService)
        preview = await DataPackageService.preview_package_data_from_file(service, pkg)
        assert preview == []

    async def test_member_level_limit_applies_to_single_member(self, tmp_path):
        """单成员预检：总量合规但单成员超限也要拦（read_zip_member）。"""
        from app.services.data_package_service import DataPackageService

        pkg = _write_zip(tmp_path / "member.zip", {
            "manifest.json": _manifest(),
            "data/schools.json": json.dumps([{"name": "x" * 200}]),
        })
        import app.utils.upload_helper as uh

        original = uh.ZIP_MAX_UNCOMPRESSED_BYTES
        uh.ZIP_MAX_UNCOMPRESSED_BYTES = 10  # 比 manifest.json 还小 → 命中成员级预检
        try:
            service = DataPackageService.__new__(DataPackageService)
            result = await DataPackageService.validate_package(service, pkg)
        finally:
            uh.ZIP_MAX_UNCOMPRESSED_BYTES = original
        assert result.is_valid is False
        assert any("压缩包解压后体积超过限制" in e.message for e in result.errors)
