# 部署文档 v1.18.32

## 快速链接

| 目标平台 | 架构 | 安装包 | 文档 |
|----------|------|--------|------|
| **国产 Linux** | ARM64 / x86_64 | `.deb` | [国产电脑一键安装指南](02-Linux部署/国产电脑一键安装指南.md) |
| **麒麟 V10** | ARM64 / x86_64 | `.deb`（Electron 桌面版 + standalone Web 版） | [麒麟V10离线部署方案](02-Linux部署/麒麟V10离线部署完整方案.md) |
| **Windows 10/11** | x86_64 | `.exe` | [Windows 构建与部署指南](01-Windows部署/构建打包指南.md) |
| **Docker** | 任意 | 镜像 | [Docker 快速开始](03-Docker部署/DOCKER_QUICK_START.md) |
| **Docker E2E** | 任意 | compose | `make test-e2e-docker` (E2E 测试专用配置) |
| **升级/回滚（全平台）** | — | — | [离线升级与回滚指南](OFFLINE_UPGRADE.md) |
| **安装后起不来 / 打包态排障** | — | — | [打包态启动排障与离线包验证](06-打包态启动排障与离线包验证.md)（环境变量清单 / difflib 事故 / 冻结模块自检 / 冒烟命令） |
| **本版发布说明** | — | — | [RELEASE_NOTES-v1.18.32](RELEASE_NOTES-v1.18.32.md)（8 项修复 + 升级必读 + **避坑指南**） |
| **上一版发布说明** | — | — | [RELEASE_NOTES-v1.18.31](RELEASE_NOTES-v1.18.31.md)（瓦片地图概览层 + 打包启动健壮性） |

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

## 本版发布物（v1.18.32，2026-11-01）

GitHub Release [v1.18.32](https://github.com/lzh745200/MRRS/releases/tag/v1.18.32) 产出（Windows x64 + 麒麟 ARM64）：

| 平台 | 产物 | 体积 |
|---|---|---|
| Windows 10/11 x64 | `MRRS-Setup-1.18.32-x64.exe`（NSIS，自包含 Electron + 冻结后端，含 Python 运行时） | 见 Release 资产 |
| Windows（增量更新元数据） | `MRRS-Setup-1.18.32-x64.exe.blockmap`、`latest.yml` | — |
| 麒麟 V10 ARM64 | `MRRS-Setup-1.18.32-arm64.deb`（Electron 桌面版） | 见 Release 资产 |
| 麒麟 V10 ARM64 | `assistance-management-system_1.18.32_arm64.deb`（standalone 纯 Web 版，systemd 托管） | 见 Release 资产 |
| 全部 | `SHA256SUMS-windows-x64.txt`、`SHA256SUMS-electron-deb-arm64.txt`、`SHA256SUMS-standalone-deb-arm64.txt` | 分发前务必 `sha256sum -c` 校验 |

> **离线口径不变**：安装包内置 CPython 运行时（PyInstaller 冻结后端 + Electron 内置 Node），
> 目标机**无需**安装 Python / Node / 依赖包；麒麟包用 `dpkg -i` 后由 systemd 托管，
> Windows 包为 NSIS 一键安装。冻结模块门禁（`scripts/verify_frozen_modules.py`）在两条
> 打包链路都会校验 `difflib` 与全部 `app.*` 模块。

### v1.18.32 升级要点（3 条，现场最常问）

1. **导入后列表看不到数据** → 本版修复归属字段，升级前导入的历史数据仍缺 `organization_id`，
   需要管理员用「系统管理 → 数据修复」或重新导入（超管可见 → 批量编辑补归属）。
2. **普通账号访问 `/sync/status` 返回 403** → 预期行为（运维接口收紧为管理员专属），不是故障。
3. **审计「今日操作数」口径变化** → 现在按**本地零点**统计；升级当天数字可能与历史对不上，
   属口径修正，不是数据丢失。

## 上一版发布物（v1.18.31，2026-10-31）

GitHub Release [v1.18.31](https://github.com/lzh745200/MRRS/releases/tag/v1.18.31) 产出（Windows x64 + 麒麟 ARM64）：

| 平台 | 产物 | 体积 |
|---|---|---|
| Windows 10/11 x64 | `MRRS-Setup-1.18.31-x64.exe`（NSIS，自包含 Electron + 冻结后端） | 283,524,134 B ≈ 270.4 MB |
| Windows（增量更新元数据） | `MRRS-Setup-1.18.31-x64.exe.blockmap`、`latest.yml` | — |
| 麒麟 V10 ARM64 | `MRRS-Setup-1.18.31-arm64.deb`（Electron 桌面版） | 281,990,840 B ≈ 268.9 MB |
| 麒麟 V10 ARM64 | `assistance-management-system_1.18.31_arm64.deb`（standalone 纯 Web 版，systemd 托管） | 105,041,660 B ≈ 100.2 MB |
| 全部 | `SHA256SUMS-windows-x64.txt`、`SHA256SUMS-electron-deb-arm64.txt`、`SHA256SUMS-standalone-deb-arm64.txt` | 分发前务必 `sha256sum -c` 校验 |

> 本版 P0：ARM64 安装包补齐 `difflib`（v1.18.29 起启动即崩），并在四条打包链路接入
> 冻结模块自检。现场升级前请先读
> [打包态启动排障与离线包验证](06-打包态启动排障与离线包验证.md) 的 §2.1。
>
> 发布验证：tag 触发的 `Build Windows Installer (x64)` 与
> `Build Self-Contained ARM64 Debian Package` 均 success。main 的 PR Checks 在
> 2026-10-31 当天多次受 runner 出网故障影响，属 CI 基础设施问题（见 CHANGELOG）。

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
  --build-arg VERSION=1.18.32 \
  -f docker/Dockerfile.kylin-standalone \
  --output type=local,dest=dist/deb .
```

> 历史脚本 `build-scripts/build-deb-ubuntu.sh` 已删除（见
> [国产电脑一键安装指南](02-Linux部署/国产电脑一键安装指南.md) 的说明）。

## 一键安装

```bash
sudo dpkg -i assistance-management-system_1.18.32_arm64.deb
# 浏览器访问 http://localhost:8000
```

## 发布通知模板（派单 / 通知平台可直接粘贴）

### v1.18.32 模板（当前版本）

> 仓库内没有名为「派单」的模块，站内消息中心（`/message`）已在
> [使用指南](../02-用户手册/使用指南.md) 覆盖。若通知渠道是外部 OA / 钉钉 / 企业微信，
> 直接粘贴下面模板即可，无需改代码；如需自动推送，请提供平台 Webhook 与凭据（**待确认**）。

```text
【版本发布】帮扶管理信息系统 v1.18.32（2026-11-01）

一、本版重点（8 项"不报错但结果是错的"缺陷）
1. 导入不再"幽灵台账"：Excel 导入项目/资金/学校会写入归属组织与创建者，
   非超管账号导入后能立刻在自己的列表看到（此前导入成功但一条都看不到）。
2. 安全：批量导出在"账号未绑定组织"时曾可整库导出（已 fail-closed 拒绝）；
   /sync/status 与 /sync/dashboard 收敛为管理员专属（普通账号访问返回 403，属预期）。
3. 时间口径统一按本地时区：审计「今日操作数」不再在北京时间 0–8 点算成昨天；
   同步趋势日期、个人中心「最后登录时间」、90 天未走访预警同步修正。
4. 展示层：资金审批核定金额为 0 时不再被申请额覆盖；政策搜索状态缺失显示"—"
   而非红色「禁用」；同步日志历史按导出/导入正确过滤；登录页步骤文案不再自相矛盾。

二、安装包（GitHub Release 附带 SHA256SUMS，下载后请先核对哈希）
- Windows x64：MRRS-Setup-1.18.32-x64.exe（体积见 Release 资产）
- 麒麟/国产 ARM64（Electron 桌面版）：MRRS-Setup-1.18.32-arm64.deb
- 麒麟/国产 ARM64（standalone Web，自包含无 Electron）：assistance-management-system_1.18.32_arm64.deb

三、升级步骤
1. 备份：系统管理 → 备份与存储 → 创建备份（务必记录备份密码）。
2. 覆盖安装对应架构的包（Windows 直接运行安装程序；Linux `sudo dpkg -i <deb>`）。
3. 启动后确认：登录页可见 1.18.32；GET /api/v1/health 全项 ok；
   用非超管账号导入 1 条项目，列表立即可见。
4. 升级后 30 分钟内不要卸载旧包，便于回滚（见《离线升级与回滚指南》）。

四、常见问题（先看这里，再提单）
- 普通账号打开"数据同步"提示 403：本版已把同步运维接口收敛为管理员专属，属预期。
- 升级前导入的历史数据仍看不到：历史行缺归属组织，需重新导入或由管理员补归属（超管可见）。
- 装完打不开 / 白屏 / 启动即退：见《打包态启动排障与离线包验证》
  （冻结模块自检 verify_frozen_modules.py、环境变量清单、日志位置）。
- 多机/局域网注册被拒 403：所有实例统一配置同一 PASS_CODE_SECRET。
- 导入授权包失败 400：本机未配置 GRANT_PUBKEY（或包未签名），见 README「部署前置检查」第 3 条。

五、反馈
请在派单中附：安装包名 + 架构 + 操作系统版本 + 报错截图 + 日志
（Windows: %LOCALAPPDATA%\bumofu-assistance\data\logs；Linux: /opt/assistance-management-system/data/logs）。
```

### 历史模板：v1.18.31（2026-10-31）

```text
【版本发布】帮扶管理信息系统 v1.18.31（2026-10-31）

一、本版重点
1. P0 修复：ARM64 安装包漏收 difflib，安装后后端启动即崩（v1.18.29 事故，已补构建期冻结模块门禁）。
2. 地图：瓦片包内置 z5–8 全省概览，单包导入即可缩放看全省；新增右侧图例/图注与比例尺。
3. 安全：权限包导入提权、9 类超管端点错配、组织通行码越权、审计日志销毁、校验码 oracle、
   媒体链路（路径逃逸/像素炸弹）、前端锁屏绕过与导入错误 XSS 等 10 项收敛（提交 06a9e994）。

二、安装包（GitHub Release 附带 SHA256SUMS，下载后请先核对哈希）
- Windows x64：MRRS-Setup-1.18.31-x64.exe（283,524,134 B）
- 麒麟/国产 ARM64（Electron 桌面版）：MRRS-Setup-1.18.31-arm64.deb（281,990,840 B）
- 麒麟/国产 ARM64（standalone Web，自包含无 Electron）：assistance-management-system_1.18.31_arm64.deb（105,041,660 B）

三、升级步骤
1. 备份：系统管理 → 备份与存储 → 创建备份（务必记录备份密码）。
2. 覆盖安装对应架构的包（Windows 直接运行安装程序；Linux `sudo dpkg -i <deb>`）。
3. 启动后确认：浏览器/桌面能打开登录页；管理端「版本.json」显示 1.18.31。
4. 升级后 30 分钟内不要卸载旧包，便于回滚（见《离线升级与回滚指南》）。

四、常见问题（先看这里，再提单）
- 装完打不开 / 白屏 / 启动即退：见《打包态启动排障与离线包验证》
  （冻结模块自检 verify_frozen_modules.py、环境变量清单、日志位置）。
- 多机/局域网注册被拒 403：所有实例统一配置同一 PASS_CODE_SECRET。
- 导入授权包失败 400：本机未配置 GRANT_PUBKEY（或包未签名），见 README「部署前置检查」第 3 条。

五、反馈
请在派单中附：安装包名 + 架构 + 操作系统版本 + 报错截图 + 日志
（Windows: %LOCALAPPDATA%\bumofu-assistance\data\logs；Linux: /opt/assistance-management-system/data/logs）。
```
