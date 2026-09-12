#!/usr/bin/env bash
# DEB 冒烟验证：结构完整性 + 架构正确性 + glibc 兼容上限 (Phase H)
# 用法: ./scripts/verify_deb_smoke.sh <path-to.deb>
set -euo pipefail

DEB="$1"
FAIL=0

echo "=== 1. dpkg-deb 元数据 ==="
dpkg-deb --info "$DEB" | head -20 || { echo "FAIL: dpkg-deb 无法解析"; exit 1; }

echo "=== 2. ar 归像成员 ==="
MEMBERS=$(ar t "$DEB")
echo "$MEMBERS"
for need in debian-binary control.tar data.tar; do
  echo "$MEMBERS" | grep -q "^$need" || { echo "FAIL: 缺少 $need"; FAIL=1; }
done

echo "=== 3. 解包并校验主二进制 ==="
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cd "$TMP"
ar x "$OLDPWD/$DEB" 2>/dev/null || ar x "$DEB"
mkdir -p root
tar xf data.tar.* -C root 2>/dev/null || tar xf data.tar.zst -C root

BIN=$(find root -type f \( -name "assistance-backend*" -o -name "assistance-management-backend" -o -name "assistance-management-system" \) | head -1)
if [ -z "$BIN" ]; then
  echo "FAIL: 未找到后端二进制"
  exit 1
fi
file "$BIN"

echo "--- 架构检查（必须 aarch64）---"
file "$BIN" | grep -q "ARM aarch64" || { echo "FAIL: 非 ARM64 二进制"; FAIL=1; }

echo "--- glibc 符号版本上限（Kylin V10 = 2.28，不得超过）---"
if command -v objdump >/dev/null; then
  MAX_GLIBC=$(objdump -T "$BIN" | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -1 | cut -d_ -f2)
  echo "max GLIBC required: $MAX_GLIBC"
  HIGHEST=$(printf '%s\n2.28\n' "$MAX_GLIBC" | sort -V | tail -1)
  if [ "$HIGHEST" != "2.28" ]; then
    echo "FAIL: GLIBC $MAX_GLIBC > 2.28，麒麟 V10 无法运行"
    FAIL=1
  else
    echo "glibc 兼容性 OK（≤2.28）"
  fi
else
  echo "WARN: objdump 不可用，跳过 glibc 检查"
fi

echo "=== 4. 桌面集成载荷（开始菜单图标 + .desktop 必须在包内）==="
# 根因门禁（2026-09-10）：历史上 Electron DEB 无 hicolor 图标、菜单项 Icon=
# 无法解析且从不创建桌面快捷方式；standalone 缺载荷时 postinst 曾静默跳过。
# 两类缺陷都在出包前用载荷断言拦截，防止静默出厂。
if [ -f "root/usr/share/pixmaps/assistance-management-system.png" ]; then
  echo "pixmaps 图标 OK"
else
  echo "FAIL: 缺少 /usr/share/pixmaps/assistance-management-system.png"
  FAIL=1
fi

HC=$(find root/usr/share/icons/hicolor -type f -name 'assistance-management-system.png' 2>/dev/null | wc -l)
if [ "$HC" -ge 1 ]; then
  echo "hicolor 图标 OK（${HC} 个尺寸）"
else
  echo "FAIL: hicolor 主题图标缺失（菜单项 Icon= 将无法解析）"
  FAIL=1
fi

DT=$(find root \( -path '*/usr/share/applications/*.desktop' -o -path '*/opt/*/desktop/*.desktop' \) 2>/dev/null | wc -l)
if [ "$DT" -ge 1 ]; then
  echo "应用入口 .desktop OK（${DT} 个）"
else
  echo "FAIL: 载荷中无任何 .desktop（开始菜单/桌面快捷方式将缺失）"
  FAIL=1
fi

# 维护脚本行尾门禁（CRLF 会让 postinst 无法执行 → 桌面集成全部失效）。
# 注意：只检查 control 归档里的 DEBIAN 文本脚本——对整个载荷 grep 会
# 误报二进制文件（PNG 内天然含 \r 字节）。
mkdir -p ctrl
tar xf control.tar.* -C ctrl 2>/dev/null || tar xf control.tar.zst -C ctrl --zstd 2>/dev/null || true
if [ -d ctrl/DEBIAN ]; then
  if grep -rl $'\r' ctrl/DEBIAN >/dev/null 2>&1; then
    CR_FILES=$(grep -rl $'\r' ctrl/DEBIAN | head -5 | tr '\n' ' ')
    echo "FAIL: DEBIAN 维护脚本含 CRLF: ${CR_FILES}"
    FAIL=1
  else
    echo "维护脚本 LF 行尾 OK"
  fi
else
  echo "WARN: control 归档解包失败，跳过 CRLF 检查"
fi

echo "=== 结论 ==="
if [ "$FAIL" -eq 0 ]; then
  echo "SMOKE PASS"
else
  echo "SMOKE FAIL"
  exit 1
fi
