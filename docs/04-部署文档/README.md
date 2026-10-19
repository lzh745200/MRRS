# 部署文档 v1.2.0

## 快速链接

| 目标平台 | 架构 | 安装包 | 文档 |
|----------|------|--------|------|
| **国产 Linux** | ARM64 / x86_64 | `.deb` | [国产电脑一键安装指南](02-Linux部署/国产电脑一键安装指南.md) |
| **麒麟 V10** | ARM64 / x86_64 | `.deb` + AppImage | [麒麟V10离线部署方案](02-Linux部署/麒麟V10离线部署完整方案.md) |
| **Windows 10/11** | x86_64 | `.exe` | [Windows 构建与部署指南](01-Windows部署/构建打包指南.md) |
| **Docker** | 任意 | 镜像 | [Docker 快速开始](03-Docker部署/DOCKER_QUICK_START.md) |
| **Docker E2E** | 任意 | compose | `make test-e2e-docker` (E2E 测试专用配置) |
| **升级/回滚（全平台）** | — | — | [离线升级与回滚指南](OFFLINE_UPGRADE.md) |

## 部署前置检查（安全红线，v1.15.7）

> 部署到**多机 / 局域网 / 非回环访问**前先完成本节两项检查；否则现场会出现
> "用户自助注册被拒（403）""只读账号写操作 403"等看似故障的问题。

### 1. PASS_CODE_SECRET 必须全实例一致（多机 / LAN / 非回环）

- **单机离线**（后端绑定 `127.0.0.1`、管理员与用户同一数据库）：可留空，通行码走本机预录入。
- **多机 / 局域网 / 非回环部署**：必须在**所有实例**配置**同一**随机 `PASS_CODE_SECRET`
  （建议 ≥32 位随机字符）。
  - Linux（麒麟/国产系统 DEB）：写入 `/opt/assistance-management-system/config/kylin.env`
    （systemd `EnvironmentFile` 加载），或 systemd unit 的 `Environment=`；
  - Windows 安装版：配置为系统/用户环境变量 `PASS_CODE_SECRET`（Electron 启动后端进程时继承）；
  - 后端可读取的 `.env`（`backend/.env` / 工作目录 `.env`）同样生效。
- 未配置时，来自**非本机回环地址**的自助注册/通行码自验证会被 **fail-closed 拒绝（403）**，
  只能由管理员在用户所在机器本机预录入通行码。
- 密钥不得提交版本库；生产环境建议 `USE_ENCRYPTED_SECRETS=true` 走加密文件。
- 更换密钥会让已签发的 HMAC 通行码全部失效，需重新签发。

### 2. viewer 角色为严格只读

- `viewer`（访客）**只能读取**：所有写操作（POST/PUT/PATCH/DELETE，含直连 API）由服务端返回 **403**；
  前端隐藏按钮只是体验层，不是权限边界。
- 需要录入/审批/导出的业务账号必须使用 `user` 及以上角色；不要给业务操作人员分配
  `viewer` 后又期望其可写。
- 旧角色值由 `normalize_role()` 自动归一：`approval_leader`/`manager` → `admin`，
  `operator` → `user`。

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
