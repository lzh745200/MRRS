# 部署文档 v1.15.15

## 快速链接

| 目标平台 | 架构 | 安装包 | 文档 |
|----------|------|--------|------|
| **国产 Linux** | ARM64 / x86_64 | `.deb` | [国产电脑一键安装指南](02-Linux部署/国产电脑一键安装指南.md) |
| **麒麟 V10** | ARM64 / x86_64 | `.deb`（Electron 桌面版 + standalone Web 版） | [麒麟V10离线部署方案](02-Linux部署/麒麟V10离线部署完整方案.md) |
| **Windows 10/11** | x86_64 | `.exe` | [Windows 构建与部署指南](01-Windows部署/构建打包指南.md) |
| **Docker** | 任意 | 镜像 | [Docker 快速开始](03-Docker部署/DOCKER_QUICK_START.md) |
| **Docker E2E** | 任意 | compose | `make test-e2e-docker` (E2E 测试专用配置) |
| **升级/回滚（全平台）** | — | — | [离线升级与回滚指南](OFFLINE_UPGRADE.md) |
| **本版发布说明** | — | — | [RELEASE_NOTES-v1.15.15](RELEASE_NOTES-v1.15.15.md)（安装包/SHA256/升级必读） |

## 部署前置检查（安全红线，v1.15.12 起，v1.15.15 复核）

> 部署到**多机 / 局域网 / 非回环访问**前先完成本节 4 项检查；否则现场会出现
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

### 3. R33 单位授权包签名（**导入授权包前必须先配置验签公钥**）

授权包 = 上级单位下发给下级单位的"模块授权矩阵"JSON，Ed25519 签名用于防篡改。
出厂配置下不配置密钥，**导入授权包会直接失败**（带签名包 → 400「本机未配置验签公钥」；
未签名包 → 400「授权包未签名」）。

- **上级（下发方）**：配置 `GRANT_SIGNING_KEY`（32 字节 hex Ed25519 **私钥**）用于签发授权包。
  ⚠️ 私钥必须保密、不得提交版本库、不得下发给下级。未配置时导出的包为未签名包，下级默认拒绝。
- **下级（接收方）**：只配置 `GRANT_PUBKEY`（32 字节 hex **公钥**）用于导入验签。
- `GRANT_ALLOW_UNSIGNED` **永远保持 false**：一旦开启即摧毁"授权包不可篡改"的防篡改设计
  （仅离线演练可临时开启，演练后必须改回）。
- 生成密钥对（在 `backend` 目录执行，输出 hex 私钥/公钥；私钥只留在上级机器）：

  ```bash
  # Windows
  cd backend && .venv\Scripts\python.exe -c "from app.core.grant_signing import generate_keypair as g; k=g(); print('GRANT_SIGNING_KEY='+k[0]); print('GRANT_PUBKEY='+k[1])"
  # Linux / macOS
  cd backend && .venv/bin/python -c "from app.core.grant_signing import generate_keypair as g; k=g(); print('GRANT_SIGNING_KEY='+k[0]); print('GRANT_PUBKEY='+k[1])"
  ```

- 配置位置：Linux（麒麟/国产系统 DEB）写入 `/opt/assistance-management-system/config/kylin.env`
  或 systemd `Environment=`；Windows 安装版配置系统/用户环境变量；后端可读取的 `.env` 同样生效。
- 操作路径：上级「系统管理 → 组织与权限 → 单位授权」配置矩阵并导出签名包 → U 盘/内网摆渡
  → 下级「单位授权 → 导入授权包」。**导入前必须先配置 `GRANT_PUBKEY`**。
- 密钥轮换：旧包验签会全部失败，需上级用新私钥重签、所有下级同步更新公钥。

### 4. R33 写收窄（GRANT_GUARD_MODE）为可选能力

| 模式 | 行为 |
|---|---|
| `off`（默认） | 完全关闭写收窄；仅"菜单裁剪"生效（看不到无权菜单），接口层不额外拦截 |
| `shadow` | 只记日志不拦截，用于上线前收集"将被拦"清单 |
| `enforce` | 越权写请求返回 403（「无该模块的录入权限」） |

- **生产建议**：先 `GRANT_GUARD_MODE=shadow` 观察 1~2 周，确认"将被拦"清单符合预期后再切 `enforce`；
  不要直接把默认值改为 enforce（会把存量权限配置问题一次性暴露成 403）。
- 切换只需改环境变量并重启后端，无需改代码。

## 本版发布物（v1.15.15，2026-10-20）

GitHub Release [v1.15.15](https://github.com/lzh745200/MRRS/releases) 产出（双平台）：

| 平台 | 产物 | 体积 |
|---|---|---|
| Windows 10/11 x64 | `MRRS-Setup-1.15.15-x64.exe`（NSIS，自包含） | 286,035,588 B ≈ 272.8 MB |
| Windows（增量更新元数据） | `MRRS-Setup-1.15.15-x64.exe.blockmap`、`latest.yml` | — |
| 麒麟 V10 ARM64 | `MRRS-Setup-1.15.15-arm64.deb`（Electron 桌面版） | 205,545,106 B ≈ 196 MB |
| 麒麟 V10 ARM64 | `assistance-management-system_1.15.15_arm64.deb`（standalone 纯 Web 版） | 60,786,460 B ≈ 58 MB |
| 全部 | `SHA256SUMS-windows-x64.txt`、`SHA256SUMS-electron-deb-arm64.txt`、`SHA256SUMS-standalone-deb-arm64.txt` | 分发前务必 `sha256sum -c` 校验 |

> 发布验证：PR Checks success（后端 12 段独立进程 + 覆盖率 100%）、Build Windows Installer success、
> Build ARM64 Deb success。升级前必读项见 [RELEASE_NOTES-v1.15.15](RELEASE_NOTES-v1.15.15.md)。

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
  --build-arg VERSION=1.15.15 \
  -f docker/Dockerfile.kylin-standalone \
  --output type=local,dest=dist/deb .
```

> 历史脚本 `build-scripts/build-deb-ubuntu.sh` 已删除（见
> [国产电脑一键安装指南](02-Linux部署/国产电脑一键安装指南.md) 的说明）。

## 一键安装

```bash
sudo dpkg -i assistance-management-system_1.15.15_arm64.deb
# 浏览器访问 http://localhost:8000
```
