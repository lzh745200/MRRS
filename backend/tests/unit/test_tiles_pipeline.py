"""瓦片真功能（安装包预置 + 离线导入）测试。

覆盖范围：
- ``offline_map_service``：目录扫描、MANIFEST 解析/校验、zip-slip/符号链接防护、
  数量/体积上限、SHA256、ZIP 与本机目录两条导入路径；
- ``api/v1/map.py``：``_resolve_tiles_dir`` 优先级、``GET /map/tile-info``、
  ``POST /map/tiles/import``（管理员校验 / 上传 / 本机目录 / 错误分支）；
- ``api/v1/offline_map.py``：``GET /offline-map/status`` 读真实目录、
  ``POST /offline-map/download`` 显式 501。
"""

import hashlib
import io
import json
import os
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

import app.api.v1.map as map_mod
import app.api.v1.offline_map as offline_mod
import app.services.offline_map_service as oms
from app.services.offline_map_service import (
    TilePackageError,
    import_tile_directory,
    import_tile_zip_bytes,
    normalize_manifest,
    scan_tiles_dir,
)

MAP_BASE = "/api/v1/map"
OFFLINE_BASE = "/api/v1/offline-map"

TILE_DATA = b"\x89PNG\r\n\x1a\n" + b"0" * 24 + b"IHDR"


# ==================== 测试辅助 ====================


def _write_tile(root: Path, z: int, x: int, y: int, data: bytes = TILE_DATA) -> Path:
    path = root / str(z) / str(x) / f"{y}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _manifest_bytes(
    tile_count=1,
    total_bytes=len(TILE_DATA),
    z_range=(5, 5),
    **extra,
) -> bytes:
    payload = {
        "schemaVersion": 1,
        "provider": "osm",
        "license": "OpenStreetMap contributors, ODbL",
        "coordinateSystem": "EPSG:3857 XYZ",
        "generatedAt": "2026-10-21T00:00:00Z",
        "zoom": {"min": z_range[0], "max": z_range[1]},
        "tileCount": tile_count,
        "totalBytes": total_bytes,
    }
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _zip_bytes(entries: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buffer.getvalue()


def _single_tile_zip(**manifest_extra) -> bytes:
    manifest = _manifest_bytes(**manifest_extra)
    return _zip_bytes({"MANIFEST.json": manifest, "5/1/2.png": TILE_DATA})


def _make_store(tmp_path: Path, z: int = 5, x: int = 1, y: int = 2) -> Path:
    store = tmp_path / "store"
    _write_tile(store, z, x, y)
    (store / "MANIFEST.json").write_bytes(_manifest_bytes())
    return store


@pytest.fixture
def store(tmp_path):
    return _make_store(tmp_path)


@pytest.fixture
def admin_client(client_with_mocked_auth):
    return client_with_mocked_auth


# ==================== scan_tiles_dir ====================


class TestScanTilesDir:
    def test_missing_dir_returns_empty(self, tmp_path):
        stats = scan_tiles_dir(tmp_path / "absent")
        assert stats == {
            "total_tiles": 0,
            "total_bytes": 0,
            "total_size_mb": 0.0,
            "zoom_levels": [],
        }

    def test_counts_tiles_and_ignores_noise(self, tmp_path):
        _write_tile(tmp_path, 5, 1, 2, b"a" * 10)
        _write_tile(tmp_path, 6, 1, 2, b"b" * 20)
        (tmp_path / "README.md").write_text("note", encoding="utf-8")
        (tmp_path / "not-a-zoom").mkdir()
        (tmp_path / "5" / "stray.txt").write_text("x", encoding="utf-8")
        stats = scan_tiles_dir(tmp_path)
        assert stats["total_tiles"] == 2
        assert stats["total_bytes"] == 30
        assert stats["total_size_mb"] == 0.0
        assert stats["zoom_levels"] == [5, 6]

    def test_stat_failure_skips_file(self, tmp_path):
        _write_tile(tmp_path, 5, 1, 2, b"ok")
        real_stat = Path.stat

        def flaky_stat(self, *args, **kwargs):
            if self.name == "2.png":
                raise OSError("vanished")
            return real_stat(self, *args, **kwargs)

        with patch.object(Path, "stat", flaky_stat):
            stats = scan_tiles_dir(tmp_path)
        assert stats["total_tiles"] == 0
        assert stats["zoom_levels"] == [5]


# ==================== normalize_manifest ====================


class TestNormalizeManifest:
    def test_non_dict_rejected(self):
        with pytest.raises(TilePackageError, match="JSON 对象"):
            normalize_manifest([1, 2])

    def test_zoom_dict_ok(self):
        result = normalize_manifest({"zoom": {"min": 5, "max": 12}})
        assert result["zRange"] == [5, 12]

    def test_zoom_dict_missing_keys_rejected(self):
        with pytest.raises(TilePackageError, match="zoom 字段非法"):
            normalize_manifest({"zoom": {"min": 5}})

    def test_zoom_dict_min_greater_than_max_rejected(self):
        with pytest.raises(TilePackageError, match="不能大于"):
            normalize_manifest({"zoom": {"min": 12, "max": 5}})

    def test_zoom_list_ok(self):
        assert normalize_manifest({"zoom": [6, 9]})["zRange"] == [6, 9]

    def test_zoom_list_invalid_values_rejected(self):
        with pytest.raises(TilePackageError, match="两个整数"):
            normalize_manifest({"zoom": ["a", "b"]})

    def test_zoom_levels_ok(self):
        assert normalize_manifest({"zoomLevels": [7, 8, 9]})["zRange"] == [7, 9]

    def test_zoom_levels_invalid_values_rejected(self):
        with pytest.raises(TilePackageError, match="整数列表"):
            normalize_manifest({"zoomLevels": ["x"]})

    def test_tile_count_invalid_rejected(self):
        with pytest.raises(TilePackageError, match="tileCount"):
            normalize_manifest({"tileCount": "3"})

    def test_tile_count_bool_rejected(self):
        with pytest.raises(TilePackageError, match="tileCount"):
            normalize_manifest({"tileCount": True})

    def test_total_bytes_negative_rejected(self):
        with pytest.raises(TilePackageError, match="totalBytes"):
            normalize_manifest({"totalBytes": -1})

    def test_empty_manifest_rejected(self):
        with pytest.raises(TilePackageError, match="缺少必要字段"):
            normalize_manifest({})

    def test_unknown_zoom_type_falls_back_to_tile_count(self):
        result = normalize_manifest({"zoom": "6-12", "tileCount": 0})
        assert result["zRange"] is None
        assert result["tileCount"] == 0


# ==================== read_manifest_file ====================


class TestReadManifestFile:
    def test_missing_returns_none(self, tmp_path):
        assert oms.read_manifest_file(tmp_path / "MANIFEST.json") is None

    def test_invalid_json_returns_none(self, tmp_path):
        path = tmp_path / "MANIFEST.json"
        path.write_text("{not json", encoding="utf-8")
        assert oms.read_manifest_file(path) is None

    def test_invalid_schema_returns_none(self, tmp_path):
        path = tmp_path / "MANIFEST.json"
        path.write_text(json.dumps({"foo": 1}), encoding="utf-8")
        assert oms.read_manifest_file(path) is None

    def test_valid_returns_normalized(self, tmp_path):
        path = tmp_path / "MANIFEST.json"
        path.write_bytes(_manifest_bytes())
        result = oms.read_manifest_file(path)
        assert result["provider"] == "osm"
        assert result["zRange"] == [5, 5]


# ==================== 内部校验函数 ====================


class TestManifestCrossCheck:
    def test_count_mismatch(self):
        with pytest.raises(TilePackageError, match="tileCount"):
            oms._check_manifest_against(
                {"tileCount": 2, "totalBytes": None, "zRange": None},
                [("5/1/2.png", 5, 1, 2)],
                10,
            )

    def test_bytes_mismatch(self):
        with pytest.raises(TilePackageError, match="totalBytes"):
            oms._check_manifest_against(
                {"tileCount": None, "totalBytes": 99, "zRange": None},
                [("5/1/2.png", 5, 1, 2)],
                10,
            )

    def test_z_range_mismatch(self):
        with pytest.raises(TilePackageError, match="缩放范围"):
            oms._check_manifest_against(
                {"tileCount": None, "totalBytes": None, "zRange": [6, 6]},
                [("5/1/2.png", 5, 1, 2)],
                10,
            )

    def test_all_match_passes(self):
        oms._check_manifest_against(
            {"tileCount": 1, "totalBytes": 10, "zRange": [5, 5]},
            [("5/1/2.png", 5, 1, 2)],
            10,
        )


class TestSafeRelative:
    def test_empty_rejected(self):
        with pytest.raises(TilePackageError, match="空文件名"):
            oms._safe_relative("")

    def test_absolute_rejected(self):
        with pytest.raises(TilePackageError, match="绝对路径"):
            oms._safe_relative("/etc/passwd")

    def test_drive_letter_rejected(self):
        with pytest.raises(TilePackageError, match="绝对路径"):
            oms._safe_relative("C:\\windows\\x.png")

    def test_parent_traversal_rejected(self):
        with pytest.raises(TilePackageError, match="路径穿越"):
            oms._safe_relative("../evil.png")

    def test_normalizes_backslashes_and_dots(self):
        assert oms._safe_relative(".\\5\\1\\.\\2.png") == "5/1/2.png"

    def test_only_dots_rejected(self):
        with pytest.raises(TilePackageError, match="路径穿越"):
            oms._safe_relative("..")


class TestParseTileRel:
    def test_bad_name_rejected(self):
        with pytest.raises(TilePackageError, match="非瓦片文件"):
            oms._parse_tile_rel("5/1/2.jpg")

    def test_zoom_out_of_range_rejected(self):
        with pytest.raises(TilePackageError, match="缩放级别超出范围"):
            oms._parse_tile_rel("23/1/1.png")

    def test_coordinates_out_of_range_rejected(self):
        with pytest.raises(TilePackageError, match="坐标越界"):
            oms._parse_tile_rel("1/2/0.png")

    def test_valid(self):
        assert oms._parse_tile_rel("10/512/256.png") == (10, 512, 256)


class TestWriteTile:
    def test_new_tile(self, tmp_path):
        count = oms._write_tile(tmp_path / "5" / "1" / "2.png", tmp_path, b"x")
        assert count == 0
        assert (tmp_path / "5" / "1" / "2.png").read_bytes() == b"x"

    def test_overwrite_returns_one(self, tmp_path):
        target = tmp_path / "5" / "1" / "2.png"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"old")
        assert oms._write_tile(target, tmp_path, b"new") == 1
        assert target.read_bytes() == b"new"

    def test_path_escape_rejected(self, tmp_path):
        dest = tmp_path / "store"
        dest.mkdir()
        with pytest.raises(TilePackageError, match="写入路径越界"):
            oms._write_tile(tmp_path / "outside.png", dest, b"x")


class TestVerifyTileHash:
    def test_non_dict_hashes_skipped(self):
        oms._verify_tile_hash(None, "5/1/2.png", b"x")

    def test_missing_key_skipped(self):
        oms._verify_tile_hash({}, "5/1/2.png", b"x")

    def test_match_passes(self):
        oms._verify_tile_hash(
            {"5/1/2.png": hashlib.sha256(b"x").hexdigest()}, "5/1/2.png", b"x"
        )

    def test_mismatch_rejected(self):
        with pytest.raises(TilePackageError, match="SHA256 校验失败"):
            oms._verify_tile_hash({"5/1/2.png": "deadbeef"}, "5/1/2.png", b"x")


class TestManifestPrefix:
    def test_missing(self):
        with pytest.raises(TilePackageError, match="缺少 MANIFEST"):
            oms._manifest_prefix(["5/1/2.png"])

    def test_multiple_rejected(self):
        with pytest.raises(TilePackageError, match="多个 MANIFEST"):
            oms._manifest_prefix(["MANIFEST.json", "tiles/MANIFEST.json"])

    def test_too_deep_rejected(self):
        with pytest.raises(TilePackageError, match="根目录或单一顶层目录"):
            oms._manifest_prefix(["a/b/MANIFEST.json"])

    def test_root_prefix(self):
        assert oms._manifest_prefix(["MANIFEST.json", "5/1/2.png"]) == ""

    def test_single_top_dir(self):
        assert oms._manifest_prefix(["tiles/MANIFEST.json"]) == "tiles/"


# ==================== ZIP 导入 ====================


class TestImportTileZip:
    def test_bad_zip_rejected(self, tmp_path):
        with pytest.raises(TilePackageError, match="不是有效的 ZIP"):
            import_tile_zip_bytes(b"not-a-zip", tmp_path / "store")

    def test_empty_zip_rejected(self, tmp_path):
        with pytest.raises(TilePackageError, match="为空"):
            import_tile_zip_bytes(_zip_bytes({}), tmp_path / "store")

    def test_missing_manifest_rejected(self, tmp_path):
        with pytest.raises(TilePackageError, match="缺少 MANIFEST"):
            import_tile_zip_bytes(_zip_bytes({"5/1/2.png": TILE_DATA}), tmp_path / "store")

    def test_multiple_manifests_rejected(self, tmp_path):
        payload = _zip_bytes(
            {
                "MANIFEST.json": _manifest_bytes(),
                "tiles/MANIFEST.json": _manifest_bytes(),
                "5/1/2.png": TILE_DATA,
            }
        )
        with pytest.raises(TilePackageError, match="多个 MANIFEST"):
            import_tile_zip_bytes(payload, tmp_path / "store")

    def test_deep_manifest_rejected(self, tmp_path):
        payload = _zip_bytes({"a/b/MANIFEST.json": _manifest_bytes(), "5/1/2.png": TILE_DATA})
        with pytest.raises(TilePackageError, match="根目录或单一顶层目录"):
            import_tile_zip_bytes(payload, tmp_path / "store")

    def test_absolute_member_rejected(self, tmp_path):
        payload = _zip_bytes({"/evil.png": TILE_DATA, "MANIFEST.json": _manifest_bytes()})
        with pytest.raises(TilePackageError, match="绝对路径"):
            import_tile_zip_bytes(payload, tmp_path / "store")

    def test_parent_traversal_rejected(self, tmp_path):
        payload = _zip_bytes({"../evil.png": TILE_DATA, "MANIFEST.json": _manifest_bytes()})
        with pytest.raises(TilePackageError, match="路径穿越"):
            import_tile_zip_bytes(payload, tmp_path / "store")

    def test_no_tiles_rejected(self, tmp_path):
        payload = _zip_bytes({"MANIFEST.json": _manifest_bytes(tile_count=0, total_bytes=0)})
        with pytest.raises(TilePackageError, match="没有瓦片文件"):
            import_tile_zip_bytes(payload, tmp_path / "store")

    def test_too_many_tiles_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(oms, "MAX_TILES_PER_IMPORT", 1)
        payload = _zip_bytes(
            {
                "MANIFEST.json": _manifest_bytes(tile_count=2, total_bytes=len(TILE_DATA) * 2),
                "5/1/2.png": TILE_DATA,
                "5/1/3.png": TILE_DATA,
            }
        )
        with pytest.raises(TilePackageError, match="超过单次导入上限"):
            import_tile_zip_bytes(payload, tmp_path / "store")

    def test_uncompressed_over_limit_rejected(self, tmp_path, monkeypatch):
        from fastapi import HTTPException

        monkeypatch.setattr(oms, "MAX_TILES_TOTAL_BYTES", 10)
        with pytest.raises(HTTPException) as excinfo:
            import_tile_zip_bytes(_single_tile_zip(), tmp_path / "store")
        assert excinfo.value.status_code == 413

    def test_manifest_too_large_rejected(self, tmp_path, monkeypatch):
        from fastapi import HTTPException

        monkeypatch.setattr(oms, "MAX_MANIFEST_BYTES", 10)
        with pytest.raises(HTTPException) as excinfo:
            import_tile_zip_bytes(_single_tile_zip(), tmp_path / "store")
        assert excinfo.value.status_code == 413

    def test_tile_member_too_large_rejected(self, tmp_path, monkeypatch):
        from fastapi import HTTPException

        monkeypatch.setattr(oms, "MAX_TILE_MEMBER_BYTES", 5)
        with pytest.raises(HTTPException) as excinfo:
            import_tile_zip_bytes(_single_tile_zip(), tmp_path / "store")
        assert excinfo.value.status_code == 413

    def test_manifest_invalid_json_rejected(self, tmp_path):
        payload = _zip_bytes(
            {"MANIFEST.json": b"{bad", "5/1/2.png": TILE_DATA}
        )
        with pytest.raises(TilePackageError, match="合法的 UTF-8 JSON"):
            import_tile_zip_bytes(payload, tmp_path / "store")

    def test_manifest_schema_invalid_rejected(self, tmp_path):
        payload = _zip_bytes(
            {"MANIFEST.json": b'{"tileCount": "x"}', "5/1/2.png": TILE_DATA}
        )
        with pytest.raises(TilePackageError, match="tileCount"):
            import_tile_zip_bytes(payload, tmp_path / "store")

    def test_count_mismatch_rejected(self, tmp_path):
        payload = _zip_bytes(
            {
                "MANIFEST.json": _manifest_bytes(tile_count=9),
                "5/1/2.png": TILE_DATA,
            }
        )
        with pytest.raises(TilePackageError, match="tileCount"):
            import_tile_zip_bytes(payload, tmp_path / "store")

    def test_bytes_mismatch_rejected(self, tmp_path):
        payload = _zip_bytes(
            {
                "MANIFEST.json": _manifest_bytes(total_bytes=999),
                "5/1/2.png": TILE_DATA,
            }
        )
        with pytest.raises(TilePackageError, match="totalBytes"):
            import_tile_zip_bytes(payload, tmp_path / "store")

    def test_z_range_mismatch_rejected(self, tmp_path):
        payload = _zip_bytes(
            {
                "MANIFEST.json": _manifest_bytes(z_range=(6, 6)),
                "5/1/2.png": TILE_DATA,
            }
        )
        with pytest.raises(TilePackageError, match="缩放范围"):
            import_tile_zip_bytes(payload, tmp_path / "store")

    def test_hash_mismatch_rejected(self, tmp_path):
        payload = _zip_bytes(
            {
                "MANIFEST.json": _manifest_bytes(hashes={"5/1/2.png": "deadbeef"}),
                "5/1/2.png": TILE_DATA,
            }
        )
        with pytest.raises(TilePackageError, match="SHA256"):
            import_tile_zip_bytes(payload, tmp_path / "store")

    def test_hash_match_imports(self, tmp_path):
        digest = hashlib.sha256(TILE_DATA).hexdigest()
        payload = _zip_bytes(
            {
                "MANIFEST.json": _manifest_bytes(hashes={"5/1/2.png": digest}),
                "5/1/2.png": TILE_DATA,
            }
        )
        store = tmp_path / "store"
        result = import_tile_zip_bytes(payload, store)
        assert result["tileCount"] == 1
        assert (store / "5" / "1" / "2.png").read_bytes() == TILE_DATA

    def test_success_ignores_non_tile_and_foreign_root(self, tmp_path):
        payload = _zip_bytes(
            {
                "MANIFEST.json": _manifest_bytes(),
                "5/1/2.png": TILE_DATA,
                "readme.txt": b"hello",
                "__MACOSX/5/1/2.png": TILE_DATA,
            }
        )
        store = tmp_path / "store"
        result = import_tile_zip_bytes(payload, store)
        assert result["tileCount"] == 1
        assert result["ignored"] == 2
        assert (store / "MANIFEST.json").is_file()
        manifest = json.loads((store / "MANIFEST.json").read_text(encoding="utf-8"))
        assert manifest["provider"] == "osm"

    def test_nested_prefix_and_backslash_members_import(self, tmp_path):
        payload = _zip_bytes(
            {
                "tiles\\MANIFEST.json": _manifest_bytes(),
                "tiles\\5\\1\\2.png": TILE_DATA,
                # 与 MANIFEST 不同根目录的文件 → 计为 ignored 而不是导入
                "readme.txt": b"outside the package root",
            }
        )
        store = tmp_path / "store"
        result = import_tile_zip_bytes(payload, store)
        assert result["tileCount"] == 1
        assert result["ignored"] == 1
        assert (store / "5" / "1" / "2.png").is_file()

    def test_merge_overwrites_existing(self, tmp_path):
        store = tmp_path / "store"
        _write_tile(store, 5, 1, 2, b"old")
        result = import_tile_zip_bytes(_single_tile_zip(), store)
        assert result["overwritten"] == 1
        assert (store / "5" / "1" / "2.png").read_bytes() == TILE_DATA

    def test_zip_with_directory_entries_ok(self, tmp_path):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("MANIFEST.json", _manifest_bytes())
            zf.writestr("5/", b"")
            zf.writestr("5/1/", b"")
            zf.writestr("5/1/2.png", TILE_DATA)
        store = tmp_path / "store"
        assert import_tile_zip_bytes(buffer.getvalue(), store)["tileCount"] == 1


# ==================== 本机目录导入 ====================


class TestImportTileDirectory:
    def test_missing_dir_rejected(self, tmp_path):
        with pytest.raises(TilePackageError, match="瓦片目录不存在"):
            import_tile_directory(tmp_path / "absent", tmp_path / "store")

    def test_missing_manifest_rejected(self, tmp_path):
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        with pytest.raises(TilePackageError, match="缺少 MANIFEST"):
            import_tile_directory(src, tmp_path / "store")

    def test_multiple_sub_manifests_rejected(self, tmp_path):
        src = tmp_path / "src"
        for name in ("a", "b"):
            (src / name).mkdir(parents=True)
            (src / name / "MANIFEST.json").write_bytes(_manifest_bytes())
        with pytest.raises(TilePackageError, match="缺少 MANIFEST"):
            import_tile_directory(src, tmp_path / "store")

    def test_success_direct_manifest(self, tmp_path):
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        (src / "MANIFEST.json").write_bytes(_manifest_bytes())
        (src / "readme.txt").write_text("ignore me", encoding="utf-8")
        store = tmp_path / "store"
        result = import_tile_directory(src, store)
        assert result["tileCount"] == 1
        assert result["ignored"] == 1
        assert (store / "5" / "1" / "2.png").is_file()
        assert (store / "MANIFEST.json").is_file()

    def test_success_single_subdir(self, tmp_path):
        src = tmp_path / "src"
        nested = src / "tiles"
        _write_tile(nested, 5, 1, 2)
        (nested / "MANIFEST.json").write_bytes(_manifest_bytes())
        store = tmp_path / "store"
        assert import_tile_directory(src, store)["tileCount"] == 1

    def test_symlink_dir_rejected(self, tmp_path):
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        (src / "MANIFEST.json").write_bytes(_manifest_bytes())
        (src / "linked").mkdir()
        real_islink = os.path.islink

        def fake_islink(path):
            return Path(path).name == "linked" or real_islink(path)

        with patch.object(oms.os.path, "islink", side_effect=fake_islink):
            with pytest.raises(TilePackageError, match="符号链接"):
                import_tile_directory(src, tmp_path / "store")

    def test_symlink_file_rejected(self, tmp_path):
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        (src / "MANIFEST.json").write_bytes(_manifest_bytes())
        real_islink = os.path.islink

        def fake_islink(path):
            return Path(path).name == "2.png" or real_islink(path)

        with patch.object(oms.os.path, "islink", side_effect=fake_islink):
            with pytest.raises(TilePackageError, match="符号链接"):
                import_tile_directory(src, tmp_path / "store")

    def test_no_tiles_rejected(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "MANIFEST.json").write_bytes(_manifest_bytes(tile_count=0, total_bytes=0))
        with pytest.raises(TilePackageError, match="没有瓦片文件"):
            import_tile_directory(src, tmp_path / "store")

    def test_too_many_tiles_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(oms, "MAX_TILES_PER_IMPORT", 1)
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        _write_tile(src, 5, 1, 3)
        (src / "MANIFEST.json").write_bytes(
            _manifest_bytes(tile_count=2, total_bytes=len(TILE_DATA) * 2)
        )
        with pytest.raises(TilePackageError, match="超过单次导入上限"):
            import_tile_directory(src, tmp_path / "store")

    def test_total_bytes_over_limit_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(oms, "MAX_TILES_TOTAL_BYTES", 10)
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        (src / "MANIFEST.json").write_bytes(_manifest_bytes())
        with pytest.raises(TilePackageError, match="总体积"):
            import_tile_directory(src, tmp_path / "store")

    def test_manifest_too_large_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(oms, "MAX_MANIFEST_BYTES", 5)
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        (src / "MANIFEST.json").write_bytes(_manifest_bytes())
        with pytest.raises(TilePackageError, match="字节上限"):
            import_tile_directory(src, tmp_path / "store")

    def test_manifest_stat_failure_rejected(self, tmp_path):
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        manifest = src / "MANIFEST.json"
        manifest.write_bytes(_manifest_bytes())
        real_stat = Path.stat

        def flaky_stat(self, *args, **kwargs):
            if self.name == "MANIFEST.json":
                raise OSError("locked")
            return real_stat(self, *args, **kwargs)

        # 定位阶段先短路（同时覆盖 _locate_manifest_root 的单一返回口），
        # 让 stat 失败真实发生在读取 MANIFEST 体积处
        with patch.object(oms, "_locate_manifest_root", return_value=(src, manifest)), patch.object(
            Path, "stat", flaky_stat
        ):
            with pytest.raises(TilePackageError, match="读取 MANIFEST"):
                import_tile_directory(src, tmp_path / "store")

    def test_tile_too_large_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setattr(oms, "MAX_TILE_MEMBER_BYTES", 5)
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        (src / "MANIFEST.json").write_bytes(_manifest_bytes())
        with pytest.raises(TilePackageError, match="字节上限"):
            import_tile_directory(src, tmp_path / "store")

    def test_tile_stat_failure_rejected(self, tmp_path):
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        (src / "MANIFEST.json").write_bytes(_manifest_bytes())
        real_stat = Path.stat

        def flaky_stat(self, *args, **kwargs):
            if self.name == "2.png":
                raise OSError("locked")
            return real_stat(self, *args, **kwargs)

        with patch.object(Path, "stat", flaky_stat):
            with pytest.raises(TilePackageError, match="读取瓦片失败"):
                import_tile_directory(src, tmp_path / "store")

    def test_count_mismatch_rejected(self, tmp_path):
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        (src / "MANIFEST.json").write_bytes(_manifest_bytes(tile_count=3))
        with pytest.raises(TilePackageError, match="tileCount"):
            import_tile_directory(src, tmp_path / "store")

    def test_hash_mismatch_rejected(self, tmp_path):
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        (src / "MANIFEST.json").write_bytes(_manifest_bytes(hashes={"5/1/2.png": "bad"}))
        with pytest.raises(TilePackageError, match="SHA256"):
            import_tile_directory(src, tmp_path / "store")


# ==================== /map/tile-info 与 /map/tiles/import ====================


class TestResolveTilesDirPriority:
    def test_env_wins_over_meipass(self, tmp_path, monkeypatch):
        meipass = tmp_path / "frozen"
        (meipass / "resources" / "map-tiles").mkdir(parents=True)
        monkeypatch.setattr(map_mod.sys, "_MEIPASS", str(meipass), raising=False)
        monkeypatch.setenv("MAP_TILES_DIR", str(tmp_path / "custom"))
        assert map_mod._resolve_tiles_dir() == tmp_path / "custom"

    def test_meipass_when_no_env(self, tmp_path, monkeypatch):
        meipass = tmp_path / "frozen"
        tiles = meipass / "resources" / "map-tiles"
        tiles.mkdir(parents=True)
        monkeypatch.setattr(map_mod.sys, "_MEIPASS", str(meipass), raising=False)
        monkeypatch.delenv("MAP_TILES_DIR", raising=False)
        assert map_mod._resolve_tiles_dir() == tiles

    def test_default_repo_resources(self, monkeypatch):
        monkeypatch.delattr(map_mod.sys, "_MEIPASS", raising=False)
        monkeypatch.delenv("MAP_TILES_DIR", raising=False)
        result = map_mod._resolve_tiles_dir()
        assert result.name == "map-tiles"
        assert result.parent.name == "resources"


class TestTileInfo:
    def test_dir_missing(self, client, tmp_path):
        with patch.object(map_mod, "TILES_DIR", tmp_path / "absent"):
            resp = client.get(f"{MAP_BASE}/tile-info")
        data = resp.json()["data"]
        assert data["available"] is False
        assert data["tileCount"] == 0
        assert data["zoomLevels"] == []
        assert data["totalBytes"] == 0
        assert data["manifest"] is None
        assert data["dir"] == "absent"

    def test_dir_without_zoom_levels(self, client, tmp_path):
        (tmp_path / "not-a-zoom").mkdir()
        with patch.object(map_mod, "TILES_DIR", tmp_path):
            data = client.get(f"{MAP_BASE}/tile-info").json()["data"]
        assert data["available"] is False
        assert data["zoomLevels"] == []

    def test_available_with_manifest(self, client, store):
        with patch.object(map_mod, "TILES_DIR", store):
            data = client.get(f"{MAP_BASE}/tile-info").json()["data"]
        assert data["available"] is True
        assert data["tileCount"] == 1
        assert data["zoomLevels"] == [5]
        assert data["minZoom"] == 5
        assert data["maxZoom"] == 5
        assert data["totalBytes"] == len(TILE_DATA)
        assert data["dir"] == store.name
        # 安全口径：不泄露完整磁盘路径
        assert "\\" not in data["dir"] and "/" not in data["dir"]
        assert data["manifest"]["provider"] == "osm"
        assert data["manifest"]["zRange"] == [5, 5]

    def test_invalid_manifest_returns_null(self, client, tmp_path):
        _write_tile(tmp_path, 5, 1, 2)
        (tmp_path / "MANIFEST.json").write_text("{broken", encoding="utf-8")
        with patch.object(map_mod, "TILES_DIR", tmp_path):
            data = client.get(f"{MAP_BASE}/tile-info").json()["data"]
        assert data["available"] is True
        assert data["manifest"] is None


class TestImportEndpoint:
    def _url(self):
        return f"{MAP_BASE}/tiles/import"

    def test_requires_admin(self, client_with_regular_user_auth):
        resp = client_with_regular_user_auth.post(
            self._url(), files={"file": ("t.zip", _single_tile_zip(), "application/zip")}
        )
        assert resp.status_code == 403

    def test_anonymous_rejected(self, client):
        resp = client.post(
            self._url(), files={"file": ("t.zip", _single_tile_zip(), "application/zip")}
        )
        assert resp.status_code == 401

    def test_no_file_and_no_source_dir(self, admin_client, tmp_path):
        with patch.object(map_mod, "TILES_DIR", tmp_path / "store"):
            resp = admin_client.post(self._url())
        assert resp.status_code == 400
        assert "file" in resp.json()["detail"]

    def test_both_sources_rejected(self, admin_client, tmp_path):
        with patch.object(map_mod, "TILES_DIR", tmp_path / "store"):
            resp = admin_client.post(
                self._url(),
                files={"file": ("t.zip", _single_tile_zip(), "application/zip")},
                data={"source_dir": str(tmp_path)},
            )
        assert resp.status_code == 400
        assert "二选一" in resp.json()["detail"]

    def test_upload_success(self, admin_client, tmp_path):
        store = tmp_path / "store"
        with patch.object(map_mod, "TILES_DIR", store), patch.object(
            map_mod.AuditLogger, "log"
        ) as audit:
            resp = admin_client.post(
                self._url(), files={"file": ("t.zip", _single_tile_zip(), "application/zip")}
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["tileCount"] == 1
        assert data["totalBytes"] == len(TILE_DATA)
        assert data["source"] == "upload"
        assert data["zoomLevels"] == [5]
        assert data["store"]["tileCount"] == 1
        assert (store / "5" / "1" / "2.png").is_file()
        audit.assert_called_once()
        assert audit.call_args.kwargs["details"]["origin"] == "upload"

    def test_local_directory_success(self, admin_client, tmp_path):
        src = tmp_path / "src"
        _write_tile(src, 5, 1, 2)
        (src / "MANIFEST.json").write_bytes(_manifest_bytes())
        store = tmp_path / "store"
        with patch.object(map_mod, "TILES_DIR", store), patch.object(map_mod.AuditLogger, "log"):
            resp = admin_client.post(self._url(), data={"source_dir": str(src)})
        assert resp.status_code == 200
        assert resp.json()["data"]["source"] == "local-directory"
        assert (store / "5" / "1" / "2.png").is_file()

    def test_invalid_package_returns_400(self, admin_client, tmp_path):
        with patch.object(map_mod, "TILES_DIR", tmp_path / "store"):
            resp = admin_client.post(
                self._url(), files={"file": ("t.zip", b"not-a-zip", "application/zip")}
            )
        assert resp.status_code == 400
        assert "ZIP" in resp.json()["detail"]

    def test_missing_source_dir_returns_400(self, admin_client, tmp_path):
        with patch.object(map_mod, "TILES_DIR", tmp_path / "store"):
            resp = admin_client.post(self._url(), data={"source_dir": str(tmp_path / "absent")})
        assert resp.status_code == 400

    def test_write_error_returns_500(self, admin_client, tmp_path):
        with patch.object(map_mod, "TILES_DIR", tmp_path / "store"), patch.object(
            map_mod, "import_tile_zip_bytes", side_effect=OSError("disk full")
        ):
            resp = admin_client.post(
                self._url(), files={"file": ("t.zip", _single_tile_zip(), "application/zip")}
            )
        assert resp.status_code == 500
        assert "写入失败" in resp.json()["detail"]

    def test_unexpected_error_returns_400(self, admin_client, tmp_path):
        with patch.object(map_mod, "TILES_DIR", tmp_path / "store"), patch.object(
            map_mod, "import_tile_zip_bytes", side_effect=RuntimeError("boom")
        ):
            resp = admin_client.post(
                self._url(), files={"file": ("t.zip", _single_tile_zip(), "application/zip")}
            )
        assert resp.status_code == 400
        assert "解析失败" in resp.json()["detail"]

    def test_oversized_upload_returns_413(self, admin_client, tmp_path, monkeypatch):
        monkeypatch.setattr(map_mod, "MAX_TILE_UPLOAD_BYTES", 10)
        with patch.object(map_mod, "TILES_DIR", tmp_path / "store"):
            resp = admin_client.post(
                self._url(), files={"file": ("t.zip", _single_tile_zip(), "application/zip")}
            )
        assert resp.status_code == 413

    def test_audit_failure_does_not_break_import(self, admin_client, tmp_path):
        store = tmp_path / "store"
        with patch.object(map_mod, "TILES_DIR", store), patch.object(
            map_mod.AuditLogger, "log", side_effect=RuntimeError("audit down")
        ):
            resp = admin_client.post(
                self._url(), files={"file": ("t.zip", _single_tile_zip(), "application/zip")}
            )
        assert resp.status_code == 200
        assert (store / "5" / "1" / "2.png").is_file()


# ==================== /offline-map/status 与 /download ====================


class TestOfflineMapStatus:
    def test_status_reads_real_directory(self, client, store):
        with patch.object(offline_mod, "TILES_DIR", store):
            data = client.get(f"{OFFLINE_BASE}/status").json()["data"]
        assert data["available"] is True
        assert data["tileCount"] == 1
        assert data["tileCount"] == data["total_tiles"]
        assert data["zoomLevels"] == [5]
        assert data["zoom_levels"] == [5]
        assert data["downloadSupported"] is False
        assert "cache" in data

    def test_status_when_dir_missing(self, client, tmp_path):
        with patch.object(offline_mod, "TILES_DIR", tmp_path / "absent"):
            data = client.get(f"{OFFLINE_BASE}/status").json()["data"]
        assert data["available"] is False
        assert data["tileCount"] == 0

    def test_status_error(self, client):
        with patch.object(
            offline_mod.offline_map_service, "get_coverage", side_effect=RuntimeError("x")
        ):
            resp = client.get(f"{OFFLINE_BASE}/status")
        assert resp.status_code in (400, 500)
        assert "获取离线地图状态失败" in resp.text


class TestOfflineDownloadUnsupported:
    def test_download_returns_501(self, admin_client):
        resp = admin_client.post(
            f"{OFFLINE_BASE}/download",
            params={
                "min_lat": 25.0,
                "max_lat": 26.0,
                "min_lon": 106.0,
                "max_lon": 107.0,
                "min_zoom": 4,
                "max_zoom": 12,
            },
        )
        assert resp.status_code == 501
        assert "不支持在线抓取" in resp.json()["detail"]
        assert "import" in resp.json()["detail"]

    def test_download_without_params_still_501(self, admin_client):
        assert admin_client.post(f"{OFFLINE_BASE}/download").status_code == 501

    def test_download_anonymous_rejected(self, client):
        assert client.post(f"{OFFLINE_BASE}/download").status_code == 401
