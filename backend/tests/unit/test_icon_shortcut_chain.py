"""图标链路静态回归（2026-11-22）。

现场「安装后图标仍然白纸」的复盘结论：
- 图标**资源**没问题（exe .rsrc 7 档齐全、ico 混合编码正确）；
- 问题在**外壳缓存按路径记账** + **Linux deb 装完不刷图标缓存**。

本文件把三处修复钉死，防止被"顺手简化"回去：
1. Windows 安装后脚本：图标复制成 ``icon-<时间戳>.ico``（缓存键必变）并逐项 UPDATEITEM；
2. 现场修复脚本具备同样能力；
3. Electron DEB 配置了 afterInstall，且脚本里真的有 gtk-update-icon-cache；
4. ico 仍是「小尺寸 BMP + 256 PNG」，不是全 PNG。
"""

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WIN = ROOT / "scripts" / "windows"
ICO = ROOT / "resources" / "icons" / "app-circle.ico"


def test_post_install_uses_timestamped_icon():
    text = (WIN / "post-install.ps1").read_text(encoding="utf-8-sig")
    # 缓存键必变：复制成带时间戳的新文件名
    assert 'icon-$stamp.ico' in text
    assert 'Copy-Item -LiteralPath $icoSrc -Destination $icoDst -Force' in text
    # 逐项通知（ASSOCCHANGED 不会清单项缓存）
    assert "SHCNE_UPDATEITEM" in text
    assert "0x00002000" in text
    # 清缓存（Win10 1703+），失败忽略
    assert "-ClearIconCache" in text


def test_field_repair_script_matches_installer_behaviour():
    text = (WIN / "fix-trust-and-icon.ps1").read_text(encoding="utf-8-sig")
    assert 'icon-$stamp.ico' in text
    assert "0x00002000" in text
    assert "-ClearIconCache" in text


def test_electron_deb_wires_after_install():
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    deb = pkg["build"]["deb"]
    assert deb.get("afterInstall") == "scripts/linux/after-install.sh"
    script = ROOT / deb["afterInstall"]
    assert script.exists(), "afterInstall 指向的脚本不存在，deb 构建会失败"
    body = script.read_text(encoding="utf-8")
    # electron-builder 默认模板不含这一步，麒麟上会导致菜单/桌面图标空白
    assert "gtk-update-icon-cache" in body
    assert "update-desktop-database" in body


def test_ico_keeps_bmp_small_sizes_and_png_256():
    b = ICO.read_bytes()
    count = struct.unpack_from("<H", b, 4)[0]
    kinds = {}
    for i in range(count):
        w = b[6 + i * 16] or 256
        off = struct.unpack_from("<I", b, 6 + i * 16 + 12)[0]
        kinds[w] = "PNG" if b[off : off + 8] == b"\x89PNG\r\n\x1a\n" else "BMP"
    assert kinds.get(256) == "PNG"
    assert all(kinds[w] == "BMP" for w in kinds if w < 256), kinds
    assert 16 in kinds and 48 in kinds
