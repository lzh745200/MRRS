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

构建已统一收敛到 Docker（`docker/Dockerfile.kylin-standalone` / `Dockerfile.kylin-amd64`），
本机无需安装 Python/Node 工具链：

```bash
# ARM64 麒麟 V10（QEMU 交叉构建，CI 同款）
make build-kylin-arm64

# x86_64 麒麟 / 国产系统 standalone
make build-deb-standalone-amd64

# 或直接用 buildx（等价，产物落 dist/deb/kylin/）
docker buildx build --platform linux/arm64 \
  --build-arg VERSION=1.15.4 \
  -f docker/Dockerfile.kylin-standalone \
  --output type=local,dest=dist/deb .
```

> 历史脚本 `build-scripts/build-deb-ubuntu.sh` 已删除（见
> [国产电脑一键安装指南](02-Linux部署/国产电脑一键安装指南.md) 的说明）。

## 一键安装

```bash
sudo dpkg -i assistance-management-system_1.2.0_arm64.deb
# 浏览器访问 http://localhost:8000
```
