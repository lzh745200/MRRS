"""`scripts/verify_release_assets.py` 门禁的回归测试（发布链路排查后追加）。

## 为什么要给这个脚本写测试

该脚本的作用是在 Release 上传之后**就地**核对「已发布资产 == 构建产物」，
把历史上「发布后才发现」的三类问题在作业内拦下：资产缺失、size/SHA256 不一致、
Release 正文为空或被覆盖成占位。门禁的价值在于能红，所以每条规则都配负向用例，
再配一个正向用例证明全对时确实放行。

## 覆盖点

- `_expected_assets`：windows / arm64 两套资产清单的版本号展开；
- `_check_artifacts`：资产缺失、size 不一致、SHA256 不一致、digest 缺失、全部一致；
- `_check_latest_yml`：四个字段全对、缺字段、sha512 不符、exe 文件名版本号不符；
- `_check_body`：正文为空、正文不含版本号、draft 标记；
- `_repo_slug`：三种 origin 写法（SSH / HTTPS / ssh://）的解析；
- `main()` 端到端：monkeypatch `_gh_api` 返回假 Release，正反向退出码。
"""

import base64
import hashlib
import importlib.util
import pathlib

import pytest

# backend/tests/unit/test_release_assets_gate.py → 上溯 3 级才是仓库根
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "verify_release_assets.py"


def _load():
    spec = importlib.util.spec_from_file_location("verify_release_assets_mod", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha512_b64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")


def _write(path: pathlib.Path, data: bytes) -> pathlib.Path:
    path.write_bytes(data)
    return path


def _release(assets=None, body="## v1.18.53\n\n产物。", draft=False, prerelease=False):
    return {
        "tag_name": "v1.18.53",
        "draft": draft,
        "prerelease": prerelease,
        "body": body,
        "assets": assets or [],
    }


def _asset(name: str, data: bytes, size: int | None = None):
    return {
        "name": name,
        "size": len(data) if size is None else size,
        "digest": f"sha256:{_sha256(data)}",
    }


class TestExpectedAssets:
    def test_windows_assets_expand_version(self, mod):
        names = mod._expected_assets("windows", "1.18.53")
        assert names == (
            "MRRS-Setup-1.18.53-x64.exe",
            "MRRS-Setup-1.18.53-x64.exe.blockmap",
            "latest.yml",
            "SHA256SUMS-windows-x64.txt",
        )

    def test_arm64_assets_expand_version(self, mod):
        names = mod._expected_assets("arm64", "1.18.53")
        assert "MRRS-Setup-1.18.53-arm64.deb" in names
        assert "assistance-management-system_1.18.53_arm64.deb" in names

    def test_unknown_asset_set_raises(self, mod):
        with pytest.raises(ValueError):
            mod._expected_assets("unknown", "1.0.0")


class TestCheckArtifacts:
    def test_all_matching_passes(self, mod, tmp_path):
        exe = _write(tmp_path / "MRRS-Setup-1.18.53-x64.exe", b"payload")
        release = _release(assets=[_asset(exe.name, exe.read_bytes())])
        assert mod._check_artifacts(release, [exe], "v1.18.53") == []

    def test_missing_asset_flagged(self, mod, tmp_path):
        exe = _write(tmp_path / "MRRS-Setup-1.18.53-x64.exe", b"payload")
        release = _release(assets=[])
        problems = mod._check_artifacts(release, [exe], "v1.18.53")
        assert any("资产缺失" in item for item in problems)

    def test_missing_local_file_flagged(self, mod, tmp_path):
        release = _release(assets=[])
        problems = mod._check_artifacts(release, [tmp_path / "nope.exe"], "v1.18.53")
        assert any("本地文件不存在" in item for item in problems)

    def test_size_mismatch_flagged(self, mod, tmp_path):
        exe = _write(tmp_path / "MRRS-Setup-1.18.53-x64.exe", b"payload")
        release = _release(
            assets=[_asset(exe.name, exe.read_bytes(), size=len(exe.read_bytes()) + 1)]
        )
        problems = mod._check_artifacts(release, [exe], "v1.18.53")
        assert any("大小不一致" in item for item in problems)

    def test_digest_mismatch_flagged(self, mod, tmp_path):
        exe = _write(tmp_path / "MRRS-Setup-1.18.53-x64.exe", b"payload")
        release = _release(
            assets=[{"name": exe.name, "size": exe.stat().st_size, "digest": "sha256:deadbeef"}]
        )
        problems = mod._check_artifacts(release, [exe], "v1.18.53")
        assert any("SHA256 不一致" in item for item in problems)

    def test_missing_digest_flagged(self, mod, tmp_path):
        exe = _write(tmp_path / "MRRS-Setup-1.18.53-x64.exe", b"payload")
        release = _release(assets=[{"name": exe.name, "size": exe.stat().st_size, "digest": ""}])
        problems = mod._check_artifacts(release, [exe], "v1.18.53")
        assert any("缺少 sha256 digest" in item for item in problems)


class TestCheckLatestYml:
    def _make(self, tmp_path, body: str, exe_name: str = "MRRS-Setup-1.18.53-x64.exe"):
        exe = _write(tmp_path / exe_name, b"payload")
        yml = _write(tmp_path / "latest.yml", body.encode("utf-8"))
        return yml, exe

    def test_all_fields_match_passes(self, mod, tmp_path):
        exe_name = "MRRS-Setup-1.18.53-x64.exe"
        exe = _write(tmp_path / exe_name, b"payload")
        yml = tmp_path / "latest.yml"
        yml.write_text(
            "version: 1.18.53\n"
            "files:\n"
            "  - url: {exe}\n"
            "    sha512: {sha}\n"
            "    size: {size}\n"
            "path: {exe}\n"
            "sha512: {sha}\n"
            .format(exe=exe_name, sha=_sha512_b64(b"payload"), size=exe.stat().st_size),
            encoding="utf-8",
        )
        assert mod._check_latest_yml(yml, exe, "1.18.53") == []

    def test_missing_field_flagged(self, mod, tmp_path):
        yml, exe = self._make(tmp_path, "version: 1.18.53\n")
        problems = mod._check_latest_yml(yml, exe, "1.18.53")
        assert any("缺少字段" in item for item in problems)

    def test_sha512_mismatch_flagged(self, mod, tmp_path):
        exe_name = "MRRS-Setup-1.18.53-x64.exe"
        exe = _write(tmp_path / exe_name, b"payload")
        yml = tmp_path / "latest.yml"
        yml.write_text(
            "version: 1.18.53\npath: {e}\nsize: {s}\nsha512: AAAA\n".format(
                e=exe_name, s=exe.stat().st_size
            ),
            encoding="utf-8",
        )
        problems = mod._check_latest_yml(yml, exe, "1.18.53")
        assert any("sha512" in item for item in problems)

    def test_exe_version_mismatch_flagged(self, mod, tmp_path):
        yml, exe = self._make(tmp_path, "", exe_name="MRRS-Setup-1.18.99-x64.exe")
        yml.write_text(
            "version: 1.18.53\npath: {e}\nsize: {s}\nsha512: {sha}\n".format(
                e=exe.name, s=exe.stat().st_size, sha=_sha512_b64(b"payload")
            ),
            encoding="utf-8",
        )
        problems = mod._check_latest_yml(yml, exe, "1.18.53")
        assert any("文件名版本号" in item for item in problems)

    def test_missing_local_files_flagged(self, mod, tmp_path):
        assert mod._check_latest_yml(tmp_path / "a.yml", tmp_path / "b.exe", "1.18.53")
        exe = _write(tmp_path / "MRRS-Setup-1.18.53-x64.exe", b"payload")
        assert mod._check_latest_yml(tmp_path / "a.yml", exe, "1.18.53")


class TestCheckBody:
    def test_empty_body_flagged(self, mod):
        problems = mod._check_body(_release(body="   "), "1.18.53")
        assert any("正文为空" in item for item in problems)

    def test_body_missing_version_flagged(self, mod):
        problems = mod._check_body(_release(body="## 发布说明\n\n无版本号"), "1.18.53")
        assert any("未包含版本号" in item for item in problems)

    def test_draft_flagged(self, mod):
        problems = mod._check_body(_release(draft=True), "1.18.53")
        assert any("draft" in item for item in problems)

    def test_prerelease_only_warns(self, mod, capsys):
        problems = mod._check_body(_release(prerelease=True), "1.18.53")
        assert problems == []
        assert "prerelease" in capsys.readouterr().err

    def test_good_body_passes(self, mod):
        assert mod._check_body(_release(body="## v1.18.53\n\nok"), "1.18.53") == []


class TestRepoSlug:
    def test_ssh_url(self, mod, monkeypatch):
        monkeypatch.setattr(
            mod.subprocess,
            "run",
            lambda *a, **k: type(
                "P", (), {"returncode": 0, "stdout": "git@github.com:owner/repo.git\n"}
            )(),
        )
        assert mod._repo_slug() == "owner/repo"

    def test_https_url(self, mod, monkeypatch):
        monkeypatch.setattr(
            mod.subprocess,
            "run",
            lambda *a, **k: type(
                "P", (), {"returncode": 0, "stdout": "https://github.com/owner/repo.git\n"}
            )(),
        )
        assert mod._repo_slug() == "owner/repo"

    def test_ssh_scheme_url(self, mod, monkeypatch):
        monkeypatch.setattr(
            mod.subprocess,
            "run",
            lambda *a, **k: type(
                "P", (), {"returncode": 0, "stdout": "ssh://git@github.com/owner/repo.git\n"}
            )(),
        )
        assert mod._repo_slug() == "owner/repo"

    def test_bad_remote_raises(self, mod, monkeypatch):
        monkeypatch.setattr(
            mod.subprocess,
            "run",
            lambda *a, **k: type("P", (), {"returncode": 0, "stdout": "https://git.example.com/a/b\n"})(),
        )
        with pytest.raises(RuntimeError):
            mod._repo_slug()


class TestCheckLocalDir:
    def _populate(self, tmp_path, version="1.18.53", exe_name="MRRS-Setup-1.18.53-x64.exe"):
        exe = _write(tmp_path / exe_name, b"payload")
        _write(tmp_path / (exe_name + ".blockmap"), b"blockmap")
        yml = tmp_path / "latest.yml"
        yml.write_text(
            "version: {v}\npath: {e}\nsize: {s}\nsha512: {sha}\n".format(
                v=version, e=exe_name, s=exe.stat().st_size, sha=_sha512_b64(b"payload")
            ),
            encoding="utf-8",
        )
        sums = tmp_path / "SHA256SUMS-windows-x64.txt"
        sums.write_text(f"{_sha256(b'payload')}  {exe_name}\n", encoding="utf-8")
        return exe, yml, sums

    def test_complete_windows_dir_passes(self, mod, tmp_path):
        self._populate(tmp_path)
        assert mod._check_local_dir(tmp_path, "1.18.53", "windows") == []

    def test_missing_expected_asset_flagged(self, mod, tmp_path):
        exe, yml, sums = self._populate(tmp_path)
        (tmp_path / (exe.name + ".blockmap")).unlink()
        problems = mod._check_local_dir(tmp_path, "1.18.53", "windows")
        assert any("blockmap" in item for item in problems)

    def test_latest_yml_mismatch_flagged(self, mod, tmp_path):
        exe, yml, sums = self._populate(tmp_path)
        yml.write_text(
            "version: 1.18.53\npath: {e}\nsize: 1\nsha512: AAAA\n".format(e=exe.name),
            encoding="utf-8",
        )
        problems = mod._check_local_dir(tmp_path, "1.18.53", "windows")
        assert any("size" in item or "sha512" in item for item in problems)

    def test_sums_hash_mismatch_flagged(self, mod, tmp_path):
        exe, yml, sums = self._populate(tmp_path)
        sums.write_text(f"0000  {exe.name}\n", encoding="utf-8")
        problems = mod._check_local_dir(tmp_path, "1.18.53", "windows")
        assert any("SHA256" in item for item in problems)

    def test_sums_missing_entry_flagged(self, mod, tmp_path):
        exe, yml, sums = self._populate(tmp_path)
        sums.write_text("", encoding="utf-8")
        problems = mod._check_local_dir(tmp_path, "1.18.53", "windows")
        assert any("缺少" in item for item in problems)

    def test_nonexistent_dir_flagged(self, mod, tmp_path):
        problems = mod._check_local_dir(tmp_path / "nope", "1.18.53", "windows")
        assert any("目录不存在" in item for item in problems)

    def test_arm64_dir_deb_sums_checked(self, mod, tmp_path):
        deb1 = _write(tmp_path / "MRRS-Setup-1.18.53-arm64.deb", b"one")
        deb2 = _write(tmp_path / "assistance-management-system_1.18.53_arm64.deb", b"two")
        sums_electron = tmp_path / "SHA256SUMS-electron-deb-arm64.txt"
        sums_standalone = tmp_path / "SHA256SUMS-standalone-deb-arm64.txt"
        sums_electron.write_text(f"{_sha256(b'one')}  {deb1.name}\n", encoding="utf-8")
        sums_standalone.write_text(f"{_sha256(b'two')}  {deb2.name}\n", encoding="utf-8")
        assert mod._check_local_dir(tmp_path, "1.18.53", "arm64") == []
        # standalone 清单漏掉自己的 deb → 必须报缺条目（而不是被 electron 清单顶替）
        sums_standalone.write_text("", encoding="utf-8")
        problems = mod._check_local_dir(tmp_path, "1.18.53", "arm64")
        assert any("缺少" in item for item in problems)


class TestMainEndToEnd:
    def _argv(self, tmp_path, exe_name="MRRS-Setup-1.18.53-x64.exe"):
        exe = _write(tmp_path / exe_name, b"payload")
        blockmap = _write(tmp_path / (exe_name + ".blockmap"), b"blockmap")
        yml = tmp_path / "latest.yml"
        yml.write_text(
            "version: 1.18.53\n"
            "path: {e}\nsize: {s}\nsha512: {sha}\n".format(
                e=exe_name, s=exe.stat().st_size, sha=_sha512_b64(b"payload")
            ),
            encoding="utf-8",
        )
        sums = tmp_path / "SHA256SUMS-windows-x64.txt"
        sums.write_text(f"{_sha256(b'payload')}  {exe_name}\n", encoding="utf-8")
        return exe, blockmap, yml, sums

    def _patch_gh(self, mod, monkeypatch, release):
        def fake_api(path):
            if path.endswith("releases/tags/v1.18.53"):
                return release
            raise AssertionError(f"意外调用：{path}")

        monkeypatch.setattr(mod, "_gh_api", fake_api)

    def _release_from_local(self, files):
        """按本地文件真实内容构造「已发布资产」，保证正向用例数据自洽。"""
        return _release(assets=[_asset(path.name, path.read_bytes()) for path in files])

    def _run_main(self, mod, monkeypatch, tmp_path, release, expect_argv_extra=None):
        exe, blockmap, yml, sums = self._argv(tmp_path)
        self._patch_gh(mod, monkeypatch, release)
        argv = [
            "verify_release_assets.py", "--tag", "v1.18.53", "--repo", "owner/repo",
            "--asset-set", "windows",
            "--artifacts", str(exe), str(blockmap), str(yml), str(sums),
            "--latest-yml", str(yml), "--exe", str(exe),
        ]
        monkeypatch.setattr(mod.sys, "argv", argv + (expect_argv_extra or []))
        return mod.main()

    def test_all_good_returns_zero(self, mod, monkeypatch, tmp_path):
        exe, blockmap, yml, sums = self._argv(tmp_path)
        release = self._release_from_local((exe, blockmap, yml, sums))
        assert self._run_main(mod, monkeypatch, tmp_path, release) == 0

    def test_digest_mismatch_returns_one(self, mod, monkeypatch, tmp_path):
        exe, blockmap, yml, sums = self._argv(tmp_path)
        release = self._release_from_local((exe, blockmap, yml, sums))
        release["assets"][0]["digest"] = "sha256:0000"
        assert self._run_main(mod, monkeypatch, tmp_path, release) == 1

    def test_empty_body_returns_one(self, mod, monkeypatch, tmp_path):
        exe, blockmap, yml, sums = self._argv(tmp_path)
        release = self._release_from_local((exe, blockmap, yml, sums))
        release["body"] = ""
        assert self._run_main(mod, monkeypatch, tmp_path, release) == 1

    def test_expected_asset_missing_returns_one(self, mod, monkeypatch, tmp_path):
        exe, blockmap, yml, sums = self._argv(tmp_path)
        release = self._release_from_local((exe, blockmap, yml, sums))
        # 故意少一个 blockmap 资产，验证预期清单完整性检查生效
        release["assets"] = [a for a in release["assets"] if not a["name"].endswith(".blockmap")]
        assert self._run_main(mod, monkeypatch, tmp_path, release) == 1

    def test_release_absent_returns_two(self, mod, monkeypatch, tmp_path, capsys):
        def fake_api(path):
            raise RuntimeError("gh api 失败：not found")

        monkeypatch.setattr(mod, "_gh_api", fake_api)
        monkeypatch.setattr(
            mod.sys, "argv", ["verify_release_assets.py", "--tag", "v1.18.53", "--repo", "owner/repo"]
        )
        assert mod.main() == 2

    def test_dir_mode_passes(self, mod, monkeypatch, tmp_path):
        self._argv(tmp_path)
        monkeypatch.setattr(
            mod.sys,
            "argv",
            [
                "verify_release_assets.py", "--dir", str(tmp_path),
                "--expect-version", "1.18.53", "--asset-set", "windows",
            ],
        )
        assert mod.main() == 0

    def test_dir_mode_missing_expect_version_returns_two(self, mod, monkeypatch, tmp_path):
        self._argv(tmp_path)
        monkeypatch.setattr(
            mod.sys,
            "argv",
            ["verify_release_assets.py", "--dir", str(tmp_path), "--asset-set", "windows"],
        )
        assert mod.main() == 2

    def test_dir_mode_missing_asset_returns_one(self, mod, monkeypatch, tmp_path):
        exe, blockmap, yml, sums = self._argv(tmp_path)
        (tmp_path / (exe.name + ".blockmap")).unlink()
        monkeypatch.setattr(
            mod.sys,
            "argv",
            [
                "verify_release_assets.py", "--dir", str(tmp_path),
                "--expect-version", "1.18.53", "--asset-set", "windows",
            ],
        )
        assert mod.main() == 1
