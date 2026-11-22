#!/bin/bash
# Electron DEB 安装后脚本（2026-11-22 新增）。
#
# 为什么需要：electron-builder 默认的 after-install 只跑 update-mime-database 与
# update-desktop-database，**不刷新图标缓存**。麒麟 V10（UKUI）上 .desktop 的
# `Icon=assistance-management-system` 依赖 /usr/share/icons/hicolor 的缓存索引，
# 不刷新就会出现"程序装好了、菜单/桌面图标空白或显示成默认齿轮"。
# 注：standalone DEB（deploy/kylin/DEBIAN/postinst）早已包含这两步，此处补齐 Electron DEB。
set -e

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi

# UKUI / 麒麟的**用户级**图标缓存（尽力而为）：不清的话，已登录用户要注销才更新。
# 只删缓存文件，不动用户其它数据。
for home in /home/*; do
    [ -d "$home/.cache" ] || continue
    rm -f "$home/.cache/icon-cache.kcache" 2>/dev/null || true
done

exit 0
