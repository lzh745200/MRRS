#!/bin/bash
set -e
LATEST=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | grep -o '"tag_name": *"[^"]*"' | head -1 | cut -d'"' -f4)
echo "TAG=$LATEST"
V=${LATEST#v}
mkdir -p /opt/actions-runner && cd /opt/actions-runner
echo "$LATEST" > .tag

dl() {
  local url="https://github.com/actions/runner/releases/download/${LATEST}/$1"
  for i in $(seq 1 12); do
    curl -sL -C - --retry 8 --retry-all-errors -m 600 -o "$1" "$url" || true
    SZ=$(stat -c%s "$1" 2>/dev/null || echo 0)
    echo "try$i $1 bytes=$SZ"
    if [ "$SZ" -gt 150000000 ]; then return 0; fi
    sleep 5
  done
  return 1
}

if [ ! -s runner-linux.tar.gz ] || [ "$(stat -c%s runner-linux.tar.gz)" -lt 150000000 ]; then
  rm -f runner-linux.tar.gz
  dl "actions-runner-linux-x64-${V}.tar.gz"
fi
if [ ! -s /mnt/c/actions-runner/win.zip ] || [ "$(stat -c%s /mnt/c/actions-runner/win.zip 2>/dev/null || echo 0)" -lt 150000000 ]; then
  mkdir -p /mnt/c/actions-runner
  dl "actions-runner-win-x64-${V}.zip"
  cp -f "actions-runner-win-x64-${V}.zip" /mnt/c/actions-runner/win.zip
fi
ls -lh /opt/actions-runner/*.tar.gz /mnt/c/actions-runner/win.zip 2>/dev/null
