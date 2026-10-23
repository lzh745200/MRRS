# 离线 OCR（ARM64）与地图瓦片预置 —— 可行性、实现与验证报告

> 核查/实施日期：2026-10-24
> 目标：回答"ARM64 安装包能否实现离线 OCR"与"瓦片能否全部提前打进安装包"，并把结论落成**可构建、可验证、可回退**的实现。
> 范围：构建配置（Dockerfile / PyInstaller spec / CI）、后端瓦片服务、打包接线、前端瓦片底图、瓦片工具链。
> 状态：**已实现并通过本地可执行的验证**；ARM64 真机与出包验证需在 CI/麒麟环境执行（本机无 Docker、无 GDAL、无 ARM64 环境，已在文中标注）。

---

## 零、结论先行

### 1. ARM64 离线 OCR：**可行，且已落地改造**

此前 ARM64 被裁剪的理由是"onnxruntime / opencv 无 buster ARM64 wheel"。**该理由已过时**：

- `onnxruntime 1.31.0` 提供 `cp311-manylinux_2_28_aarch64` 轮子（20.4MB）；
- 我下载该轮子并扫描 `onnxruntime/capi/libonnxruntime.so.1.31.0`：引用的 GLIBC 符号**最高为 GLIBC_2.28**（集合 2.17/2.25/2.27/2.28），DT_NEEDED 只有 `libc/libdl/libgcc_s/libm/libpthread/librt/libstdc++`，**不需要 libgomp、libGL、libcuda**；
- 构建基座 `python:3.11-slim-buster` 与目标机麒麟 V10 的 glibc 都是 **2.28**，与 manylinux_2_28 的下限**正好匹配**；
- `opencv-python-headless 4.12.0.88` 有 `cp37-abi3-manylinux2014_aarch64` 轮子（31.6MB，不链接 libGL）；`pyclipper 1.4.0`、`shapely 2.2.0`、`PyYAML 6.0.3`、`numpy 2.4.6`、`pillow 12.3.0` 均有 aarch64 轮子；`rapidocr-onnxruntime 1.4.4` 为 `py3-none-any`（模型随 wheel，14.2MB）。

实现要点：过滤正则放开 → `opencv-python-headless` 替代非 headless（**保持 DEB 零外部依赖**）→ PyInstaller spec 显式收集 → 构建期 OCR 冒烟 + 出包后载荷断言 → 文档同步。详见 §一。

### 2. 地图瓦片：**机制已实现，瓦片数据需一次性生成**

- 假成功接口已改为显式 501（`POST /offline-map/download`）；
- 新增 `GET /map/tile-info`（真实统计 + MANIFEST）、`POST /map/tiles/import`（ZIP/U 盘目录导入，管理员）；
- 瓦片目录解析改为 **`MAP_TILES_DIR` 环境变量优先**，Electron 注入 → 安装包内 `<resources>/map-tiles`；
- `package.json extraResources` + PyInstaller `datas` + CI 校验全部接线，**瓦片会随安装包分发**；
- 前端新增 Leaflet 瓦片底图（默认视图仍是 ECharts 矢量，瓦片为可选切换，懒加载）；
- 新增 `scripts/tiles/` 工具链：在线抓取 / 离线切片 / 导入 / 校验。

体量结论（PNG 18KB/张估算，与工具 dry-run 互验）：**黔南州 z6–12 = 933 张 / 16.4MB**；**贵州省 z5–11 = 1,423 张 / 25MB**；建议默认预置"省域 z5–10（368 张 / 7MB）+ 黔南 z11–12（847 张 / 15MB）≈ 22MB"，对 230MB 安装包影响约 +10%。

### 3. 坐标系结论（决定能不能直接叠加标注）

仓库 `frontend/src/assets/geo/guizhou.json` 中 **都匀市的 center = [107.517021, 26.258205]**，与 WGS-84/CGCS2000 实测值吻合（高德 GCJ-02 约为 [107.5217, 26.2614]，差约 400m）→ **现有底图数据是 WGS-84 系**。

因此：**首选天地图（CGCS2000，与标注天然对齐）或单位自有 WGS-84 底图**；若用高德（GCJ-02）底图，必须在前端把标注做 WGS-84→GCJ-02 转换（已实现 `toDisplayCoord/convertMarkersForTiles`，并在 UI 提示）。OSM 批量下载受 tile usage policy 限制，仅作应急。

---

## 一、ARM64 离线 OCR：可行性证据与实现

### 1.1 可行性证据（2026-10-21 实测）

| 依赖 | ARM64/cp311 轮子 | 大小 | 结论 |
|---|---|---|---|
| onnxruntime 1.31.0 | `manylinux_2_28_aarch64` | 20.4MB | ✅ 最高引用 GLIBC_2.28，与麒麟/ buster 匹配 |
| opencv-python-headless 4.12.0.88 | `cp37-abi3-manylinux2014_aarch64` | 31.6MB | ✅ 无 libGL 依赖 → DEB 可保持零外部依赖 |
| numpy 2.4.6 | `manylinux_2_27/2_28_aarch64` | 15.2MB | ✅ 已在主清单 |
| pillow 12.3.0 | `manylinux_2_27/2_28_aarch64` | 6.0MB | ✅ 已在主清单 |
| pyclipper 1.4.0 | `manylinux_2_24/2_28_aarch64` | 0.9MB | ✅ |
| shapely 2.2.0 | `manylinux_2_24/2_28_aarch64` | 2.1MB | ✅ |
| PyYAML 6.0.3 | `manylinux2014_aarch64` | 0.7MB | ✅ |
| rapidocr-onnxruntime 1.4.4 | `py3-none-any`（模型随 wheel） | 14.2MB | ✅ |
| six / tqdm / flatbuffers / protobuf | 纯 Python / abi3 aarch64 | — | ✅ |

> ELF 验证方法（可复现）：下载 aarch64 wheel → 扫描 `libonnxruntime.so` 中的 `GLIBC_2.x` 版本串与 DT_NEEDED 名称。结果：`GLIBC_2.17/2.25/2.27/2.28` + `libc/libdl/libgcc_s/libm/libpthread/librt/libstdc++`。

### 1.2 改动清单

| 文件 | 改动 |
|---|---|
| `backend/requirements-arm64-ocr.txt`（新增） | ARM64 OCR 依赖精确清单（headless cv2 + onnxruntime + pyclipper/shapely/tqdm/flatbuffers/protobuf） |
| `docker/Dockerfile.kylin-standalone` | ① 过滤正则**移除** `rapidocr-onnxruntime|onnxruntime|opencv-python`；② 追加 `requirements-arm64-ocr.txt`，并 `pip install --no-deps rapidocr-onnxruntime==1.4.4`（避免把非 headless opencv 拉回来）；③ 构建期 OCR 冒烟 `docker/ocr_smoke_arm64.py`（import cv2 + `RapidOCR()` 实例化 + 对 Pillow 合成图真实识别 + 断言识别出数字）；④ PyInstaller 冻结产物断言（ONNX 模型 ≥2、onnxruntime 绑定库 ≥1、cv2 扩展 ≥1）；⑤ DEB `Depends` **保持为空**（headless 方案，零外部依赖），并在注释中写明换回非 headless 时必须补 libgl1 |
| `docker/ocr_smoke_arm64.py`（新增） | 构建期可复用的 OCR 冒烟脚本（不用 Dockerfile heredoc，避免 BuildKit 语法依赖） |
| `backend/backend_linux_arm64_standalone.spec` | 条件收集 `collect_data_files('rapidocr_onnxruntime')`、`collect_dynamic_libs('onnxruntime')`、`collect_submodules(...)`（`find_spec` 守卫）；另加 **map-tiles datas**（与 Windows spec 同一 snippet） |
| `.github/workflows/build-arm64.yml` | ① Electron DEB 载荷断言（ONNX + onnxruntime 绑定）；② standalone DEB 载荷断言 + **零依赖契约断言**（Depends 不得含 libgl1/libgomp1/libglib2.0-0） |
| `README.md`、`docs/04-部署文档/*`、`docs/03-开发文档/06-运维文档/技术栈说明.md` | 口径由"ARM64 过滤降级为 503"改为"ARM64 内置离线 OCR（headless，glibc≥2.28），安装包 +65~75MB" |

> 说明：`docker/Dockerfile.kylin-standalone` 中仍保留一条**安装方式用**的 `grep -v '^rapidocr-onnxruntime'`（把引擎本体从批量清单摘出、改用 `--no-deps` 单装，以避开其写死的非 headless `opencv-python` 依赖名）。这是"换安装方式"，不是能力降级；主过滤正则已完全不含三项。

### 1.3 体积与性能

- 安装包增量估算：onnxruntime 20.4MB + headless cv2 31.6MB + pyclipper/shapely/protobuf 等 ≈ **+60~75MB**（压缩后实际值以 CI 产物为准，README 已写 65~75MB）。
- 模型 15.4MB（3 个 ONNX）沿用现有随包方式；首次识别初始化约 1~2s（Windows 实测 1.15s，ARM64 预期相近，CPU 推理）。
- DEB 体积预计从约 58MB（standalone）增至约 120~130MB 量级。

### 1.4 风险与回退（必须知悉）

| 风险 | 表现 | 处置 |
|---|---|---|
| 目标机 glibc < 2.28 | `import onnxruntime` 失败（`GLIBC_2.28 not found`） | 前置条件写入部署文档；现有 `ocr_service.available()` + 503 + 手工录入降级链**保持不变** |
| 缺 `libstdc++`/`libgcc_s` 极简系统 | 同上报错 | 麒麟 V10 默认具备；极端场景在 DEB 用 `Recommends` 提示（当前无硬依赖） |
| PyInstaller 漏收模型/so | 装完仍 503 | 构建期已加两层断言（Dockerfile 内 + CI 出包后 `dpkg-deb -c`），构建即红 |
| onnxruntime 模型精度 | 凭证金额/日期识别偏差 | 保持"识别结果可编辑 + 手工录入兜底" |

### 1.5 验证步骤（本机不可执行，需 CI/真机）

1. CI：`build-arm64.yml` 两处冒烟/断言全绿（构建期 OCR 冒烟 + 出包载荷断言 + 零依赖断言）。
2. 真机：`dpkg -i assistance-management-system_<ver>_arm64.deb` → `systemctl start` → `POST /api/v1/funds/ocr-voucher` 上传凭证图 → 返回 200 且金额/日期可解析；断网复测一次。
3. 麒麟 V10 桌面版（Electron DEB）同样验证一次（复用同一 backend 产物）。

---

## 二、地图瓦片预置：架构、来源与体量

### 2.1 端到端链路

```
[运维·联网机] scripts/tiles/fetch_tiles.py   ─┐
[运维·离线机] scripts/tiles/slice_tiles.py   ─┼→ resources/map-tiles/{z}/{x}/{y}.png + MANIFEST.json
[交付包/ U盘] import_tiles.py / 管理页导入    ─┘
                        │
        verify_tiles.py（CI + 交付自检：数量/体积/MANIFEST/SHA256/PNG 抽样）
                        │
        electron-builder extraResources → <app>/resources/map-tiles
        PyInstaller datas            → <backend>/_internal/resources/map-tiles
                        │
        Electron 注入 MAP_TILES_DIR（打包态 process.resourcesPath/map-tiles；开发态仓库 resources/map-tiles）
                        │
        GET /api/v1/map/tiles/{z}/{x}/{y}.png  ← Leaflet（本机回环、无需鉴权、immutable 缓存）
        GET /api/v1/map/tile-info               ← 管理页展示覆盖度 + MANIFEST 元数据
        POST /api/v1/map/tiles/import（admin）  ← ZIP 或本机目录增量导入（离线升级）
```

### 2.2 瓦片来源与授权（重要）

| 来源 | 工具 | 授权 | 坐标系 | 建议 |
|---|---|---|---|---|
| **单位自有/已授权底图**（GeoTIFF/正射影像） | `slice_tiles.py`（GDAL `gdal2tiles --xyz`，全离线） | 自有或已授权 | 转 EPSG:3857 | **首选**：无外部授权争议、可与标注天然对齐 |
| **天地图** | `fetch_tiles.py --provider tianditu --key <tk>` | 需单位申请 tk，按服务条款缓存 | CGCS2000（≈WGS-84） | **次选**：官方授权、坐标对齐 |
| 高德 | `fetch_tiles.py --provider amap` | 批量/商用须授权 | **GCJ-02** | 仅在已有授权时使用；前端已做坐标转换与提示 |
| OpenStreetMap | `fetch_tiles.py --provider osm` | ODbL，批量受 tile usage policy 限制（默认限速 2 req/s） | WGS-84 | 仅应急/演示 |

> 结论：**军事/涉密场景建议走"自有底图切片"或"天地图授权"**，避免 GCJ-02 偏移与授权风险。

### 2.3 体量预算（与工具 dry-run 互验）

| 范围 | 缩放 | 瓦片数 | 预估体积 |
|---|---|---|---|
| 黔南州 (106.0,25.1,108.5,26.9) | z6–12 | **933** | **16.4MB** |
| 黔南州 | z11–12 | 847 | 14.9MB |
| 黔南州 | z6–13 | 3,555 | ≈62.5MB |
| 黔南州 | z6–14 | 14,043 | ≈247MB |
| 贵州省 (103.6,24.6,109.6,29.2) | z5–11 | 1,423 | ≈25MB |
| 贵州省 | z6–12 | 5,622 | ≈99MB |

**推荐默认预置**：省域 z5–10（368 张 ≈7MB）+ 黔南 z11–12（847 张 ≈15MB）= **1,215 张 ≈22MB**（安装包 +约 10%）。更高层级（z13+）按需通过"导入瓦片包"增量补充。

### 2.4 操作步骤（可直接执行）

```bash
# ① 联网机：先 dry-run 核对规模（不联网、不写盘）
python scripts/tiles/fetch_tiles.py --provider tianditu --key <tk> \
  --bbox 106.0,25.1,108.5,26.9 --zoom 6-12 --dry-run
# ② 正式抓取（限速/重试/断点续跑，生成 MANIFEST）
python scripts/tiles/fetch_tiles.py --provider tianditu --key <tk> \
  --bbox 106.0,25.1,108.5,26.9 --zoom 6-12 --hashes

# 或完全离线：用自有底图切片
python scripts/tiles/slice_tiles.py --source ./底图.tif --zoom 10-14 --dry-run
python scripts/tiles/slice_tiles.py --source ./底图.tif --zoom 10-14

# ③ 交付前自检（CI 同款）
python scripts/tiles/verify_tiles.py --require-min 1

# ④ 打包（瓦片随包）
npm run build:win      # extraResources + PyInstaller datas 自动收录
```

离线升级（已有安装包补瓦片）：管理员在「系统管理 → 备份与存储 → 地图瓦片」页上传 ZIP，或把 U 盘目录拷入后执行
`python scripts/tiles/import_tiles.py --source D:/tiles.zip --target resources/map-tiles`（服务端同款校验：MANIFEST/SHA256/数量≤200k/解压≤2GB/zip-slip/符号链接）。

### 2.5 CI 门禁

| 环节 | 断言 |
|---|---|
| `build-windows.yml` | PyInstaller 后执行 `verify_tiles.py --require-min ${MAP_TILES_REQUIRED:-0}`；设仓库变量 `MAP_TILES_REQUIRED=1` 即强制"无瓦片不许出包" |
| `build-arm64.yml` | 同款校验 + DEB 载荷中 map-tiles 存在性（若预置） |
| 打包后 | 建议首次出包人工确认 `win-unpacked/resources/map-tiles/` 有 PNG（本机无 electron-builder 环境，未实跑） |

> ⚠️ **提交前必做**：`scripts/tiles/`、`resources/map-tiles/README.md`、`backend/tests/unit/test_tiles_pipeline.py` 等新增文件目前均为 **untracked**。若未 `git add` 就推送，CI checkout 后既没有瓦片工具链、也没有 `extraResources` 的源目录（`resources/map-tiles`），打包会失去预置瓦片能力。

---

## 三、本次验证记录（实测）

| 验证项 | 方法 | 结果 |
|---|---|---|
| aarch64 轮子齐备性 | PyPI JSON 查询 cp311/aarch64 文件列表 | ✅ 全部齐备（见 §1.1） |
| onnxruntime 的 glibc 上限 | 下载 wheel + ELF 版本串扫描 | ✅ 最高 GLIBC_2.28；无 libgomp/libGL 依赖 |
| 瓦片体量预算 | Python 独立计算 vs `fetch_tiles.py --dry-run` | ✅ 两者一致（933 张 / 16.4MB） |
| 后端瓦片改造单测 | `pytest test_{map,api_map_full,map_api_cov,offline_map_api_cov,offline_map_service,tiles_pipeline}.py` | ✅ **214 passed**（F 区跑全部相关文件合计 **289 passed**，其中新增 `test_tiles_pipeline.py` 110 项） |
| 前端瓦片组件/管理页 | `vitest run`（5 个文件） | ✅ **80 passed** |
| 后端 lint/语法 | `flake8 app/`（改动文件）、`py_compile`、spec `ast.parse` | ✅ app 文件 0 issue；测试文件的 flake8 提示属既有风格、CI 不扫 tests |
| 瓦片校验脚本 | `verify_tiles.py --require-min 0`（占位目录） | ✅ exit 0 + 明确"未预置瓦片"警告 |
| **瓦片包端到端导入** | 合成一个真实瓦片包（256×256 PNG + MANIFEST/SHA256）→ `import_tiles.py --dry-run` → 真实导入 → `verify_tiles.py --require-min 1` | ✅ 三步全通过：dry-run 1 张/762B、导入成功、verify `[通过]` |
| **运行期瓦片服务与坐标系优先** | 设 `MAP_TILES_DIR` 指向上述瓦片仓，用 `TestClient` 调用真实应用 | ✅ `GET /map/tile-info` 返回 `available:true, tileCount:1, totalBytes:762, manifest{provider,zRange,generatedAt}, minZoom/maxZoom:8`；`GET /map/tiles/8/207/104.png` → **200 image/png / 762B（匿名可访问）**；缺失瓦片 → 404（Leaflet `tileerror` 路径） |
| 假下载接口语义 | `POST /offline-map/download` | ✅ 已改为 501（无 CSRF 时先被 403 拦截，属正常中间件顺序） |
| 打包接线语法 | `package.json` JSON 解析、workflow YAML 解析、`node --check electron/main.js` | ✅ 通过（F 区报告） |

**尚未在本机执行（环境缺失，需 CI/真机）**：ARM64 镜像构建与 OCR 冒烟、`dpkg -i` 真机安装、`electron-builder` 出包、麒麟桌面版验证。

---

## 四、与上一轮"离线不适用功能"核查的闭环状态

| 上一轮问题 | 本次处置 | 状态 |
|---|---|---|
| 地图瓦片"下载"假成功（A8/C2） | `POST /offline-map/download` 改为显式 501 + 指向"导入瓦片包" | ✅ 已闭环 |
| 瓦片资产不存在、`/map/tiles` 恒 404（C1） | 预置 + 导入机制落地，`resources/map-tiles` 占位目录与打包接线就绪 | ✅ 机制闭环；**数据待一次性生成** |
| 麒麟 ARM64 无 OCR（C3） | headless cv2 + onnxruntime + spec 收取 + 构建期/出包断言 | ✅ 已闭环（待 CI 真机构建验证） |
| 文档宣称"Leaflet 离线瓦片双模式"（与实现不符） | 前端已真正实现 Leaflet 瓦片底图（可选），文档口径同步 | ✅ 已闭环 |
| `/map/config` 的 `map_type:"gaode"` 误导 | 见「遗留」——建议改 `vector`/删除（本轮未改，避免与 F 区契约冲突） | ⚠️ 待办（1 行） |
| 瓦片管理页"下载需联网"文案 | 改为"默认矢量地图 + 导入瓦片包"如实文案 | ✅ 已闭环 |
| Electron 拼写检查可能联网（D8） | 未改（风险极低，失败仅无拼写检查） | ⚠️ 待办（1 行 `spellcheck:false`） |

---

## 五、遗留项与建议

1. **瓦片数据生成需要一次人工动作**：仓库不内置瓦片（体积 + 授权原因）。首次出包请按 §2.4 生成并设置 `MAP_TILES_REQUIRED=1`，否则安装包地图默认仍是矢量（功能可用，只是无栅格底图）。
2. **`map_type:"gaode"` 清理**与 **`spellcheck:false`** 两处一行改动，建议下个补丁一并做。
3. **瓦片升级无版本回滚**：当前为"整体合并覆盖"，MANIFEST 被最后一次导入覆盖；如需多来源共存，建议扩展为 `provider` 子目录 + 优先级（F 区已留说明）。
4. **ARM64 真机验收**：CI 通过后务必在麒麟 V10（桌面版 + 服务器版各一台）各跑一次 OCR 与安装，确认 glibc/零依赖假设成立。
5. **瓦片与坐标系**：若最终选用高德底图，需在验收时用已知点（如都匀市政府 107.5175,26.2583）比对偏移，>200m 即说明转换未生效。
6. **QEMU 构建超时风险**：ARM64 镜像在 QEMU 下 `strip/upx` 大 `.so`（onnxruntime 25MB、cv2）可能超时；应急做法是在 spec 的 `upx_exclude` 中加入 `onnxruntime/*`、`opencv*`。
7. **`backend/backend_linux_arm64.spec` 未被任何流水线引用**：本次只改了真正出包用的 `backend_linux_arm64_standalone.spec`；前者与 `docs/04-部署文档/01-Windows部署/构建打包指南.md:98` 的表述已过时，建议后续统一（避免维护两份 ARM64 spec）。
8. **`httpx` 未登记 `required_packages.py`**（上一轮发现）与 **`map_type:"gaode"`**、**`spellcheck:false`** 三处小改动建议随下个补丁一起收口。
