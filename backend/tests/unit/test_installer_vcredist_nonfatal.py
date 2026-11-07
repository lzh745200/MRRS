"""安装器 VC++ 运行库校验的回归：失败不得阻断整个安装。

现场现象：升级安装到 4% 时弹「VC++ Redistributable 前置检查失败
(SHA256 不匹配)」并 Abort。VC++ 只是 Layer 2 双保险，应用自身已由
PyInstaller 捆绑 VCRUNTIME140/MSVCP140；可选组件哈希不符应告警跳过，
而不是让整个安装失败。
"""
from pathlib import Path

HOOK = Path(__file__).resolve().parents[3] / "build-scripts" / "electron-builder-nsis-hook.nsh"


def test_vcredist_hash_failure_is_non_fatal():
    text = HOOK.read_text(encoding="utf-8")
    block = text.split("vcredist_hash_fail:", 1)[1].split("vcredist_done:", 1)[0]
    assert "Abort" not in block, "VC++ 校验失败仍会中止安装"
    assert "MB_ICONEXCLAMATION" in block, "失败必须给出可读告警"
    assert "Goto vcredist_done" in block


def test_nsis_paths_use_single_backslash():
    text = HOOK.read_text(encoding="utf-8")
    # 文件头已说明 NSIS 反斜杠不是转义符；双反斜杠会生成错误路径
    assert "$INSTDIR\\\\" not in text
    assert "$DESKTOP\\\\" not in text
    assert "$PROFILE\\\\" not in text


def test_hash_check_retries_extraction_race():
    text = HOOK.read_text(encoding="utf-8")
    assert "for ($$i = 0; $$i -lt 10; $$i++)" in text
    assert "Start-Sleep -Milliseconds 500" in text
    assert "verify_x64_hash.txt" in text
