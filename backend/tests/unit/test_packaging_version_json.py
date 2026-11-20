"""打包回归：version.json 必须进入 Windows/ARM64 三个 PyInstaller 产物。

背景（2026-11-20）：三个 spec 都漏收 backend/version.json，冻结后端启动时
VersionService 找不到文件，会在 _internal 写入“当天日期 + 泛化描述”的伪版本，
导致 /api/v1/system/version 的 release_date/description 与发布版本脱节。
"""

from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
SPECS = [
    BACKEND / "assistance-backend.spec",
    BACKEND / "backend_linux_arm64.spec",
    BACKEND / "backend_linux_arm64_standalone.spec",
]


def test_all_specs_include_version_json():
    for spec in SPECS:
        text = spec.read_text(encoding="utf-8")
        assert "version.json" in text, f"{spec.name} 未收集 backend/version.json"
