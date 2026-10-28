# Release Notes — v1.18.24（2026-10-28）

> 上一正式发布是 **v1.18.17**，因此本版说明覆盖 **v1.18.18 → v1.18.24** 四轮的全部变更。
> 逐项账本见仓库根目录 `CHANGELOG.md` 的对应版本段。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.24-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.24-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） |
| `assistance-management-system_1.18.24_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone，无 Electron） |

同一 Release 附带 `SHA256SUMS-*.txt`（三个安装包指纹）与 `latest.yml` /
`MRRS-Setup-1.18.24-x64.exe.blockmap`（electron-builder 的 NSIS 产物，**本系统不消费**：
无自动更新逻辑，升级走覆盖安装）。

```powershell
Get-FileHash .\MRRS-Setup-1.18.24-x64.exe -Algorithm SHA256
```

> **未签名包提示**：证书尚未采购，首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）。

## 二、最严重的一条：6 个系统接口全部不可达（v1.18.18）

`app/api/v1/system/__init__.py` 的聚合器已是 `APIRouter(prefix="/system")`，
而 `system.py` 自己**又写了** `prefix="/system"`，实际注册成
`/api/v1/system/system/{info,status,shutdown,restart,environment,version}` ——
正确路径 **全部 404**。这 6 个接口（含**关机/重启**）等于摆设；因为前端取系统信息走别的
途径、Electron 与自动化测试都不调它们，**一直没人发现**。

> **修复时差点放出的雷**：`/system/shutdown`、`/system/restart` 的依赖层只有
> `Depends(get_current_user)`（任意登录用户），真正的管理员校验在**函数体内**。
> 它们此前不可达所以无害，路径一修通就变成"任何登录用户可关机"。
> 已实测确认函数内 `require_admin` 存在（`system.py:235` / `273` / `336`）才动手 ——
> **修"不可达"缺陷前，必须先确认它不可达时掩盖了什么**。

同时清掉 `config_package` 重复注册多出的 4 条 `/api/v1/system/system/config-packages*`，
并新增**路由认证覆盖门禁**：`api_v1_router` 没有全局认证依赖，每个路由必须自己声明认证，
少写一行就是越权入口。门禁用 FastAPI 运行时依赖树递归判定，上线时逐个核查全部
**58 个无认证路由，无真实漏洞**（登录/健康检查/地图瓦片/机器码/初始化/shutdown 的
loopback+内部密钥/备份的函数体内认证，均登记理由）。

## 三、大瓦片包导入超时（v1.18.19）

导入全省包（`guizhou-all_z14.zip` 283.7MB / 64,900 张）时前端报"请求超时，请重试"。
根因：全局 axios `timeout: 30000`（30 秒），而后端解压落盘实测 **62.3 秒**。
现在导入走**专用超时 15 分钟** + 上传进度提示 + 超时专用文案（不再笼统归为网络错误），
并补上了进度回调的空值分支测试（否则前端分支覆盖率破 100% 门槛）。

## 四、构建链路兜底（v1.18.20）

`npm run build` 在部分 Windows 机器上**直接失败**：
`[vite:esbuild-transpile] remove ...\AppData\Local\Temp\esbuild-...: Access is denied.`
—— `%TEMP%` 存在「拒绝删除子项」ACL，esbuild 删自己的临时文件被拒，vite 判整次构建失败。
现在前端构建脚本把 `TEMP/TMP` 指向仓库内临时目录，构建不再依赖系统 `%TEMP%` 权限；
并把该行为纳入 Electron 侧单测守护。

## 五、门禁体系治理（v1.18.24）

- **统一入口 `scripts/run_gates.py`**：29 道门禁的调用方式（cwd、参数、编码）固化成注册表，
  一条命令跑完；交付收口实测 **34 道全 PASS**。背景很实在：一天内三次"门禁自己跑不起来"
  （cwd 错、缺 `--json/--baseline`、GBK 控制台崩），差点被误判成代码红。
- **新增两道棘轮**：`no-print`（生产代码不得用 `print`，桌面端永远看不到输出）
  与 `dist_size`（前端产物体积基线，防膨胀）。
- **技术债棘轮继续下压**：mypy 错误 **1394 → 1385**；`as any` **196 → 172**
  （基础设施层与政策模块清零，修掉一处 `getLevelOptions` 假传参）。
- **端点计数口径写明**：`check_doc_numbers` 统计 `/api` 前缀端点（**845**）；全部 FastAPI
  路由合计 **849**（含 `/health`、`/favicon.ico`、`/version.json`、SPA catch-all）。
  两个数字是**口径差异**，不是删了接口 —— 避免被误读。
- **分段测试执行器加单实例锁**：根治"并发跑全量导致 `.coverage` 被重置 → 覆盖率假红"。

## 六、其它修复

- **`milestoneProgress` 在 `items` 为 `null`/`undefined` 时抛 `TypeError`**（交付收口实测，
  `tests/unit/api/milestones.test.ts` 2 例红）："as any 清零"把信封守卫写成
  `(items as unknown as { items?: T[] }).items ?? []`，只容忍"信封里没有 `items` 键"，
  不容忍响应体本身是 `null`/`undefined`（204 空体、接口降级返回）。改为显式
  `| null | undefined` + 可选链，**不**回退到宽松断言；修复后该文件 13/13 全绿。
- **加密数据包版本报错可读**：原先把 bytes 直接拼进消息（用户看到 `b'9.9'`，
  非法版本字节更是不可见控制符）；现统一渲染为 `不支持的版本: 9.9（本机支持 1.0）`，
  非法字节转义为 `\xNN`，且渲染本身绝不抛错。
- **修掉内建函数当类型注解**：`Optional[any]` / `value: any` 里的 `any` 是内建**函数**而非
  `typing.Any`，注解零约束却静默生效；改为 `Optional[Any]` / `Any`。
- **Python 3.13 兼容**：`rapidocr-onnxruntime==1.4.4` 的元数据是 `requires_python<3.13`，
  加环境标记后 3.13 下不再让整个 `pip install -r requirements.txt` 失败（OCR 走既有 503 降级）。
- **路由注册遗留的过时测试**：`config_package` 移除后，逐子模块 fail-fast 测试仍断言它 →
  `DID NOT RAISE`；已改为按聚合器实际 include 的清单参数化，并新增
  "聚合器不得再 include 它 + 正确路径必须仍在"的防回归用例。

## 七、验证（本地实测，2026-10-28）

- 统一门禁入口 `python scripts/run_gates.py`：**34 道 PASS / 0 FAIL / 0 SKIP**；
- 后端分段执行器（CI 12 段等价）：**12/12 段 PASS，14,896 用例**，覆盖率
  **100.00%（46,243 语句 / 11,560 分支，Miss 0 / BrPart 0）**；
- 前端 vitest：**347 个 `.test.ts` / 7,384 用例，0 失败**（其中 `tests/` 下 **344** 个用例文件，
  与 `check_doc_numbers` 口径一致）；flake8 / vue-tsc / eslint 见 CI 同名作业；
- 路由 **849** 条（`/api` 前缀 **845**，口径见 `CLAUDE.md`）；
- CI（tag 提交）：后端 12 段 + 覆盖率门禁、前端、E2E、静态分析、安全、升级演练、
  Windows 冒烟、三层对齐由 `v1.18.24` 标签触发的构建工作流执行，结论以
  GitHub Actions 的该 tag 运行记录为准（本文件不预设结论）。

## 八、升级注意

- **行为变化**：`/api/v1/system/{info,status,environment,version}` 现在真的可用
  （此前 404）；关机/重启仍**仅超级管理员**可执行（函数内校验已验证）；
- **大瓦片包导入**现在允许更长时间（最长 15 分钟）并有进度提示，请勿中途关闭窗口；
- 无数据迁移；升级方式不变：下载对应平台安装包 → 覆盖安装，数据库与上传目录不受影响，
  详见 `docs/04-部署文档/OFFLINE_UPGRADE.md`。
