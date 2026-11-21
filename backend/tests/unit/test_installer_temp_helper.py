"""安装 TEMP 链路的静态回归：下载目录双击也可用，不依赖仓库 dist 路径。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WIN = ROOT / "scripts" / "windows"


def test_helper_prefers_installer_next_to_itself():
    text = (WIN / "install-mrrs-with-clean-temp.ps1").read_text(encoding="utf-8")
    # Release 用户把 Helper 与 Setup 放同一目录时，必须优先找 PSScriptRoot
    assert "Get-ChildItem -Path $PSScriptRoot -Filter 'MRRS-Setup-*-x64.exe'" in text
    assert "Test-Path -LiteralPath $repoRelease" in text


def test_helper_rejects_writable_but_too_full_temp():
    text = (WIN / "install-mrrs-with-clean-temp.ps1").read_text(encoding="utf-8")
    # “可写”不等于“够空间”：NSIS 需要约 2 倍安装包 + 512MB 做解包缓冲。
    assert "function Get-FreeSpaceMB" in text
    assert "function Test-TempCandidate" in text
    assert "Required free space" in text
    assert "$requiredMB" in text
    assert "insufficient free space" in text


def test_cmd_launcher_delegates_to_helper_for_space_guard():
    text = (WIN / "install-mrrs.cmd").read_text(encoding="utf-8")
    assert "MRRS-Installer-Helper.ps1" in text
    assert '-TempDir "%MRRS_TEMP%"' in text
    assert "start \"\" /wait" in text


def test_nsis_hook_kills_old_process_without_plugin_dependency():
    text = (ROOT / "build-scripts" / "electron-builder-nsis-hook.nsh").read_text(
        encoding="utf-8"
    )
    # customInit 在 InitPluginsDir 之前执行，不能用 nsExec（插件）做 taskkill。
    assert "nsExec::Exec 'taskkill" not in text
    assert text.count('"$SYSDIR\\taskkill.exe" /F /T /IM') >= 3
    assert "Sleep 800" in text
    assert "Sleep 500" in text


def test_cmd_launcher_sets_temp_and_finds_setup():
    text = (WIN / "install-mrrs.cmd").read_text(encoding="utf-8")
    assert 'set "TEMP=%MRRS_TEMP%"' in text
    assert 'set "TMP=%MRRS_TEMP%"' in text
    assert "MRRS-Setup-*-x64.exe" in text
    assert 'start "" /wait "%SETUP%"' in text
