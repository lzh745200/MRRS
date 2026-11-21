"""`scripts/verify_published_release.py` 的回归测试（2026-11-21 发布链路排查后补）。

## 为什么补这组测试

该脚本是"用户到底能不能下到完整包"的唯一自动化证据，但 v1.18.55 首次实战就**误判**：
Windows 作业先发布、ARM64 Electron deb 尚在上传时，`SHA256SUMS-electron-deb-arm64.txt`
先到而它引用的 `.deb` 后到，同一轮里同时产生两条文案不同的告警；旧实现按**问题文案白名单**
判断"是否值得重试"，遇到「清单引用了不存在的资产」就当成不会自愈，于是在 1800s 预算里
只用了 973s 就判失败（24 秒后另一个触发重跑即通过）。

根因是"用文案推断状态"而不是"用状态判断状态"。修复后由 `report["missing"]` 决定是否等待，
这组测试把该判据与竞态场景固定下来。

## 覆盖点
- `expected_assets`：按版本展开 8 个资产；
- `parse_sums`：标准/`*` 前缀/注释/非法行；
- `_should_retry`：资产未齐 + 未超期 → 等；资产齐 / 超期 → 不等；
- 竞态场景（monkeypatch `fetch_release` + `download_metadata`）：清单先到、包后到时
  不重复报「引用了不存在的资产」，且 `missing` 非空、`_should_retry` 为真；
- 哈希不符仍应立刻失败（不可自愈）。
"""

import importlib.util
import pathlib

import pytest

# backend/tests/unit/test_verify_published_release.py → 上溯 3 级才是仓库根
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "verify_published_release.py"
VERSION = "1.18.55"


def _load():
    spec = importlib.util.spec_from_file_location("verify_published_release_mod", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load()


def _asset(name, size=1024, digest="sha256:" + "0" * 64):
    return {"name": name, "size": size, "digest": digest}


class TestExpectedAssets:
    def test_expands_version_into_eight_assets(self, mod):
        names = mod.expected_assets(VERSION)
        assert len(names) == 8
        assert f"MRRS-Setup-{VERSION}-x64.exe" in names
        assert f"MRRS-Setup-{VERSION}-arm64.deb" in names
        assert f"assistance-management-system_{VERSION}_arm64.deb" in names
        assert "latest.yml" in names
        assert sum(n.startswith("SHA256SUMS-") for n in names) == 3

    def test_version_is_substituted_not_hardcoded(self, mod):
        names = mod.expected_assets("9.9.9")
        assert "MRRS-Setup-9.9.9-x64.exe" in names
        assert not any(VERSION in n for n in names)


class TestParseSums:
    def test_standard_two_space_format(self, mod):
        text = "a" * 64 + "  MRRS-Setup-1.0.0-x64.exe\n"
        assert mod.parse_sums(text) == {"MRRS-Setup-1.0.0-x64.exe": "a" * 64}

    def test_binary_marker_is_stripped(self, mod):
        text = "b" * 64 + " *package.deb\n"
        assert mod.parse_sums(text) == {"package.deb": "b" * 64}

    def test_comments_and_garbage_ignored(self, mod):
        text = "\n# 注释\nnot-a-hash  name.txt\n" + "c" * 64 + "  ok.bin\n"
        assert mod.parse_sums(text) == {"ok.bin": "c" * 64}

    def test_empty_text(self, mod):
        assert mod.parse_sums("") == {}


class TestShouldRetry:
    def test_missing_assets_and_budget_left(self, mod):
        assert mod._should_retry({"missing": ["a.deb"]}, deadline=100.0, now=1.0) is True

    def test_no_missing_assets(self, mod):
        assert mod._should_retry({"missing": []}, deadline=100.0, now=1.0) is False

    def test_budget_exhausted(self, mod):
        assert mod._should_retry({"missing": ["a.deb"]}, deadline=10.0, now=10.0) is False

    def test_report_without_missing_key(self, mod):
        assert mod._should_retry({}, deadline=100.0, now=1.0) is False


class TestSumsArrivedBeforeArtifact:
    """v1.18.55 实测竞态：清单先到、它引用的 deb 后到。"""

    @pytest.fixture
    def raced(self, mod, monkeypatch):
        deb = f"MRRS-Setup-{VERSION}-arm64.deb"
        standalone = f"assistance-management-system_{VERSION}_arm64.deb"
        sums_name = "SHA256SUMS-electron-deb-arm64.txt"
        # 资产清单：清单文件已上传，它引用的 deb 还没有
        present = [
            _asset(f"MRRS-Setup-{VERSION}-x64.exe"),
            _asset(f"MRRS-Setup-{VERSION}-x64.exe.blockmap"),
            _asset("latest.yml"),
            _asset("SHA256SUMS-windows-x64.txt"),
            _asset(sums_name),
            _asset(standalone),
            _asset("SHA256SUMS-standalone-deb-arm64.txt"),
        ]
        monkeypatch.setattr(mod, "fetch_release", lambda tag: {
            "tag_name": tag, "draft": False, "prerelease": False, "assets": present,
        })
        yml = f"version: {VERSION}\npath: MRRS-Setup-{VERSION}-x64.exe\nsize: 1024\n"
        sums_text = {
            sums_name: "d" * 64 + "  " + deb + "\n",
            "SHA256SUMS-windows-x64.txt": "0" * 64 + "  MRRS-Setup-" + VERSION + "-x64.exe\n",
            "SHA256SUMS-standalone-deb-arm64.txt": "0" * 64 + "  " + standalone + "\n",
        }

        def fake_download(tag, names, dest):
            out = {}
            for name in names:
                if name == "latest.yml":
                    out[name] = yml
                elif name in sums_text:
                    out[name] = sums_text[name]
            return out

        monkeypatch.setattr(mod, "download_metadata", fake_download)
        return mod, deb, sums_name

    def test_missing_deb_is_reported_once(self, raced):
        mod, deb, _sums = raced
        problems, report = mod.check_once(f"v{VERSION}", VERSION)
        assert "缺少资产" in problems[0]
        # 不该再重复一条「清单引用了不存在的资产」（旧实现的误判来源）
        assert not any("引用了不存在的资产" in p for p in problems), problems
        assert report["missing"] == [deb]

    def test_retry_is_allowed_despite_second_wording(self, raced):
        mod, _deb, _sums = raced
        _problems, report = mod.check_once(f"v{VERSION}", VERSION)
        assert mod._should_retry(report, deadline=1000.0, now=1.0) is True

    def test_digest_mismatch_is_not_retried(self, mod, monkeypatch):
        """哈希不符属于不可自愈：资产齐全时不应继续等待。"""
        exe = f"MRRS-Setup-{VERSION}-x64.exe"
        names = mod.expected_assets(VERSION)
        present = [_asset(n) for n in names]
        monkeypatch.setattr(mod, "fetch_release", lambda tag: {
            "tag_name": tag, "draft": False, "prerelease": False, "assets": present,
        })
        yml = f"version: {VERSION}\npath: {exe}\nsize: 1024\n"
        sums = {n: ("e" * 64 + "  " + exe + "\n") for n in names if n.startswith("SHA256SUMS-")}

        def fake_download(tag, want, dest):
            out = {}
            for name in want:
                out[name] = yml if name == "latest.yml" else sums.get(name, "")
            return out

        monkeypatch.setattr(mod, "download_metadata", fake_download)
        problems, report = mod.check_once(f"v{VERSION}", VERSION)
        assert any("校验和不一致" in p for p in problems), problems
        assert report["missing"] == []
        assert mod._should_retry(report, deadline=1000.0, now=1.0) is False
