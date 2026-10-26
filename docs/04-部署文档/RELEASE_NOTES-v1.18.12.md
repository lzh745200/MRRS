# Release Notes — v1.18.12（2026-10-26）

> 供 GitHub Release 正文使用；逐项变更见仓库根目录 `CHANGELOG.md` 的 `[1.18.10]`、`[1.18.11]`、`[1.18.12]` 三段。
> 上一版发布是 **v1.18.9**，因此本版一次性包含 1.18.10 / 1.18.11 / 1.18.12 三代改动：
> **WPS 办公格式兼容** → **瓦片底图常显村/校名称 + 学校 POI** → **贵州 z14 高清预渲染**。

## 一、下载与校验

| 安装包 | 适用平台 |
|---|---|
| `MRRS-Setup-1.18.12-x64.exe` | Windows 10/11 x64（NSIS 安装包，含全部运行时） |
| `MRRS-Setup-1.18.12-arm64.deb` | 麒麟 V10 / 统信 ARM64（Electron） |
| `assistance-management-system_1.18.12_arm64.deb` | 麒麟 V10 / 统信 ARM64（standalone，无 Electron） |

同一 Release 附带 **`SHA256SUMS-*.txt`** 校验文件，以及 Windows 自动更新所需的 `latest.yml` / `.exe.blockmap`。

> **体积与 SHA256 以 Release 资产页为准**：安装包由 GitHub Actions 现场构建，
> PyInstaller / electron-builder 产物含时间戳与压缩差异，**不是逐字节可复现**；
> 正文写死哈希会在重跑构建后失效。请以资产页的 `SHA256SUMS-*.txt` 为准。

离线校验（Windows）：

```powershell
Get-FileHash .\MRRS-Setup-1.18.12-x64.exe -Algorithm SHA256
# 与 SHA256SUMS-windows-x64.txt 逐字符比对
```

离线校验（麒麟 / 统信）：

```bash
sha256sum -c SHA256SUMS-electron-deb-arm64.txt
sha256sum -c SHA256SUMS-standalone-deb-arm64.txt
```

所有行必须为 `OK`；出现 `FAILED` 表示文件损坏或被篡改，请勿安装。

> **未签名包提示**：证书尚未采购。首次运行会触发 SmartScreen（「更多信息」→「仍要运行」）；
> 涉密/企业环境请先报白名单或加 Defender 排除项，不要误判为卡死。

## 二、本版改了什么

### 1. WPS 办公格式兼容（1.18.10）

政务现场主流是 WPS，本版把「只在标准格式上成立」的缺口补齐：

- **`.xls` / WPS `.et` 现在真的能导入**：新增统一读取层 `app/services/office_reader.py`，
  按**容器魔数**（zip → openpyxl，OLE2 → xlrd）选解析器，而不是只看扩展名；
  此前多个端点文案承诺支持 `.xls`，实际全走 openpyxl，用户按 WPS「97-2003 格式」导出后**必然失败**。
- **格式白名单单一事实源** `app/core/office_formats.py`：可解析表格集合、WPS 原生集合、
  附件/导出白名单、WPS 另存为指引文案全在这里，禁止各处硬编码扩展名。
- **附件可上传 `.et/.wps/.dps`**（仅存储）；导入时若格式不可解析，给「请另存为 .docx/.pptx」的明确提示，不再抛裸异常。
- **新增机器门禁** `scripts/check_office_formats.py` 并接入 CI：导入禁止直连 `openpyxl.load_workbook`、
  白名单禁止硬编码 `.xlsx/.xls`、导出扩展名必须在白名单内、CSV 必须带 UTF-8 BOM（否则 WPS/Excel 中文乱码）。

### 2. 瓦片底图常显村/校名称 + 学校 POI（1.18.11）

- **底图直接显示名称**：`zoom >= 12` 常显帮扶村名、`zoom >= 13` 常显学校名（`zoom < 12` 仍仅悬停）；
  文本严格取系统库里的名称，防遮挡用像素格贪心（学校优先 → 距视野中心近优先），单次上限 120 条，
  不拦截拖拽，卸载时解绑监听。
- **OSM 提取新增 `pois` 图层**（schema v2→v3）：学校/幼儿园/高校节点与要素质心，贵州实测 POI 682 处。
- **贵州 z13 全省瓦片包**：16,422 张 / 约 95MB，配合导入与校验流程。

### 3. 贵州 z14 高清预渲染（1.18.12）

- **z14 全省包** `guizhou-all_z14.zip`：64,900 张 / **283.7MB**（约 8.6 m/像素，可看清街区与道路），
  低于 512MB 导入上限，可一次导入。
- **9 个市州分包** `guizhou-<市州>_z14.zip`（21.5~63.8MB，合计 389.2MB）：按市州边界打散，
  现场可只导本单位辖区；每包 MANIFEST 写 region/zoom/tileCount/license。
- **可与内置 z5–12 及 z13 包叠加**（同名覆盖）：同时导入后 5..14 级连续，不会出现空白级。
- 9 个市州包逐个 `import_tiles` + `verify_tiles`：**9/9 通过**；全省包与内置合并后 70,523 张。

### 4. 前后端对齐与门禁补强（本版顺带修复）

- **新增组织缺「组织编码」输入**：后端要求 6 位行政区划代码，前端表单却没有该输入项，
  用户点提交只能收到 422。已补字段（必填 + `^\d{6}$` 校验 + 省份/市州/县市编码规则提示，编辑态只读），
  并修掉同源的 3 处类型漂移（`DataReportCreate` 缺 `report_type`、`SupportedVillageCreate`、
  `ReportSubscriptionCreate`）。
- **三层对齐门禁扩为四层**：新增 **D 轴「请求体必填性」** —— 同名且全局唯一的 `*Create`/`*Update`
  契约，前后端必填字段必须一致，三个方向都报，从此"表单少字段"这类缺陷由 CI 自动拦截。
- **仓库卫生**：清理根目录 18 个 `pip` 解包临时目录（6.42MB）、修掉 `.gitignore` 里的 GBK 双编、
  新增全仓损坏扫描门禁（mojibake / NUL / 非 UTF-8）。

## 三、已知限制

- **z14 可见路网/水系/村名/学校注记，没有建筑轮廓级细节**：OSM 贵州建筑仅 20,393 处、POI 2,261。
- **城市名/学校名为「尽量显示」而非全量**：常显标签只显示 `latitude/longitude` 非空的记录；
  缺坐标的后端会按区县估算并带 `isEstimated` 标记，部署前建议核查村/校坐标完整率。
- **z14 全省包 283.7MB** 已接近导入体验上限，现场建议用 9 个市州分包按需导入。
- 安装包未签名（见上）。

## 四、验证口径

- 后端 **12 段分段执行**（单进程跑全量会在约 88% 处 Windows 进程级崩溃）+ 覆盖率门禁 **100%**；
- 前端全量单测 + 覆盖率分组阈值（`src/{utils,stores,composables,api,views,components,router,config,directives,constants,data,layouts}` 均 100%）；
- 14 道静态门禁：前后端四层对齐、菜单/console tab 映射、迁移健康、依赖清单、安全审计、更新日志、
  发布说明一致性、错误文案泄漏、office 格式、全仓损坏扫描、上传限长、os_exit、目录替换、调度注册等；
- 麒麟 ARM64 与 Windows x64 安装包均由 GitHub Actions 在 tag 上现场构建，
  构建前置门禁会轮询该 commit 的 PR Checks 结论（上限 90 分钟）。
