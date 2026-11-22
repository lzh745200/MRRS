# 帮扶管理信息系统 v1.18.63 发布说明

**发布日期**：2026-11-22  
**版本**：1.18.63  
**主题**：图标二次收口 + 授权包严格验签补漏 + 文档口径校准

## 一、本版修复

### 1. Windows 图标缓存按路径复用旧白纸条目（主因）

Windows 的 iconcache 以路径为键。升级后 exe 图标已换新，Explorer 仍可能复用旧的空白条目；
提权安装进程调用 `ie4uinit -show` 常被拒（0x80070522）或静默无效。

- 安装后脚本把 `resources/app-circle.ico` 复制为 `resources/icon-<时间戳>.ico`，快捷方式图标指向新文件；
  缓存键必然变化，不依赖任何缓存刷新接口。
- 对桌面/开始菜单两个 `.lnk` 逐个发 `SHCNE_UPDATEITEM`，最后再补 `-ClearIconCache` + `-show`（失败不影响主方案）。
- 已装机的机器无需重装：运行 `scripts/windows/fix-trust-and-icon.ps1` 即可修复。

### 2. Linux（麒麟）Electron DEB 装完不刷新图标缓存

electron-builder 默认 after-install 只跑 `update-mime-database` / `update-desktop-database`，
不含 `gtk-update-icon-cache`，UKUI 菜单/桌面解析不到图标。

- 新增 `scripts/linux/after-install.sh` 并接入 `build.deb.afterInstall`；
- 安装后刷新 hicolor 缓存、更新 desktop 数据库，并清理用户级 UKUI 图标缓存。

### 3. 严格验签模式可被自签包绕过（安全）

`apply_package` 原在“有签名、但本机未配置 `GRANT_PUBKEY`”分支**无条件跳过验签**，
即使部署已设 `GRANT_ALLOW_UNSIGNED=false` —— 任何人自签一个包即可绕过“强制验签”。

- 严格模式（`GRANT_ALLOW_UNSIGNED=false`）现直接拒收无法验签的签名包；
- 宽松模式（默认 `true`）维持告警放行，兼容没有密钥基建的离线摆渡；
- 新增回归用例 `test_signed_without_public_key_rejected_in_strict_mode`。

### 4. 文档与实现不一致

- `GRANT_ALLOW_UNSIGNED` 自 v1.18.45 起默认 `true`；此前 README、部署文档、用户手册、
  一键安装指南与 `.env.example` 写成“必须 false / 未配公钥即 400”，现统一为实际行为。
- 补充 `/uploads` 非回环部署边界：单机默认 `127.0.0.1` 可维持现状；`HOST=0.0.0.0` 或反向代理暴露时
  该静态目录无鉴权，建议在代理层加 `auth_request`/签名 URL。
- 前端认证存储注释纠正：Electron 下“记住登录”走 `safeStorage` 加密存储，仅浏览器/无 bridge 环境
  回退 `localStorage`（无行为变化）。

## 二、验证

- 后端：**16,095** 用例通过（12 段独立进程 + 新增回归；0 skipped；语句 **49,740/49,740**、分支 **12,654/12,654**，覆盖率门禁 100%）。
- 前端：**351** 个测试文件 / **7,588** 用例通过；`type-check`、`lint:check` 0 错误。
- Electron 外壳：**23** 用例通过。
- 仓库门禁：**42/42 PASS**（含权限目录、包契约、文档数字、更新日志、迁移、乱码等）。
- 新增 `backend/tests/unit/test_icon_shortcut_chain.py`（4 例）与上述验签回归。

## 三、发布物

- Windows x64：`MRRS-Setup-1.18.63-x64.exe`（NSIS），附 `latest.yml` / `.blockmap`。
- Linux ARM64：`MRRS-Setup-1.18.63-arm64.deb` 与 standalone
  `assistance-management-system_1.18.63_arm64.deb`。
- 校验值与下载地址以 GitHub Release `v1.18.63` 页面为准。

## 四、升级提示

- 升级前备份 `backend/data/rural_revitalization.db` 与上传目录。
- 单机桌面默认仅监听 `127.0.0.1`，本版无需改配置即可升级。
- 使用单位授权包的多机部署：生产建议配置 `GRANT_PUBKEY`；启用严格模式前确认上级已用
  `GRANT_SIGNING_KEY` 签发，否则未签名包会被拒收。
