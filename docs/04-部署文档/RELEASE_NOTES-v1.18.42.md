# 帮扶管理信息系统 v1.18.42 发布说明

- 发布日期：2026-11-14
- 适用对象：需要「全新安装后由登录页导入权限包」的单位；以及此前遇到「系统已存在账号，请先登录管理员账号后再导入权限包」的部署。
- 安装包：GitHub Release `v1.18.42`（Windows x64 自签名安装包 + 麒麟/统信 ARM64 deb）

## 一、本版修复

### 登录页首装导入权限包被误拦截

- **现象**：全新安装、从未登录过系统的电脑，在登录页导入权限包时提示
  「系统已存在账号，请先登录管理员账号后再导入权限包」，无法完成离线首装。
- **原因**：启动种子 `_seed_default_admin` 会在空库首次启动时创建出厂管理员 `admin`
  （`must_change_password=True`、从未登录）。权限包导入的匿名放行原判定是「本机 loopback + 系统中没有任何用户」，
  而种子账号已存在，条件永远不成立。
- **修复**：新增 `_is_pristine_first_run`，在下列条件**全部**满足时把系统视为「等价空库」并允许本机匿名导入：
  1. 系统尚未完成初始化（`SystemConfigService.is_initialized()` 为假）；
  2. 用户表只有一个账号；
  3. 该账号是出厂种子账号（用户名 = `DEFAULT_ADMIN_USERNAME` 或工厂默认 `admin`）；
  4. 该账号 `is_superuser=True`、`must_change_password=True`、`last_login IS NULL`（从未使用）。
- **仍然拒绝**：已登录、已改密、存在第二个账号、非种子用户名、非超管、系统已初始化、状态读取异常、非 loopback。
  判定全程 fail-closed，`/import` 与 `/confirm/{file_name}` 共用同一入口。

## 二、验证记录

| 项目 | 结果 |
| --- | --- |
| 新增 `backend/tests/unit/test_permission_package_first_run.py` | 13 例通过（含 8 种 403 分支） |
| `test_permission_package_first_run.py + test_permission_package_sec1.py` | 27 passed |
| 后端全量 12 段 | 15,793 passed，覆盖率 100.00%（48,515 stmts / 0 miss；12,308 branches / 0 partial） |
| 前端全量 | 348 files / 7,530 tests，覆盖率 100% |
| 打包态 E2E | 新库 + 登录页路径（loopback + CSRF）匿名导入 → 越过 403、返回 400（包格式校验） |
| 门禁 | flake8 / type-check / lint / Electron / 三层对齐 / 文档数字 / CHANGELOG / 硬编码色 / 路由鉴权 全部通过 |

## 三、安装与信任

- Windows 安装包为**内网自签名**：`CN=MRRS Internal Code Signing, O=MRRS, C=CN`，
  指纹 `8203900B6DA54201A49BDAF923B2F20D76CA35A1`，有效期至 2031-11-05。
- 未信任该证书的机器会显示「未知发布者」。目标机请由管理员通过组策略或
  `certutil -addstore -f Root MRRS-Internal-CodeSigning.cer` 将证书加入「受信任的根证书颁发机构」；
  证书文件随安装包与仓库 `docs/04-部署文档/01-Windows部署/MRRS-Internal-CodeSigning.cer` 提供。
- 安装器为 perMachine，需要管理员权限；内置后端运行时、前端资源与 VC++ 运行库，离线可直接安装。
- ARM64 独立版 deb（`assistance-management-system`）无外部依赖；Electron 版 deb 依赖系统 Chromium 运行库。

## 四、升级步骤

1. 退出正在运行的旧版本（托盘退出，确认任务管理器无残留进程）。
2. 运行 `MRRS-Setup-1.18.42-x64.exe` 覆盖安装；**不要勾选**「同时删除用户数据」，否则会清空业务库与附件。
3. 启动后按原账号登录；版本号显示 `1.18.42` 即升级完成。
4. 全新机器建议流程：安装 → 直接使用登录页「导入权限包」→ 导入后再用包内管理员账号登录。

## 五、已知边界

- 本修复只覆盖「未使用的出厂种子账号」这一等价空库场景；只要系统产生过真实使用痕迹（改密、登录、第二个账号），
  仍必须由管理员登录后导入，这是 SEC-1 的既定安全口径。
- 自签名证书未进入公共信任链，SmartScreen 仍可能提示「未知发布者」，需按第三节信任证书。
- 权限包本身未签名时依赖 `GRANT_ALLOW_UNSIGNED` 配置；生产建议使用签名包。
