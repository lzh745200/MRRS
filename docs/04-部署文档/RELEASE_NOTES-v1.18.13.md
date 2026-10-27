# Release Notes — v1.18.13（2026-10-27）

> 供 GitHub Release 正文使用；逐项变更见仓库根目录 `CHANGELOG.md` 的 `[1.18.13]` 段。
> 本版是 **界面口径与可读性收口**：把「数据管理」页按实际使用重排为「数据概览」，
> 并清掉一类长期存在的「同页两名」——侧栏一个名字、面包屑与浏览器标题另一个名字。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.13-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.13-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） |
| `assistance-management-system_1.18.13_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone，无 Electron） |

同一 Release 附带 **`SHA256SUMS-*.txt`** 校验文件，以及 Windows 自动更新所需的 `latest.yml` / `.exe.blockmap`。

> **体积与 SHA256 以 Release 资产页为准**：安装包由 GitHub Actions 现场构建，
> PyInstaller / electron-builder 产物含时间戳与压缩差异，**不是逐字节可复现**；
> 正文写死哈希会在重跑构建后失效。

离线校验（Windows）：

```powershell
Get-FileHash .\MRRS-Setup-1.18.13-x64.exe -Algorithm SHA256
# 与 SHA256SUMS-windows-x64.txt 逐字符比对
```

离线校验（麒麟 / 统信）：

```bash
sha256sum -c SHA256SUMS-electron-deb-arm64.txt
sha256sum -c SHA256SUMS-standalone-deb-arm64.txt
```

所有行必须为 `OK`；出现 `FAILED` 表示文件损坏或被篡改，请勿安装。

> **未签名包提示**：证书尚未采购。首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）；
> 涉密/企业环境请先报白名单或加 Defender 排除项。

## 二、本版改了什么

### 1. 「数据管理」页改版为「数据概览」

进入「数据管理」板块看到的不再是一个空壳入口集，而是**一屏可读的现状**：

- **核心指标常驻卡片**：帮扶村总数、本月导入次数、备份数量；
  **导出审计卡片仅管理员可见**——非管理员不再请求 `/system/audit/exports`，
  既不每轮刷新打一个 403，也不会看到一个恒为 0 的假数字。
- **最近流转记录**直接渲染真实记录（导入历史 + 管理员可见的导出审计），
  不再需要「前往…」跳到别的页面才能看到。
- **数据质量**由页签改为**常驻区块**：帮扶村抽样统计（后端 `page_size` 上限 200），
  一眼能看到缺项与异常。
- 子组件仍按原分包策略异步加载，首屏不会变慢。

### 2. 23 处「同页两名」一次性对齐

典型例子：`data-overview` 在侧栏叫「数据概览」，但面包屑与浏览器标签页标题写的是「数据管理」。
本版以 `menus.py`（全站唯一菜单源）为准，把 23 条路由的 `meta.title` 逐个对齐，包括：

「汇报大屏」「综合数据录入」「数据包与批量导入」「报表导出」「报表模板」「政策法规」「帮扶项目」
「帮扶学校」「经费台账」「决算结算」「审批总览」「工作首页」「工作列表」「分析仪表盘」「工作分析」
「用户与组织」「角色管理」「安全审计」「健康检查」「错误上报」「地图瓦片」「机器码管理」「零信任」。

### 3. 新增门禁规则 F（防复发）

`scripts/check_menu_alignment.py` 原有 A~E 规则只管「路径可解析 / menuKey 合法 / 无孤儿 key /
路径不重复 / 板块唯一」，**从不校验文案**，所以上面那 23 处可以长期存在而无人发现。
本版新增 **规则 F：`kind=page` 且带 `path` 的条目，菜单 label 必须等于路由 `meta.title`**，
首次运行即抓出全部 23 处，此后由 CI 自动拦截。

### 4. 测试稳定性与规范修复

- **`policies/Edit.test.ts` 跨用例污染**：该视图 `useFormDraft` 的 600ms 防抖定时器会在
  后续用例执行期间把上一个用例的表单写回共享 `localStorage`，造成「单跑通过、整文件必红」。
  改用 `enableAutoUnmount(afterEach)` 统一卸载（仓库 49 个视图测试同款约定）。
- **`smoke.test.ts` 移除同一视图的 bare import**：遵守 coverage-merge 不变量
  （一个受覆盖率阈值锁定的 `.vue` 只由一个测试文件执行），可挂载性由全量路由表测试保证。
- **`utils/index.test.ts` 删除重复覆盖**该视图的内容。
- **lint 归零**：`policies/Edit.test.ts` 5 处未使用绑定 + 29 处 prettier 缩进修净后才入库。

## 三、验证

- 前端全量 `npm run test:coverage`：**347 文件 / 7,374 用例全过**，`All files 100 | 100 | 100 | 100`；
- `vue-tsc --noEmit` 0 错误；改动文件 `eslint --max-warnings=0` 0 告警；
- 21 道静态门禁全绿（含新增规则 F、四层对齐、Office 格式、全仓损坏扫描、版本一致性、更新日志同步、文档数字）；
- 布局/菜单/路由相关 88 例（面包屑回退、`Menu.vue` 子路由过滤、`router/guards` 文档标题）全过；
- 后端 12 段分段执行 + 覆盖率 100% 门禁、E2E 套件由 CI 在 tag 提交上执行。

## 四、已知限制

- 安装包未签名（见上）。
- 「数据概览」的指标来自真实端点；若某类数据从未产生（如从未导出过），
  对应卡片会显示 0 并附说明，不是加载失败。
