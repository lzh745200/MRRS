"""z13 升级：OSM POI 图层（schema v3）与渲染 POI 注记的单元测试。

覆盖两层：
- `scripts/tiles/osm_extract.py`：amenity 白名单、名称优先级/截断、way 质心、
  bbox 过滤与去重、schema v3 payload（`pois` 键 + `meta.counts.pois`）；
- `scripts/tiles/render_osm_tiles.py`：`pois` 向后兼容（v2 pkl 无该键）、POI 最小
  缩放（大学/学院 z12、学校/幼儿园 z13）、标签上限 32、优先级（大学/学院 >
  学校/幼儿园 > 村）、村名 z11 行为不回归、POI 候选携带 marker 标记。

脚本模块用 `spec_from_file_location` 独立加载（沿用仓库脚本测试风格）。
"""

from __future__ import annotations

import importlib.util
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TILES_DIR = Path(__file__).resolve().parents[3] / "scripts" / "tiles"
if str(TILES_DIR) not in sys.path:
    sys.path.insert(0, str(TILES_DIR))


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"tiles_{name}", TILES_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extract = _load_script("osm_extract")
render = _load_script("render_osm_tiles")


# ==================== extract：POI 分类 / 名称 / 质心 ====================


class TestExtractPoiClassification:
    def test_amenity_whitelist(self):
        assert extract._amenity_class({"amenity": "school"}) == "school"
        assert extract._amenity_class({"amenity": "kindergarten"}) == "kindergarten"
        assert extract._amenity_class({"amenity": "college"}) == "college"
        assert extract._amenity_class({"amenity": "university"}) == "university"
        assert extract._amenity_class({"amenity": " School "}) == "school"  # 大小写/空白容忍
        assert extract._amenity_class({"amenity": "hospital"}) is None
        assert extract._amenity_class({}) is None

    def test_schema_version_is_v3(self):
        assert extract.SCHEMA_VERSION == 3
        assert extract.POI_AMENITIES == ("school", "kindergarten", "college", "university")

    def test_encode_poi_name_priority_and_truncation(self):
        payload = extract._encode_poi(
            {"name": "Fallback School", "name:zh": "甲秀小学"}, 106.7, 26.5, "school"
        )
        assert payload == {
            "name": "甲秀小学",
            "name_zh": "甲秀小学",
            "cls": "school",
            "lon": 106.7,
            "lat": 26.5,
            "amenity": "school",
        }
        # 无 name:zh → 回退 name
        assert extract._encode_poi({"name": "B School"}, 106.0, 26.0, "school")["name"] == "B School"
        # 名称截断到 100
        long_name = "学" * 130
        assert len(extract._encode_poi({"name": long_name}, 106.0, 26.0, "school")["name"]) == 100

    def test_encode_poi_without_name_returns_none(self):
        assert extract._encode_poi({"amenity": "school"}, 106.0, 26.0, "school") is None
        assert extract._encode_poi({"name": "   "}, 106.0, 26.0, "school") is None

    def test_way_centroid(self):
        segments = [[(106.0, 26.0), (106.2, 26.0)], [(106.2, 26.4)]]
        lon, lat = extract._way_centroid(segments)
        assert lon == pytest.approx((106.0 + 106.2 + 106.2) / 3.0)
        assert lat == pytest.approx((26.0 + 26.0 + 26.4) / 3.0)
        assert extract._way_centroid([]) is None

    def test_build_pois_filters_bbox_dedupes_and_counts(self):
        handler = SimpleNamespace(
            raw_pois=[
                {"name": "甲秀小学", "name_zh": "甲秀小学", "cls": "school",
                 "lon": 106.71, "lat": 26.56, "amenity": "school"},
                {"name": "甲秀小学", "name_zh": "甲秀小学", "cls": "school",
                 "lon": 106.71, "lat": 26.56, "amenity": "school"},  # 重复
                {"name": "省外学校", "name_zh": "", "cls": "school",
                 "lon": 110.5, "lat": 26.56, "amenity": "school"},  # bbox 外
            ],
            skipped={"out_of_bbox": 0},
        )
        pois, counts, bbox = extract.build_pois(handler, (103.6, 24.6, 109.6, 29.2))
        assert len(pois) == 1
        assert counts["school"] == 1
        assert counts["university"] == 0
        assert bbox == [106.71, 26.56, 106.71, 26.56]
        assert handler.skipped["out_of_bbox"] == 1
        assert handler.raw_pois == []  # 处理完及时释放

    def test_build_payload_contains_pois_and_counts(self):
        payload = extract._build_payload(
            Path("guizhou.osm.pbf"), 123, [103.6, 24.6, 109.6, 29.2],
            {"lines": {}, "polys": {}, "places": {}, "pois": {"school": 2}},
            [], [], [], [{"name": "甲秀小学", "name_zh": "", "cls": "school",
                          "lon": 106.7, "lat": 26.5, "amenity": "school"}],
            [],
        )
        assert payload["meta"]["schema_version"] == 3
        assert payload["meta"]["counts"]["pois"] == {"school": 2}
        assert payload["pois"][0]["amenity"] == "school"


# ==================== render：POI 注记 ====================


def _layers(pois=None, places=None):
    return {
        "lines": [],
        "polys": [],
        "places": places or [],
        "pois": pois or [],
    }


def _to_px(lon, lat):
    """测试用简单投影：经/纬度各 100px/度，围绕 (107, 26)。"""
    return (128 + (lon - 107.0) * 100.0, 128 - (lat - 26.0) * 100.0)


QUERY_BOX = (106.0, 25.0, 108.0, 27.0)
RECT = (0.0, 0.0, 256.0, 256.0)


class TestRenderPoiConstants:
    def test_max_labels_raised_to_32(self):
        assert render.MAX_LABELS == 32

    def test_poi_min_zoom_table(self):
        assert render.POI_MIN_ZOOM == {
            "university": 12,
            "college": 12,
            "school": 13,
            "kindergarten": 13,
        }

    def test_village_min_zoom_unchanged(self):
        # z11/12 行为不变（回归红线）：村/屯仍从 z11 起绘
        assert render.PLACE_MIN_ZOOM["village"] == 11
        assert render.PLACE_MIN_ZOOM["hamlet"] == 11
        assert render.PLACE_MIN_ZOOM["town"] == 10
        assert render.PLACE_MIN_ZOOM["city"] == 8

    def test_poi_priority_ordering(self):
        p = render.LABEL_PRIORITY
        assert p["university"] < p["college"] < p["school"] < p["kindergarten"] < p["village"]


class TestLoadLayersBackwardCompatibility:
    def _write_pkl(self, tmp_path, payload):
        path = tmp_path / "layers.pkl"
        path.write_bytes(pickle.dumps(payload))
        return path

    def test_v2_pickle_without_pois_still_loads(self, tmp_path):
        path = self._write_pkl(tmp_path, {
            "meta": {"schema_version": 2},
            "lines": [], "polys": [], "places": [],
        })
        layers = render.load_layers(path)
        assert layers["pois"] == []

    def test_v3_pois_normalized(self, tmp_path):
        path = self._write_pkl(tmp_path, {
            "meta": {"schema_version": 3},
            "lines": [], "polys": [], "places": [],
            "pois": [
                {"name": "甲秀小学", "name_zh": "", "cls": "school", "lon": 106.7, "lat": 26.5},
                {"name": "贵州大学", "name_zh": "贵州大学", "cls": "university", "lon": 106.6, "lat": 26.4},
                {"name": "坏类别", "cls": "hospital", "lon": 106.6, "lat": 26.4},
                {"name": "", "cls": "school", "lon": 106.6, "lat": 26.4},
                {"name": "越界", "cls": "school", "lon": 200.0, "lat": 26.4},
                "not-a-dict",
            ],
        })
        layers = render.load_layers(path)
        assert [p.name for p in layers["pois"]] == ["甲秀小学", "贵州大学"]
        assert [p.cls for p in layers["pois"]] == ["school", "university"]


class TestPoiLabels:
    def _renderer(self):
        pois = [
            render.PoiItem("贵州大学", "university", 106.60, 26.40),
            render.PoiItem("甲秀小学", "school", 106.70, 26.55),
            render.PoiItem("第二幼儿园", "kindergarten", 106.75, 26.60),
        ]
        return render.Renderer(_layers(pois=pois), None, "")

    def _poi_candidates(self, z):
        renderer = self._renderer()
        return [
            c for c in renderer._label_candidates(_to_px, z, QUERY_BOX, RECT, [])
            if getattr(c, "marker", False)
        ]

    def test_schools_only_from_z13(self):
        assert self._poi_candidates(12)  # 大学/学院在 z12
        texts_z12 = {c.text for c in self._poi_candidates(12)}
        assert texts_z12 == {"贵州大学"}
        texts_z13 = {c.text for c in self._poi_candidates(13)}
        assert texts_z13 == {"贵州大学", "甲秀小学", "第二幼儿园"}

    def test_poi_candidates_marked_and_priority_ordered(self):
        candidates = self._poi_candidates(13)
        for candidate in candidates:
            assert candidate.marker is True
        priorities = [c.priority for c in sorted(candidates, key=lambda c: c.priority)]
        assert priorities == sorted(priorities)
        assert min(priorities) < render.LABEL_PRIORITY["village"]

    def test_poi_outside_rect_skipped(self):
        pois = [render.PoiItem("远处小学", "school", 110.0, 26.5)]
        renderer = render.Renderer(_layers(pois=pois), None, "")
        assert renderer._label_candidates(_to_px, 13, (109.0, 26.0, 111.0, 27.0), RECT, []) == []

    def test_village_still_drawn_from_z11(self):
        village = render.PlaceItem("幸福村", "village", 106.65, 26.50, None)
        renderer = render.Renderer(_layers(places=[village]), None, "")
        labels_z10 = renderer._label_candidates(_to_px, 10, QUERY_BOX, RECT, [])
        labels_z11 = renderer._label_candidates(_to_px, 11, QUERY_BOX, RECT, [])
        assert labels_z10 == []
        assert [c.text for c in labels_z11] == ["幸福村"]

    def test_poi_render_can_be_disabled(self):
        """`--no-poi` 的等价开关：关闭后不产生 POI 候选（z12 可完全复现旧样式）。"""
        renderer = self._renderer()
        assert renderer._label_candidates(_to_px, 13, QUERY_BOX, RECT, [])
        renderer.pois = []
        assert not [
            c for c in renderer._label_candidates(_to_px, 13, QUERY_BOX, RECT, [])
            if getattr(c, "marker", False)
        ]
