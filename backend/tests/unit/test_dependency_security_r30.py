"""R30 回归锁定：依赖安全加固。

一、可修复依赖已升级（pip-audit：5 包 24 条唯一公告 → 1 包 1 条）
    pyjwt 2.9.0 → 2.13.0、pillow 12.2.0 → 12.3.0、mammoth 1.6.0 → 1.11.0、
    filelock 3.13.1 → 3.32.6（四个 requirements 文件同步）。
    本文件锁定"安装版本不低于修复版本"，防止回退。

二、不可修复依赖改用安全序列化：diskcache ≤5.6.3 默认 pickle
    （CVE-2025-69872 / PYSEC-2026-2447：能写缓存目录者可在读取时执行任意代码，
    上游 last_affected=5.6.3、无修复版本）。本项目两处 diskcache 用法
    （dashboard 统计缓存、map 距离缓存）内容均为纯 JSON 结构，改用内置
    `JSONDisk` 后行为等价且彻底消除反序列化执行面。
"""

import re
from importlib import metadata
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
REQ = BACKEND / "requirements.txt"

# pip-audit 给出的修复版本（PyPI 包名 → 最低安全版本）
MIN_SAFE = {
    "PyJWT": (2, 13, 0),
    "pillow": (12, 3, 0),
    "mammoth": (1, 11, 0),
    "filelock": (3, 32, 6),
}


def _parse(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


class TestVulnerablePinsUpgraded:
    @pytest.mark.parametrize("pkg,minimum", MIN_SAFE.items())
    def test_requirements_pin_at_least_safe_version(self, pkg, minimum):
        text = REQ.read_text(encoding="utf-8")
        m = re.search(rf"^{pkg}==([0-9.]+)$", text, re.M | re.I)
        assert m, f"requirements.txt 必须显式 pin {pkg}"
        assert _parse(m.group(1)) >= minimum, f"{pkg} 需 ≥ {minimum}，当前 {m.group(1)}"

    @pytest.mark.parametrize("pkg,minimum", MIN_SAFE.items())
    def test_installed_version_at_least_safe(self, pkg, minimum):
        try:
            installed = metadata.version(pkg)
        except metadata.PackageNotFoundError:  # pragma: no cover
            pytest.skip(f"{pkg} 未安装")
        assert _parse(installed) >= minimum, f"已安装 {pkg}=={installed} < 安全版本 {minimum}"

    def test_all_requirement_files_share_the_pins(self):
        """四个 requirements 文件不得留下旧的脆弱 pin。"""
        old = ("PyJWT==2.9.0", "pillow==12.2.0", "Pillow==12.2.0",
               "mammoth==1.6.0", "filelock==3.13.1")
        for f in sorted(BACKEND.glob("requirements*.txt")):
            text = f.read_text(encoding="utf-8")
            for token in old:
                assert token not in text, f"{f.name} 仍含旧 pin {token}"


class TestDiskcacheUsesJsonSerialization:
    def test_dashboard_cache_uses_jsondisk(self):
        src = (BACKEND / "app/api/v1/data/data/dashboard.py").read_text(encoding="utf-8")
        assert "diskcache.JSONDisk" in src, "仪表盘缓存必须使用 JSONDisk（禁用 pickle 反序列化）"

    def test_map_cache_uses_jsondisk(self):
        src = (BACKEND / "app/api/v1/map.py").read_text(encoding="utf-8")
        assert "_dc.JSONDisk" in src, "地图距离缓存必须使用 JSONDisk（禁用 pickle 反序列化）"

    def test_jsondisk_roundtrip_and_no_pickle(self, tmp_path):
        diskcache = pytest.importorskip("diskcache")
        cache = diskcache.Cache(str(tmp_path / "c"), size_limit=1024 * 1024,
                                disk=diskcache.JSONDisk)
        payload = {"a": [1, 2.5, "x"], "b": {"c": True}, "d": None}
        cache.set("k", payload, expire=60)
        assert cache.get("k") == payload
        assert type(cache.disk).__name__ == "JSONDisk"
        cache.close()

    def test_non_json_value_is_rejected(self, tmp_path):
        """安全边界：JSONDisk 只能存 JSON 可序列化值 —— 任意对象（pickle 专属）写入即失败，
        即"缓存目录被塞进构造好的 pickle 载荷"这条攻击面被从序列化层切断。"""
        import threading

        diskcache = pytest.importorskip("diskcache")
        cache = diskcache.Cache(str(tmp_path / "c2"), disk=diskcache.JSONDisk)
        with pytest.raises(Exception):
            cache.set("bad", threading.Lock())
        assert cache.get("bad") is None
        cache.close()
