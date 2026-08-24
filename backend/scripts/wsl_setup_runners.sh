#!/bin/bash
set -e
cd /opt/actions-runner
if [ ! -d app-linux ]; then
  mkdir -p app-linux && tar -xzf runner-linux.tar.gz -C app-linux
fi

TOKEN=$(cat /mnt/c/actions-runner/.regtok 2>/dev/null | tr -d '\r\n')
URL="https://github.com/lzh745200/MRRS"

cfg() {
  local NAME=$1 DIR=$2
  mkdir -p "$DIR"
  if [ ! -f "$DIR/.runner" ]; then
    cd "$DIR"
    # 解包到共享 app 目录用软链方式复杂；每个实例独立解包更稳（tar 秒级）
    tar -xzf /opt/actions-runner/runner-linux.tar.gz -C "$DIR"
    ./config.sh --unattended --url "$URL" --token "$TOKEN" \
      --name "$NAME" --labels "self-hosted,ubuntu-latest,x64" \
      --work "_work-$NAME" --replace
  fi
}

cfg mrrs-wsl-u1 /opt/actions-runner/r1
cfg mrrs-wsl-u2 /opt/actions-runner/r2
cfg mrrs-wsl-u3 /opt/actions-runner/r3

# 后台启动三个监听进程
for d in r1 r2 r3; do
  cd "/opt/actions-runner/$d"
  setsid nohup ./run.sh > "/opt/actions-runner/$d.out" 2>&1 < /dev/null &
done
sleep 8
for d in r1 r2 r3; do echo "== $d =="; tail -3 "/opt/actions-runner/$d.out"; done
