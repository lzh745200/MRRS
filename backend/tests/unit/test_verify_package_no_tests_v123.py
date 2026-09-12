# -*- coding: utf-8 -*-
"""`scripts/verify_package_no_tests.py --listing` 的回归（v1.12.3 出包门禁）。

背景：CI 的 Windows 出包步骤原本用内联正则
`(^|\\s|/|\\\\)(tests?/|conftest\\.py|pytest|test_results)` 抽查安装包内容。
该正则**没有厂商豁免表**，而 PyInstaller 产物里 prophet/cmdstan 会带入
`stan/lib/stan_math/lib/tbb_2020.3/src/test/*.cpp`（本地实测 283 项）→
每一次 Windows 出包都会被判"安装包内发现测试内容，禁止发布"而失败。

修复：规则收口到本脚本 `--listing` 模式（与文件树扫描同一实现 + 同一豁免表）。
本文件同时锁死"厂商 tests 放行 / 本项目 tests 拦截"两侧行为，防止有人
再把规则改回重复实现或删掉豁免。
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_package_no_tests.py"

_spec = importlib.util.spec_from_file_location("verify_package_no_tests", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

# 真实 7z `l` 输出形状（表头 + 明细 + 汇总）
_LISTING_HEADER = """\
7-Zip 23.01 (x64) : Copyright (c) 1999-2023 Igor Pavlov : 2023-06-20

Scanning the drive for archives:
1 file, 237186457 bytes (227 MiB)

Listing archive: MRRS-Setup-1.12.3-x64.exe

--
Path = MRRS-Setup-1.12.3-x64.exe
Type = Nsis
Physical Size = 237186457

----------
"""

_VENDOR_MEMBER = (
    "resources/backend/assistance-backend/_internal/prophet/stan_model/cmdstan-2.37.0/"
    "stan/lib/stan_math/lib/tbb_2020.3/src/test/harness.h"
)
_PROJECT_TEST_DIR_MEMBER = (
    "resources/backend/assistance-backend/_internal/app/tests/test_login.py"
)
_PROJECT_TEST_FILE_MEMBER = (
    "resources/backend/assistance-backend/_internal/app/api/conftest.py"
)


def _line(member: str) -> str:
    return f"2026-09-12 10:00:00 ....A         1234         567  {member}"


class TestParseArchiveListing:
    def test_extracts_members_and_skips_noise(self):
        text = _LISTING_HEADER + _line(_VENDOR_MEMBER) + "\n----------\n"
        members = mod.parse_archive_listing(text)
        assert members == [_VENDOR_MEMBER]

    def test_ignores_lines_without_path_separator(self):
        text = _LISTING_HEADER + "2026-09-12 10:00:00 ....A  1  1  README\n"
        assert mod.parse_archive_listing(text) == []


class TestListingRules:
    def test_vendor_tests_are_exempt(self):
        """厂商自带 tests 不得阻断出包（本地实测 283 项，曾误拦 Windows 构建）。"""
        text = _line(_VENDOR_MEMBER) + "\n"
        assert mod.scan_listing_text(text) == []

    def test_project_tests_dir_is_flagged(self):
        text = _line(_VENDOR_MEMBER) + "\n" + _line(_PROJECT_TEST_DIR_MEMBER) + "\n"
        violations = mod.scan_listing_text(text)
        assert len(violations) == 1
        assert "app/tests/test_login.py" in violations[0]

    def test_project_test_file_is_flagged(self):
        text = _line(_PROJECT_TEST_FILE_MEMBER) + "\n"
        violations = mod.scan_listing_text(text)
        assert len(violations) == 1
        assert "conftest.py" in violations[0]

    def test_vendor_path_would_trip_naive_regex(self):
        """记录回归动因：朴素正则（旧 CI 实现）确实会命中厂商 tests。"""
        import re

        naive = re.compile(r"(^|\s|/|\\)(tests?/|conftest\.py|pytest|test_results)")
        assert naive.search("/" + _VENDOR_MEMBER) is not None
        assert mod.scan_listing_text(_line(_VENDOR_MEMBER)) == []


class TestListingCli:
    def test_cli_passes_on_vendor_only(self, tmp_path, monkeypatch, capsys):
        listing = tmp_path / "listing.txt"
        listing.write_text(_line(_VENDOR_MEMBER) + "\n", encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["verify_package_no_tests.py", "--listing", str(listing)])
        mod.main()
        assert "OK" in capsys.readouterr().out

    def test_cli_fails_on_project_tests(self, tmp_path, monkeypatch):
        listing = tmp_path / "listing.txt"
        listing.write_text(_line(_PROJECT_TEST_DIR_MEMBER) + "\n", encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["verify_package_no_tests.py", "--listing", str(listing)])
        with pytest.raises(SystemExit) as exc:
            mod.main()
        assert exc.value.code == 1

    def test_cli_missing_listing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "sys.argv",
            ["verify_package_no_tests.py", "--listing", str(tmp_path / "nope.txt")],
        )
        with pytest.raises(SystemExit) as exc:
            mod.main()
        assert exc.value.code == 2


class TestWindowsCiEncoding:
    """CI 编码回归：门禁脚本在 cp1252 控制台下必须仍能跑完（v1.12.3 事故）。

    windows-2022（en-US）上 Python 对管道的 stdout 编码是 cp1252，脚本输出中文
    会在第一个 print 抛 UnicodeEncodeError → exit 1，把一次**干净**的构建判成
    "安装包含测试内容"。此处以子进程 + PYTHONIOENCODING=cp1252 复现该环境，
    锁定"脚本自身强制 UTF-8"的修复。
    """

    def _run(self, env_encoding: str, *args):
        import os
        import subprocess
        import sys as _sys

        env = dict(os.environ)
        env.pop("PYTHONUTF8", None)          # 关掉本机可能存在的 UTF-8 模式
        env["PYTHONIOENCODING"] = env_encoding
        return subprocess.run(
            [_sys.executable, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(ROOT),
        )

    def test_survives_cp1252_console(self, tmp_path):
        listing = tmp_path / "listing.txt"
        listing.write_text(_line(_VENDOR_MEMBER) + "\n", encoding="utf-8")
        result = self._run("cp1252", "--listing", str(listing))
        assert "UnicodeEncodeError" not in result.stderr, result.stderr
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "OK" in result.stdout

    def test_cp1252_failure_still_reports_violation(self, tmp_path):
        """编码兜底不得把"真违规"吞掉：违规时仍需 exit 1 且打印 ::error:: 注解。"""
        listing = tmp_path / "listing.txt"
        listing.write_text(_line(_PROJECT_TEST_DIR_MEMBER) + "\n", encoding="utf-8")
        result = self._run("cp1252", "--listing", str(listing))
        assert result.returncode == 1
        assert "::error::" in result.stdout
