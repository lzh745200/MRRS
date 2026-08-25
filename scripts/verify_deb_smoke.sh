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

BIN=$(find root -type f \( -name "assistance-backend*" -o -name "assistance-management-system" \) | head -1)
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
  if [ "$(printf '%s\n2.28\n' "$MAX_GLIBC" | sort -V | head -1)" != "2.28" ]; then
    echo "FAIL: GLIBC $MAX_GLIBC > 2.28，麒麟 V10 无法运行"
    FAIL=1
  fi
else
  echo "WARN: objdump 不可用，跳过 glibc 检查"
fi

echo "=== 结论 ==="
if [ "$FAIL" -eq 0 ]; then
  echo "SMOKE PASS"
else
  echo "SMOKE FAIL"
  exit 1
fi
