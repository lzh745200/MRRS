# F 区：地图瓦片工具链 + 后端 + 打包接线

> 目标：把"地图瓦片"从空壳改为**安装包预置瓦片 + 离线导入/升级**的真功能。
> 状态：工具链 / 后端 / 打包接线 / 单测 已完成（2026-10-21）。

## 1. 结论速览

| 项 | 结果 |
|---|---|
| `POST /api/v1/offline-map/download` | 由"假成功"改为**显式 501**，中文提示指向"导入瓦片包" |
| `GET /api/v1/map/tile-info` | 新增 `totalBytes` / `manifest`；`dir` 只回显目录名（不泄露磁盘路径） |
| `POST /api/v1/map/tiles/import` | **新增**（admin）：ZIP 上传或本机目录导入，MANIFEST/SHA256/数量/体积/zip-slip/符号链接全校验 + `AuditLogger` |
| 瓦片目录解析 | `MAP_TILES_DIR` 环境变量**优先** → `_MEIPASS/resources/map-tiles` → 仓库根 `resources/map-tiles` |
| 工具链 `scripts/tiles/` | `fetch_tiles.py` / `slice_tiles.py` / `import_tiles.py` / `verify_tiles.py`（纯标准库，中文提示，非零退出） |
| 打包接线 | `package.json` extraResources、PyInstaller spec datas、Electron `MAP_TILES_DIR`、CI `verify_tiles.py` 全部落地 |

## 2. 三种瓦片来源与授权

| 来源 | 工具 | 授权/合规 | 坐标系 |
|---|---|---|---|
| 单位自有/已授权底图（GeoTIFF、正射影像） | `slice_tiles.py`（GDAL `gdal2tiles --xyz`） | 必须自有或已获授权；**禁止**用未授权数据切片分发 | 源数据 CRS → 输出 EPSG:3857 XYZ |
| 天地图 | `fetch_tiles.py --provider tianditu --key <tk>` | 需单位申请授权 tk，按天地图服务条款缓存 | CGCS2000 / EPSG:3857（WMTS 层级以服务为准，可用 `--zoom-offset` 校准） |
| 高德 | `fetch_tiles.py --provider amap` | 批量/商用须获授权，受服务条款限制 | **GCJ-02 火星坐标**，前端必须坐标转换 |
| OpenStreetMap | `fetch_tiles.py --provider osm` | ODbL；批量下载受 [tile usage policy](https://operations.osmfoundation.org/policies/tiles/) 限制（默认限速 2 req/s） | WGS-84 / EPSG:3857 XYZ |

## 3. 体积预算

PNG 按 18KB/瓦片估算。`fetch_tiles.py --dry-run` 实测（与独立计算一致）：

| 范围 | 缩放 | 瓦片数 | 预估体积 |
|---|---|---|---|
| 黔南州 bbox(106.0,25.1,108.5,26.9) | z6-12 | **933** | **16.4MB** |
| 黔南州 | z11-12 | 847 | 14.9MB |
| 黔南州 | z6-13 | 3,555 | ≈62.5MB |
| 黔南州 | z6-14 | 14,043 | ≈247MB |
| 贵州省 bbox(103.6,24.6,109.6,29.2) | z5-11 | 1,423 | ≈25MB |
| 贵州省 | z6-12 | 5,622 | ≈99MB |

**默认建议**：省域 z5-10（368 张 ≈7MB）+ 黔南 z11-12（847 张 ≈15MB）≈ **1,215 张 / 22MB**，
装机即可用；更高层级按需增量导入。

## 4. 目录结构与 MANIFEST

```
resources/map-tiles/
  MANIFEST.json
  <z>/<x>/<y>.png          # Web Mercator XYZ，与 Leaflet 一致
```

`MANIFEST.json`（工具链与后端同口径）：

```json
{
  "schemaVersion": 1,
  "provider": "osm | tianditu | amap | local-gdal2tiles | import",
  "license": "授权/使用限制说明",
  "coordinateSystem": "EPSG:3857 XYZ",
  "bbox": [106.0, 25.1, 108.5, 26.9],
  "zoom": {"min": 6, "max": 12},
  "zoomLevels": [6, 7, 8, 9, 10, 11, 12],
  "tileCount": 933,
  "totalBytes": 17195008,
  "generatedAt": "2026-10-21T04:00:00Z",
  "hashes": {"6/51/26.png": "<sha256>"}
}
```

后端 `GET /map/tile-info` 只回显白名单字段（provider/license/coordinateSystem/zRange/
generatedAt/tileCount/totalBytes）；MANIFEST 缺失或损坏 → `manifest: null`，瓦片仍可正常服务。

## 5. 生成瓦片包（联网/离线两条路）

```bash
# A. 在线侧（运维在联网机器）：先 dry-run 看规模，再抓取（断点续跑 + 失败清单）
python scripts/tiles/fetch_tiles.py --provider osm --dry-run
python scripts/tiles/fetch_tiles.py --provider tianditu --key <tk> --bbox 106.0,25.1,108.5,26.9 --zoom 6-11 --hashes

# B. 完全离线：用自有/授权底图切片（无 GDAL 时明确提示安装方式并 exit 3）
python scripts/tiles/slice_tiles.py --source 底图.tif --zoom 10-14 --dry-run
python scripts/tiles/slice_tiles.py --source 底图.tif --zoom 10-14

# C. 交付前自检（CI 同款；--require-min 0 允许未预置，1 强制至少一张）
python scripts/tiles/verify_tiles.py --require-min 0
```

## 6. 打包接线（瓦片真正进安装包）

1. **根 `package.json` → `build.extraResources`**：
   `from: resources/map-tiles` → `to: map-tiles`，`filter: ["**/*","!README.md"]`。
   - 方案：仓库提交 `resources/map-tiles/README.md` 占位（目录恒存在），README 被 filter 排除，
     不占安装包体积；瓦片本体不进 git，由构建机出包前拷入。
   - 已用 electron-builder 24.13 自身的 `FileMatcher/copyFiles` 实测（见 §9 第 4 条）：
     该条目复制后目标目录为空（README 被排除）、无异常；且此版本对**缺失的 `from`** 只 `warn`
     "file source doesn't exist" 后跳过，并不会让构建失败（README 占位让行为确定、不依赖版本差异）。
2. **`backend/assistance-backend.spec` → `datas`**（存在性守卫，本地无瓦片也能打包）：

   ```python
   _tiles_dir = os.path.join(project_root, 'resources', 'map-tiles')
   if os.path.isdir(_tiles_dir):
       datas.append((_tiles_dir, os.path.join('resources', 'map-tiles')))
   ```

   与 arm64 spec（E 区已改：`backend_linux_arm64_standalone.spec:41-43`）**逐字一致**，
   `_MEIPASS/resources/map-tiles` 命中。
3. **`electron/main.js`**：新增 `getTilesDir()` 并在 backend 子进程 env 注入
   `MAP_TILES_DIR`；打包态用 `process.resourcesPath/map-tiles`，开发态 `existsSync` 回退
   `<repo>/resources/map-tiles`（dev 下 `process.resourcesPath` 指向 Electron 自带 resources，
   不能直接用）。
4. **`.github/workflows/build-windows.yml`**：PyInstaller 之后加
   `python scripts/tiles/verify_tiles.py --require-min "${MAP_TILES_REQUIRED:-0}"`；
   仓库变量 `MAP_TILES_REQUIRED=1` 时强制 ≥1 张瓦片。

> 注意：spec 收集与 extraResources 会让瓦片在安装包内出现两份（后端 `_internal/resources/map-tiles`
> 与 `resources/map-tiles`），运行期以 `MAP_TILES_DIR` 指向的后者为准；如需省体积可后续只保留
> extraResources 一份（当前保留双份以兼容"单独分发后端"的部署方式）。

## 7. 离线导入 / 升级流程

- **UI/接口**：管理员 `POST /api/v1/map/tiles/import`
  - `file`：multipart ZIP（≤512MB，`read_upload_with_limit` 限长）；
  - `source_dir`：服务端本机目录（U 盘大包免上传）；
  - 二选一；两者都校验 MANIFEST、SHA256、数量（≤200k）、体积（解压后 ≤2GB）、
    zip-slip、符号链接；合并写入（同名覆盖），可用于增量升级。
- **离线脚本（不启动应用也能导入）**：
  `python scripts/tiles/import_tiles.py --source D:\tiles.zip --target resources/map-tiles`。
- 导入后 `GET /map/tile-info` / `GET /offline-map/status` 立即反映新计数（每次请求实时扫描磁盘，无缓存）。

## 8. 坐标系不一致导致的标记偏移

- 高德瓦片为 **GCJ-02**，帮扶村/学校标注为 **WGS-84**：直接叠加会偏移 **数百米**
  （城区约 300–600m，随纬度变化）。前端必须做 WGS-84→GCJ-02 转换后再渲染，
  或改用 CGCS2000/WGS-84 底图（天地图、自有底图）与系统标注天然对齐。
- 天地图 `img_w` 为 EPSG:3857（Web Mercator），与 Leaflet 默认一致；若座标系选 c（经纬度）
  需自行处理分辨率与编号差异——本工具链默认只产出标准 XYZ。
- `fetch_tiles.py --provider amap --dry-run` 会打印 GCJ-02 警告；MANIFEST 的
  `coordinateSystem` 字段供前端/运维核对。

## 9. 自测命令与结果（2026-10-21）

```bash
cd backend
# 任务指定的 5 个文件：142 passed
.venv\Scripts\python.exe -m pytest \
  tests/unit/test_api_map_full.py tests/unit/test_map.py tests/unit/test_map_api_cov.py \
  tests/unit/test_branch_gaps_group_d.py tests/unit/test_cov_b4b_offline_map_service.py -q
# 加新增/离线相关文件后：289 passed
.venv\Scripts\python.exe -m pytest \
  tests/unit/test_tiles_pipeline.py tests/unit/test_offline_map_api_cov.py \
  tests/unit/test_offline_map_service.py tests/test_offline_map.py -q
# 覆盖率（本区改动模块）：offline_map_service 100%、offline_map 100%、
# map.py 新增分支全部覆盖（其余 Miss 为未跑其它测试文件的既有行）

python scripts/tiles/verify_tiles.py            # exit 0（未预置瓦片，按可选处理）
python scripts/tiles/verify_tiles.py --require-min 1   # exit 3（强制要求非空时正确失败）
python scripts/tiles/fetch_tiles.py --dry-run   # 933 张 / 16.4MB，exit 0（不联网、无需 key）
python scripts/tiles/slice_tiles.py --source x.tif --dry-run  # 无 GDAL → exit 3 + 安装提示
node --check electron/main.js                   # exit 0
python -c "import ast;ast.parse(open('backend/assistance-backend.spec',encoding='utf-8').read())"
python -c "import yaml;yaml.safe_load(open('.github/workflows/build-windows.yml',encoding='utf-8'))"
python -c "import json;json.load(open('package.json',encoding='utf-8'))"

# 4) electron-builder extraResources 行为实测（用 app-builder-lib 的 FileMatcher/copyFiles，
#    等价于 electron-builder 24.13 的 extraResources 复制路径）：
#    copied into packaged dir: []   README.md excluded: true
#    missing source tolerated: true（仅 warn "file source doesn't exist"）
```

附：工具链端到端自测（ZIP 生成 → verify → import → 再次 verify）：

```text
verify(valid) exit = 0 tiles = 3 problems = []
verify(gap)   exit = 1 ['MANIFEST 缩放范围([5, 7]) 与实际(5-5) 不一致']
import dry-run exit = 0 / import real exit = 0（3 张写入 store）
verify(target) exit = 0
zip-slip rejected exit = 1（"压缩包内存在路径穿越: ../../evil.png"）
```

## 10. 遗留问题 / 后续

1. 本机无 electron-builder 出包环境，未实跑 `npx electron-builder`；已用"目录恒存在（README 占位）+
   存在性守卫"消除 `from` 缺失报错风险，建议首次 CI 出包时确认 `dist/electron/win-unpacked/resources/map-tiles` 存在。
2. 预置瓦片数据本身未进仓库（体积/授权原因），CI 首次出包默认 `--require-min 0`；要**强制**预置，
   需在构建机拷入瓦片并设置仓库变量 `MAP_TILES_REQUIRED=1`。
3. 瓦片升级目前为"整体合并覆盖"，没有版本对比/回滚；MANIFEST 会被最后一次导入覆盖
   （如需多来源共存，应扩展为 provider 子目录 + 优先级，本区未做）。
4. GCJ-02→WGS-84 的坐标转换在前端（fe-tiles 区）；后端不做隐式坐标变换。
5. `verify_tiles.py` 的 PNG 深度校验依赖 Pillow（冻结后端自带），CI runner 若未装 Pillow 会降级为
   文件头/IHDR 校验（脚本已提示）。
