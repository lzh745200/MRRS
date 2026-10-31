"""`scripts/tiles` 稀疏层级包校验单测（v1.18.31）。

背景：v1.18.31 起瓦片包改为「z5–8 全省概览 + z13/z14 明细」的稀疏层级形态。
旧的 `verify_tiles` 只认连续层级（`range(min, max+1)`），会把这种**故意稀疏**的包判成
「切片中断」→ 交付前自检恒失败。这里锁定修复后的口径：

- MANIFEST 显式声明 `zoomLevels` → 只校验声明层级齐全、不允许未声明层级（稀疏合法）；
- MANIFEST 未声明 → 仍按连续口径检查（历史包不允许静默缺层）。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3] / "scripts" / "tiles"


def _load(name: str):
    """按文件路径加载 scripts/tiles 下的脚本（该目录不是包，无 __init__.py）。"""
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_common = _load("_common")
verify_mod = _load("verify_tiles")


def _png(path: Path) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (4, 4), (0, 0, 0, 0)).save(path, format="PNG")


def _write_sparse(root: Path, levels=(5, 6, 7, 8, 13)) -> None:
    for z in levels:
        _png(root / str(z) / "0" / "0.png")


class TestNormalizeManifestZoomLevels:
    def test_declared_levels_are_kept_sorted_and_unique(self):
        result = _common.normalize_manifest({"zoomLevels": [13, 5, 8, 5]})
        assert result["zoomLevels"] == [5, 8, 13]
        # 兼容旧字段：无 zoom 时 zRange 由声明层级推导
        assert result["zRange"] == [5, 13]

    def test_levels_absent_returns_none(self):
        result = _common.normalize_manifest({"zoom": {"min": 5, "max": 12}})
        assert result["zoomLevels"] is None

    def test_invalid_levels_rejected(self):
        import pytest

        with pytest.raises(_common.TileToolError):
            _common.normalize_manifest({"zoomLevels": ["x"]})


class TestVerifySparsePackages:
    def _manifest(self, root: Path, levels, tile_count=None, declared=True):
        payload = {
            "provider": "osm-render",
            "tileCount": tile_count if tile_count is not None else len(levels),
            "zoom": {"min": min(levels), "max": max(levels)},
        }
        if declared:
            payload["zoomLevels"] = list(levels)
        (root / "MANIFEST.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_sparse_levels_pass_when_declared(self, tmp_path):
        levels = (5, 6, 7, 8, 13)
        _write_sparse(tmp_path, levels)
        self._manifest(tmp_path, levels)
        report = verify_mod.verify(tmp_path, require_min=0, sample=5)
        assert report["problems"] == []
        assert report["exitCode"] == 0

    def test_contiguous_gap_fails_without_declared_levels(self, tmp_path):
        levels = (5, 6, 7, 8, 13)
        _write_sparse(tmp_path, levels)
        self._manifest(tmp_path, levels, declared=False)
        report = verify_mod.verify(tmp_path, require_min=0, sample=5)
        assert any("不连续" in problem for problem in report["problems"])

    def test_declared_but_missing_level_fails(self, tmp_path):
        actual = (5, 6, 7, 8)
        _write_sparse(tmp_path, actual)
        self._manifest(tmp_path, (5, 6, 7, 8, 13))
        report = verify_mod.verify(tmp_path, require_min=0, sample=5)
        assert any("声明的层级缺失" in problem for problem in report["problems"])

    def test_undeclared_extra_level_fails(self, tmp_path):
        actual = (5, 6, 7, 8, 13)
        _write_sparse(tmp_path, actual)
        self._manifest(tmp_path, (5, 6, 7, 8))
        report = verify_mod.verify(tmp_path, require_min=0, sample=5)
        assert any("未声明的层级" in problem for problem in report["problems"])
