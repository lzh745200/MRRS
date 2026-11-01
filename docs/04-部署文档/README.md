# 部署文档 v1.18.34

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
| **本版发布说明** | — | — | [RELEASE_NOTES-v1.18.34](RELEASE_NOTES-v1.18.34.md)（路线图长期项收口：Electron 45 / 两阶段导入 / 可观测性） |
| **上一版发布说明** | — | — | [RELEASE_NOTES-v1.18.33](RELEASE_NOTES-v1.18.33.md)（审计报告「立即 5 项 + 短期 7 项」落地 + 升级必读） |

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

## 本版发布物（v1.18.34，2026-11-02）

GitHub Release [v1.18.34](https://github.com/lzh745200/MRRS/releases/tag/v1.18.34) 产出（Windows x64 + 麒麟 ARM64）：

| 平台 | 产物 | 体积 / SHA256 |
|---|---|---|
| Windows 10/11 x64 | `MRRS-Setup-1.18.34-x64.exe`（NSIS，自包含 Electron 45 + 冻结后端，含 Python 运行时） | 317,043,050 B ≈ 302.4 MB / `f481dc87…3384ce` |
| Windows（增量更新元数据） | `MRRS-Setup-1.18.34-x64.exe.blockmap`、`latest.yml` | — |
| 麒麟 V10 ARM64 | `MRRS-Setup-1.18.34-arm64.deb`（Electron 桌面版） | 295,550,048 B ≈ 281.9 MB / `9bdb2d08…57941d` |
| 麒麟 V10 ARM64 | `assistance-management-system_1.18.34_arm64.deb`（standalone 纯 Web 版，systemd 托管） | 105,107,032 B ≈ 100.2 MB / `7a97577e…d8564e` |
| 全部 | `SHA256SUMS-windows-x64.txt`、`SHA256SUMS-electron-deb-arm64.txt`、`SHA256SUMS-standalone-deb-arm64.txt` | 分发前务必 `sha256sum -c` 校验 |

> **安装包为什么变大了约 33 MB**：Electron 从 33（Chromium 130）升到 45（Chromium 142 代），
> 新版内核体积更大；这不是把依赖打多了，离线自包含口径未变（目标机仍**无需** Python / Node）。
>
> 发布验证：`v1.18.34` tag 触发的 `Build Windows Installer (x64)`（run 41332134601）与
> `Build Self-Contained ARM64 Debian Package`（run 41332134516）均 success；main 的 PR Checks
> （run 41329183881）9/9 job 全绿；三份 `SHA256SUMS` 与 GitHub API 资产 digest 逐字一致。

### v1.18.34 升级要点（4 条，现场最常问）

1. **浏览器内核换了**：Electron 33 已 EOL 且 Chromium 130 受在野利用 CVE 影响；升级后
   Windows 首次启动如出现 SmartScreen 提示属"未签名"已知限制（安装包签名待证书）。
2. **导入先演练**：数据包「确认导入」现在先弹「将新增 / 覆盖 / 拒绝」摘要，演练失败不会写库。
3. **监控面板多了业务卡片**：业务事件计数与慢请求 TOP5；计数是进程内累计，**服务重启归零**。
4. **后端依赖与行为不变**：本版不含数据库 schema 变更，回滚只需装回 v1.18.33（先备份）。

## 上一版发布物（v1.18.33，2026-11-01）

GitHub Release [v1.18.33](https://github.com/lzh745200/MRRS/releases/tag/v1.18.33) 产出（Windows x64 + 麒麟 ARM64）：

| 平台 | 产物 | 体积 / SHA256 |
|---|---|---|
| Windows 10/11 x64 | `MRRS-Setup-1.18.33-x64.exe`（NSIS，自包含 Electron + 冻结后端，含 Python 运行时） | 283,564,668 B ≈ 270.4 MB / `b47d5851…12e501` |
| Windows（增量更新元数据） | `MRRS-Setup-1.18.33-x64.exe.blockmap`、`latest.yml` | — |
| 麒麟 V10 ARM64 | `MRRS-Setup-1.18.33-arm64.deb`（Electron 桌面版） | 282,094,704 B ≈ 269.0 MB / `4058d2da…d9f39d` |
| 麒麟 V10 ARM64 | `assistance-management-system_1.18.33_arm64.deb`（standalone 纯 Web 版，systemd 托管） | 105,094,284 B ≈ 100.2 MB / `59d67926…4052ac` |
| 全部 | `SHA256SUMS-windows-x64.txt`、`SHA256SUMS-electron-deb-arm64.txt`、`SHA256SUMS-standalone-deb-arm64.txt` | 分发前务必 `sha256sum -c` 校验 |

> **离线口径不变**：安装包内置 CPython 运行时（PyInstaller 冻结后端 + Electron 内置 Node），
> 目标机**无需**安装 Python / Node / 依赖包；麒麟包用 `dpkg -i` 后由 systemd 托管，
> Windows 包为 NSIS 一键安装。冻结模块门禁（`scripts/verify_frozen_modules.py`）在两条
> 打包链路都会校验 `difflib` 与全部 `app.*` 模块。
>
> 发布验证：`v1.18.33` tag 触发的 `Build Windows Installer (x64)`（run 41302341399）与
> `Build Self-Contained ARM64 Debian Package`（run 41302341498）均 success；main 的
> PR Checks（run 41299746190）9/9 job 全绿。三份 `SHA256SUMS` 与 GitHub API 资产 digest 逐字一致。

### v1.18.33 升级要点（4 条，现场最常问）

1. **大批量导入不再"整个系统卡住"**：数据包确认导入此前在异步端点里同步跑完（含最长 120 秒的
   独占写锁），期间连 `/health` 都没响应；现在下放线程池，界面只看到"导入中"，其它页面可继续用。
2. **导出条数被截断会有提示**：单次导出超过上限（1 万行）时，前端会弹「仅导出前 N 条（共 M 条）」，
   并带 `X-Export-*` 响应头；不再静默少行。
3. **决算金额会自动重算**：生成决算后再追加支出、或只改单个字段，`total_remaining` 会重算；
   审批通过时再算一次（已审批的决算仍视为固化档案，不被改写）。
4. **导入的数据不会挂错组织**：数据包换主键时会重写子表外键（项目/经费不再指向旧 id）；
   报表模板导入按组织 + `is_active` 精确匹配村，重名村不再错挂。

## 更早发布物（v1.18.32，2026-11-01）

GitHub Release [v1.18.32](https://github.com/lzh745200/MRRS/releases/tag/v1.18.32) 产出（Windows x64 + 麒麟 ARM64）：

| 平台 | 产物 | 体积 |
|---|---|---|
| Windows 10/11 x64 | `MRRS-Setup-1.18.32-x64.exe`（NSIS，自包含 Electron + 冻结后端） | 283,537,167 B ≈ 270.4 MB |
| 麒麟 V10 ARM64 | `MRRS-Setup-1.18.32-arm64.deb`（Electron 桌面版） | 282,029,866 B ≈ 269.0 MB |
| 麒麟 V10 ARM64 | `assistance-management-system_1.18.32_arm64.deb`（standalone 纯 Web 版） | 105,074,352 B ≈ 100.2 MB |
| 全部 | `SHA256SUMS-*.txt` | 分发前务必校验 |

### v1.18.32 升级要点（3 条，现场最常问）

1. **导入后列表看不到数据** → 本版修复归属字段，升级前导入的历史数据仍缺 `organization_id`，
   需要管理员用「系统管理 → 数据修复」或重新导入（超管可见 → 批量编辑补归属）。
2. **普通账号访问 `/sync/status` 返回 403** → 预期行为（运维接口收紧为管理员专属），不是故障。
3. **审计「今日操作数」口径变化** → 现在按**本地零点**统计；升级当天数字可能与历史对不上，
   属口径修正，不是数据丢失。

## 更早发布物（v1.18.31，2026-10-31）

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
  --build-arg VERSION=1.18.33 \
  -f docker/Dockerfile.kylin-standalone \
  --output type=local,dest=dist/deb .
```

> 历史脚本 `build-scripts/build-deb-ubuntu.sh` 已删除（见
> [国产电脑一键安装指南](02-Linux部署/国产电脑一键安装指南.md) 的说明）。

## 一键安装

```bash
sudo dpkg -i assistance-management-system_1.18.33_arm64.deb
# 浏览器访问 http://localhost:8000
```

## 发布通知模板（派单 / 通知平台可直接粘贴）

### v1.18.34 模板（当前版本）

> 仓库内没有名为「派单」的模块，站内消息中心（`/message`）已在
> [使用指南](../02-用户手册/使用指南.md) 覆盖。若通知渠道是外部 OA / 钉钉 / 企业微信，
> 直接粘贴下面模板即可，无需改代码；如需自动推送，请提供平台 Webhook 与凭据（**待确认**）。

```text
【版本发布】帮扶管理信息系统 v1.18.34（2026-11-02）

一、本版重点（路线图长期项收口）
1. 浏览器内核升级：Electron 33（已 EOL）→ 45，修复 Chromium 130 的在野利用 CVE；
   安装包因此增大约 33 MB，仍为离线自包含（目标机无需 Python/Node）。
2. 数据包导入改为两阶段：先只读演练，弹窗显示「将新增 N 条 / 覆盖 M 条 / 拒绝 K 条」，
   演练失败零写入；确认导入仍是单事务，中途失败整体回滚。
3. 可观测性：监控面板新增业务事件（导入成功/失败、导出、备份、权限包）与慢请求 TOP5；
   计数为进程内累计，服务重启归零。
4. 质量：backend 12 段 15,543 用例全过且行/分支覆盖 100%；前端 348 文件 7,495 用例全过。

二、安装包（GitHub Release 附带 SHA256SUMS，下载后请先核对哈希）
- Windows x64：MRRS-Setup-1.18.34-x64.exe（317,043,050 B）
- 麒麟/国产 ARM64（Electron 桌面版）：MRRS-Setup-1.18.34-arm64.deb（295,550,048 B）
- 麒麟/国产 ARM64（standalone Web，自包含无 Electron）：assistance-management-system_1.18.34_arm64.deb（105,107,032 B）

三、升级步骤
1. 备份：系统管理 → 备份与存储 → 创建备份（务必记录备份密码）。
2. 覆盖安装对应架构的包（Windows 直接运行安装程序；Linux `sudo dpkg -i <deb>`）。
3. 启动后确认：登录页/「关于」显示 1.18.34；GET /api/v1/health 全项 ok；
   数据包列表点一次「演练」应弹出数量摘要；监控面板可见业务事件卡片。
4. 升级后 30 分钟内不要卸载旧包，便于回滚（见《离线升级与回滚指南》）。

四、常见问题（先看这里，再提单）
- 装完打不开 / 白屏 / 启动即退：见《打包态启动排障与离线包验证》
  （冻结模块自检 verify_frozen_modules.py、环境变量清单、日志位置）。
- Windows 首次运行 SmartScreen 提示：安装包未做代码签名（无证书）的已知限制，
  请核对 SHA256 后选择「仍要运行」。
- 监控面板业务计数为 0：本版计数为进程内累计，重启后归零；跨重启请查日志/导出记录。
- 多机/局域网注册被拒 403：所有实例统一配置同一 PASS_CODE_SECRET。
- 导入授权包失败 400：本机未配置 GRANT_PUBKEY（或包未签名），见 README「部署前置检查」第 3 条。
- 写操作被 403 且响应头有 X-Org-Module-Policy：组织模块策略处于 shadow/enforce 下的预期拦截，
  联系超管调整「组织模块策略」。

五、反馈
请在派单中附：安装包名 + 架构 + 操作系统版本 + 报错截图 + 日志
（Windows: %LOCALAPPDATA%\bumofu-assistance\data\logs；Linux: /opt/assistance-management-system/data/logs）。
```

### 历史模板：v1.18.33（2026-11-01）

> 仓库内没有名为「派单」的模块，站内消息中心（`/message`）已在
> [使用指南](../02-用户手册/使用指南.md) 覆盖。若通知渠道是外部 OA / 钉钉 / 企业微信，
> 直接粘贴下面模板即可，无需改代码；如需自动推送，请提供平台 Webhook 与凭据（**待确认**）。

```text
【版本发布】帮扶管理信息系统 v1.18.33（2026-11-01）

一、本版重点（审计报告「立即 5 项 + 短期 7 项」落地）
1. 导入/导出更稳：数据包确认导入不再卡住整个系统（含 120 秒写锁）；导出超上限会提示
   「仅导出前 N 条（共 M 条）」；CSV/Excel 公式注入已净化（= + - @ 开头的单元格加前缀）。
2. 数据更准：主键冲突换 id 后子表外键会重写（项目/经费不再挂错）；决算 total_remaining
   在追加支出、修改字段、审批前都会重算；报表模板导入按组织 + 未删除精确匹配村。
3. 权限更严：机器码管理面（列表/撤销）按组织过滤；审计日志删除/改写收敛为超管；
   备份默认加密并写审计；组织模块策略可执行（默认 shadow，不改变现有行为）。
4. 运维更好查：JSON 日志带 request_id（可与响应头 X-Request-ID 串联）；/system/metrics
   增加业务计数（导入/导出/备份/权限包）；Electron 权限默认拒绝摄像头/麦克风/定位。

二、安装包（GitHub Release 附带 SHA256SUMS，下载后请先核对哈希）
- Windows x64：MRRS-Setup-1.18.33-x64.exe（283,564,668 B）
- 麒麟/国产 ARM64（Electron 桌面版）：MRRS-Setup-1.18.33-arm64.deb（282,094,704 B）
- 麒麟/国产 ARM64（standalone Web，自包含无 Electron）：assistance-management-system_1.18.33_arm64.deb（105,094,284 B）

三、升级步骤
1. 备份：系统管理 → 备份与存储 → 创建备份（务必记录备份密码）。
2. 覆盖安装对应架构的包（Windows 直接运行安装程序；Linux `sudo dpkg -i <deb>`）。
3. 启动后确认：登录页可见 1.18.33；GET /api/v1/health 全项 ok；
   导出一份超过 1 万行的数据，应看到「仅导出前 N 条」提示而不是静默少行。
4. 升级后 30 分钟内不要卸载旧包，便于回滚（见《离线升级与回滚指南》）。

四、常见问题（先看这里，再提单）
- 装完打不开 / 白屏 / 启动即退：见《打包态启动排障与离线包验证》
  （冻结模块自检 verify_frozen_modules.py、环境变量清单、日志位置）。
- 多机/局域网注册被拒 403：所有实例统一配置同一 PASS_CODE_SECRET。
- 导入授权包失败 400：本机未配置 GRANT_PUBKEY（或包未签名），见 README「部署前置检查」第 3 条。
- 写操作被 403 且响应头有 X-Org-Module-Policy：组织模块策略处于 shadow/enforce 下的预期拦截，
  联系超管调整「组织模块策略」。

五、反馈
请在派单中附：安装包名 + 架构 + 操作系统版本 + 报错截图 + 日志
（Windows: %LOCALAPPDATA%\bumofu-assistance\data\logs；Linux: /opt/assistance-management-system/data/logs）。
```

### 历史模板：v1.18.32（2026-11-01）

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
