"""安装器 VC++ 运行库回归：构建期钉扎，安装期静默安装、不弹窗、不阻断。

现场现象：安装到 4% 时弹「VC++ Redistributable 前置检查失败
(SHA256 不匹配)」并 Abort。根因是安装期用 PowerShell 对目标文件做哈希，
在中文安装路径/受限 PowerShell/解压暂存时返回 1，被误判为篡改。

现契约：
1. 供应链 SHA256 在构建期由 scripts/verify_vcredist_bundle.py 校验；
2. 安装期只执行 `/install /quiet /norestart`，把退出码写入
   `install-vcredist.log`，不弹 MessageBox、不 Abort；
3. Electron app-local DLL 与 PyInstaller 内置 DLL 双兜底。
"""
from pathlib import Path

HOOK = Path(__file__).resolve().parents[3] / "build-scripts" / "electron-builder-nsis-hook.nsh"
PACKAGE = Path(__file__).resolve().parents[3] / "package.json"


def test_installer_does_not_recheck_hash_or_warn():
    text = HOOK.read_text(encoding="utf-8")
    assert "vcredist_hash_fail" not in text
    assert "Get-FileHash" not in text
    assert "MessageBox MB_ICONEXCLAMATION" not in text
    assert "Abort" not in text
    assert "install-vcredist.log" in text
    assert "/install /quiet /norestart" in text


def test_installer_accepts_already_installed_and_reboot_codes():
    text = HOOK.read_text(encoding="utf-8")
    for code in ("0", "1638", "3010", "1641"):
        assert f'StrCmp $0 "{code}"' in text


def test_nsis_paths_use_single_backslash():
    text = HOOK.read_text(encoding="utf-8")
    assert "$INSTDIR\\\\" not in text
    assert "$DESKTOP\\\\" not in text
    assert "$PROFILE\\\\" not in text


def test_electron_ships_app_local_vc_runtime():
    import json

    data = json.loads(PACKAGE.read_text(encoding="utf-8"))
    files = data["build"]["extraFiles"]
    filters = files[0]["filter"]
    for name in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"):
        assert name in filters


def test_build_time_verifier_exists():
    verifier = Path(__file__).resolve().parents[3] / "scripts" / "verify_vcredist_bundle.py"
    assert verifier.is_file()
    text = verifier.read_text(encoding="utf-8")
    assert "VCREDIST_{arch}_SHA256" in text
    assert "SHA256 不匹配" in text
