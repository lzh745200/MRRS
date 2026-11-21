"""安装 TEMP 链路的静态回归：下载目录双击也可用，不依赖仓库 dist 路径。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WIN = ROOT / "scripts" / "windows"


def test_helper_prefers_installer_next_to_itself():
    text = (WIN / "install-mrrs-with-clean-temp.ps1").read_text(encoding="utf-8")
    # Release 用户把 Helper 与 Setup 放同一目录时，必须优先找 PSScriptRoot
    assert "Get-ChildItem -Path $PSScriptRoot -Filter 'MRRS-Setup-*-x64.exe'" in text
    assert "Test-Path -LiteralPath $repoRelease" in text


def test_cmd_launcher_sets_temp_and_finds_setup():
    text = (WIN / "install-mrrs.cmd").read_text(encoding="utf-8")
    assert 'set "TEMP=%MRRS_TEMP%"' in text
    assert 'set "TMP=%MRRS_TEMP%"' in text
    assert "MRRS-Setup-*-x64.exe" in text
    assert 'start "" /wait "%SETUP%"' in text
