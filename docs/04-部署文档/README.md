# 部署文档 v1.2.0

## 快速链接

| 目标平台 | 架构 | 安装包 | 文档 |
|----------|------|--------|------|
| **国产 Linux** | ARM64 / x86_64 | `.deb` | [国产电脑一键安装指南](02-Linux部署/国产电脑一键安装指南.md) |
| **麒麟 V10** | ARM64 / x86_64 | `.deb` + AppImage | [麒麟V10离线部署方案](02-Linux部署/麒麟V10离线部署完整方案.md) |
| **Windows 10/11** | x86_64 | `.exe` | [Windows 部署指南](01-Windows部署/部署指南.md) |
| **Docker** | 任意 | 镜像 | [Docker 快速开始](03-Docker部署/DOCKER_QUICK_START.md) |
| **Docker E2E** | 任意 | compose | `make test-e2e-docker` (E2E 测试专用配置) |
| **升级/回滚（全平台）** | — | — | [离线升级与回滚指南](OFFLINE_UPGRADE.md) |

## 一键构建 .deb

```bash
# 在 Ubuntu 22.04+ 上
sudo VERSION=1.2.0 ./build-scripts/build-deb-ubuntu.sh

# Docker 交叉编译 ARM64
docker run --rm --platform linux/arm64 \
  -v "$(pwd):/build" -w /build \
  ubuntu:22.04 bash -c "
    apt-get update && apt-get install -y sudo && \
    sudo VERSION=1.2.0 ./build-scripts/build-deb-ubuntu.sh
  "
```

## 一键安装

```bash
sudo dpkg -i assistance-management-system_1.2.0_arm64.deb
# 浏览器访问 http://localhost:8000
```
