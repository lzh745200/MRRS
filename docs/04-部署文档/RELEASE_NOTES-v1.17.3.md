# Release Notes — v1.17.3（2026-10-24）

> 供 GitHub Release 正文使用；逐项变更见根目录 `CHANGELOG.md` 的 `[1.17.3]` 段。

## 一、下载与校验

| 安装包 | 适用平台 | 大小 | SHA256 |
|---|---|---|---|
| `MRRS-Setup-1.17.3-x64.exe` | Windows 10/11 x64 | 273.13 MB | `36130151f45e74d38773ee3a1c9275d24057040b93c669ec33b7afc926075e59` |
| `MRRS-Setup-1.17.3-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） | 269.72 MB | `114bd41539905465d502ff4f3505942af82872397be004d20034d1717c56f141` |
| `assistance-management-system_1.17.3_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone） | 101.17 MB | `ff30e8fbac8e090e8e5f70d7f703688c2bb53dbb4f5ded0f1fa266a8ab31c850` |

离线校验（Windows）：

```powershell
Get-FileHash .\MRRS-Setup-1.17.3-x64.exe -Algorithm SHA256
```

## 二、本版修了什么（两处"只在真机出现"的打包问题）

### 1. 打包后端找不到前端 → 桌面白屏（重要）

Electron 用 `http://127.0.0.1:<port>` 加载界面，靠环境变量 `FRONTEND_DIST_PATH` 指路。
PyInstaller 实际布局是：

```
<resources>/backend/assistance-backend/_internal   ← _MEIPASS
<resources>/frontend                              ← 前端产物（与 backend 同级）
```

原候选路径表缺少"自 `_MEIPASS` 上溯三级"这一条。一旦 Electron 侧没传该变量
（手工启动后端排障、升级后环境变量遗漏、麒麟用 systemd 直接跑），
浏览器访问 `/` 返回 **404**，桌面端表现为**白屏**。

修复后：后端会自己按 onedir 布局推导前端目录，显式传参仍最优先（不破坏既有契约）。

### 2. 启动日志误报「关键文件缺失」

原实现对 `app/core/config.py` 等 4 个 `.py` 源文件做存在性检查，
而打包后源码已编译进可执行文件 → 每次启动刷 4 条
`WARNING 文件完整性检查: 关键文件缺失`，让人误以为安装包损坏。

修复后：**冻结运行时跳过源码检查并记录 INFO 说明原因**（防篡改由代码签名 +
安装包 SHA256 承担），开发环境检查逻辑保持原样。

## 三、离线安装包实测（全新空环境）

在**空 `%APPDATA%` / `%LOCALAPPDATA%`** 下直接启动打包后端（等同于新电脑首次安装）：

| 检查 | 结果 |
|---|---|
| 自动建库与目录 | ✅ `data/ data_sync/ uploads/ archives/ cache/ logs/ offline_tiles/` |
| `/health` | ✅ 200，`status=ok`，`migration.at_head=true` |
| 出厂口令登录 | ✅ 200，`must_change_password=true`（首次登录强制改密生效）|
| 访问 `/`（不传 `FRONTEND_DIST_PATH`） | ✅ 200 且含 `id="app"`（修复前 404）|
| 启动日志 | ✅ 不再出现「关键文件缺失」误报 |

## 四、升级前必读（沿用 v1.17.0~1.17.2）

1. **升级前备份数据库**（系统管理 → 备份与存储 → 备份）。
2. 本版含 r36~r41 六个迁移，首启自动迁移到 head（61 个版本，单 head）；升级路径
   v1.16.4(r35) → 当前 经演练验证：122 张表数据完好。
3. 介质导入会做**整包查重**与**来源单位码核对**：重复包/来源不同均返回 409，
   需在弹窗里显式放行（见《介质数据包导入与系统自检操作说明》）。
4. 多机部署 `ENCRYPTION_KEY` 必须全实例一致（自检可查看指纹比对）。

## 五、安装步骤（Windows）

1. 备份数据库
2. 关闭旧版本
3. 运行 `MRRS-Setup-1.17.3-x64.exe`，覆盖安装（保留数据目录）
4. 首次启动自动建库/迁移（约 10~30 秒，勿中断）
5. 用出厂账号 `admin` 登录 → **必须修改密码**
6. 进入 **系统管理 → 系统设置 → 系统自检**，确认 6 项为「正常/提醒」
7. 进入 **组织与单位** 创建本单位组织（编码 = 6 位行政区划代码，如 520000）

## 六、已知限制

- 安装包**不含离线地图瓦片**（`resources/map-tiles`）。需要离线底图的部署，
  请按《离线 OSM 瓦片生产指南》单独生产并拷入安装目录 `resources/map-tiles`。
- 首次装机初始化向导（3 步）未随本版交付；装完机请按上面第 6 步执行系统自检。

## 七、发布门禁

| 项 | 结果 |
|---|---|
| 后端 12 段全量 + 覆盖率 | 100% 门禁通过 |
| 前端全量 + 覆盖率 | 329 文件 / 6,995 用例，100% |
| CI PR Checks | **8/8 success**（run `40076409380` / commit `842b3f2`） |
| 双平台构建 | **Windows x64 success / ARM64 DEB success**（standalone + Electron 均通过） |
