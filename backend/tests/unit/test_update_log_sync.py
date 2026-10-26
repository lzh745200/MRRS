# -*- coding: utf-8 -*-
"""应用内「更新日志」数据一致性回归测试。

背景：应用内更新日志曾由 `update_log_service.py` 里的硬编码列表驱动，与 CHANGELOG.md
各写各的，长期停在 1.1.1（落后 17 个小版本）。现在数据由 CHANGELOG.md 生成，
本测试在单元测试层再兜一道：生成文件必须与 CHANGELOG 完全一致，且最新版本必须等于
backend/version.json 的版本。
"""
import importlib.util
import json
from pathlib import Path

from app.services.version_history_data import VERSION_HISTORY_DATA

REPO = Path(__file__).resolve().parents[3]
SYNC_SCRIPT = REPO / "scripts" / "sync_update_log.py"
VERSION_JSON = REPO / "backend" / "version.json"


def _load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_update_log", SYNC_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _semver(version: str):
    return tuple(int(part) for part in version.split("."))


class TestVersionHistoryData:
    def test_non_empty_and_ascending(self):
        """历史数据非空，且按语义化版本升序（倒序列表依赖这个顺序）。"""
        assert len(VERSION_HISTORY_DATA) >= 10
        versions = [_semver(item["version"]) for item in VERSION_HISTORY_DATA]
        assert versions == sorted(versions)
        assert len(set(versions)) == len(versions), "存在重复版本号"

    def test_every_entry_has_required_fields(self):
        for item in VERSION_HISTORY_DATA:
            assert item["version"]
            assert item["date"]
            assert item["description"]
            assert item["features"], "版本 %s 没有更新条目" % item["version"]

    def test_latest_matches_version_json(self):
        """最新一条必须等于 backend/version.json 的版本——否则应用内更新日志就是旧的。"""
        current = json.loads(VERSION_JSON.read_text(encoding="utf-8"))["version"]
        assert VERSION_HISTORY_DATA[-1]["version"] == current


class TestGeneratedFileInSync:
    def test_generated_file_matches_changelog(self):
        """version_history_data.py 必须与 CHANGELOG.md 生成结果逐字节一致。"""
        sync = _load_sync_module()
        parsed = sync.parse_changelog(sync.CHANGELOG.read_text(encoding="utf-8"))
        expected = sync.render(parsed)
        actual = sync.TARGET.read_text(encoding="utf-8")
        assert actual == expected, "请运行 python3 scripts/sync_update_log.py 重新生成"

    def test_parse_skips_unreleased_sections(self):
        """解析必须跳过 [Unreleased] / [未发布] 等非发布段。"""
        sync = _load_sync_module()
        parsed = sync.parse_changelog(
            "# 更新日志\n\n"
            "## [Unreleased] - 2026-10-01 — 未发布内容\n\n- 不该出现\n\n"
            "## [1.2.3] - 2026-09-01 — 正式发布\n\n- 该出现\n"
        )
        assert [item["version"] for item in parsed] == ["1.2.3"]
        assert parsed[0]["features"] == ["该出现"]
