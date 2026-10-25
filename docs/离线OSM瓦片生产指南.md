# 离线 OSM 瓦片生产指南（贵州全域 z5–12，含市州分包）

> 目标：用 OSM 原始矢量数据，经"解析 → 渲染 → 分包"三段**纯离线**处理，产出本系统可直接导入的
> PNG XYZ 瓦片，既有**全省总包**，也有**9 个市州独立包**；全程不需要 GDAL / Mapnik / tilemaker / Docker。
> 版本：渲染 v2（2026-10-24）——相比 v1 新增 **multipolygon 洞（大湖/水库/大林地面）**、**z12 明细**、
> **更接近真实地图的样式**（双层道路/虚线边界/虚线铁路/比例尺/注记避让）。

---

## 一、交付物

`deliverables/osm-tiles-20261022/`

| 包名 | 地区 | 缩放 | 瓦片数 | 体积 |
|---|---|---|---|---|
| `guizhou-all_z5-12.zip` | 贵州省（全省） | z5–12 | **5,623** | **59.3MB** |
| `guizhou-guiyang_z7-12.zip` | 贵阳市 | z5–12（明细 z7–12） | 357 | 6.9MB |
| `guizhou-zunyi_z7-12.zip` | 遵义市 | z5–12 | 1,175 | 15.2MB |
| `guizhou-liupanshui_z7-12.zip` | 六盘水市 | z5–12 | 553 | 8.9MB |
| `guizhou-anshun_z7-12.zip` | 安顺市 | z5–12 | 397 | 7.4MB |
| `guizhou-bijie_z7-12.zip` | 毕节市 | z5–12 | 1,025 | 14.4MB |
| `guizhou-tongren_z7-12.zip` | 铜仁市 | z5–12 | 785 | 9.6MB |
| `guizhou-qiandongnan_z7-12.zip` | 黔东南州 | z5–12 | 1,119 | 15.2MB |
| `guizhou-qiannan_z7-12.zip` | 黔南州 | z5–12 | 1,109 | 16.6MB |
| `guizhou-qianxinan_z7-12.zip` | 黔西南州 | z5–12 | 735 | 10.7MB |

- 另有 `INDEX.md`（含 SHA256 前 16 位）、`summary.json`、`preview/`（红枫湖 z12、构皮滩 z11、贵阳 z12、全省 z5）。
- **9 个市州包都额外内含"全省 z5–6 概览"5 张瓦片**：单独导入时在省级缩放也不会出现"缺瓦片→前端回退矢量"。
- **完整包与市州包的关系**：全省包按"贵州外接矩形"渲染，共 5,623 张；9 个市州包并集 4,391 张，**全部落在贵州省界内**；
  差的 1,232 张是外接矩形内的**邻省边缘**（对各瓦片中心点按 88 个县多边形抽验，全部在省界外）。
  即：要"严格只含省界内"，导入 9 个市州包即可（并集无缺口）；要"边界不外露空白、拖到省界也能看到周边"，用全省包。
- 所有包都含 `MANIFEST.json`（provider/license/attribution/region/zoom/tileCount/totalBytes/style/tilesVersion）。

---

## 二、数据与许可

| 项 | 值 |
|---|---|
| 上游数据 | `guizhou-latest.osm.pbf`，31,209,605 B（29.76MB） |
| 下载源 | `https://download.openstreetmap.fr/extracts/asia/china/guizhou-latest.osm.pbf`（Geofabrik 在本机不可达；同属 OSM planet 数据） |
| 数据时间戳 | `2026-10-21T01:05:06Z`（replication 7337739） |
| 许可 | **ODbL-1.0**，署名 `© OpenStreetMap contributors` |
| 覆盖面 | 贵州省 bbox `103.6,24.6,109.6,29.2`（数据实际 103.56–109.62E / 24.54–29.32N） |
| 坐标系 | WGS-84 → Web Mercator XYZ（EPSG:3857），与 Leaflet/系统标注一致，无 GCJ-02 偏移 |

**合规**：瓦片右下角烧录署名；MANIFEST 写 license/attribution；前端 `tileAttribution()` 识别 OSM/ODbL 后
Leaflet 署名控件自动显示 `© OpenStreetMap contributors`。OSM 为公开众包数据，精度/现势性不适合测绘用途。

---

## 三、v2 管线

```
guizhou.osm.pbf (29.76MB)
  │ scripts/tiles/osm_extract.py   ← pyosmium 两遍扫描（relation 先读成员，再取节点坐标）
  ▼
layers.pkl 26.17MB (schema 2)
  lines 151,914 | polys 21,844（417 面带洞、1,339 洞环）| places 8,800
  │ scripts/tiles/render_osm_tiles.py --zoom 5-12 --jobs 4
  ▼
tiles-v2/{z}/{x}/{y}.png + MANIFEST   （5,623 张 / 60.0MB，4 进程 60 秒）
  │ scripts/tiles/pack_osm_subsets.py  ← 从单一权威集"取子集"，禁止逐包重渲
  ▼
deliverables/osm-tiles-20261022/*.zip （总包 + 9 市州包）
  │ scripts/tiles/verify_tiles.py + import_tiles.py（逐包真导入校验）
  ▼
系统瓦片仓 → /api/v1/map/tiles/... → 地图页「瓦片底图」
```

### v2 提取要点（multipolygon）
- 两遍扫描：pass1 只读 `type=multipolygon` 关系（676 个 / 成员 way 3,856）→ pass2 `apply_file(locations=True)` 收几何；
- **按 node id 缝合**环：多段、首尾倒序、端点相接；开链 ≤0.01° 容错补闭合；role 优先、缺失按"面积+包含"奇偶回退；多 outer 拆条；inner 挂最小包含 outer；
- 洞单独用 0.0002°（22m）简化，并旋转洞环起点保证严格落在外环内；
- 结果：**assembled 650 / failed 26 / holes 1,339**；最大水体量级正确（构皮滩 66.6 km²、三板溪 62.6、红枫湖 55.9、洪家渡 50.4、乌江渡 40.9）。

### v2 渲染要点（更接近真实地图）
- 水系：河流 casing+核心双层；湖/库/河岸填 `#cfe3f3` + 1px 岸线；wetland 另色；
- 面：forest/farmland/grass/park/urban/industrial 分色，z≥10 部分加描边；
- 道路：casing+fill 双层；`*_link` 归并父类；z12 新增 unclassified/living_street/track（1–2px）；z≥10 主干道路面高光；
- 铁路 z≥8 虚线；行政边界**边对消求并集外边界**（无需 shapely），省/地州/县分别为长虚线/短虚线/点线，虚线相位跨瓦片按全局弧长连续，2x 掩膜抗锯齿；
- 注记：优先级 city>district>county>town>village>water>park>道路名，白色描边，包围盒碰撞 + 同名去重 + 单瓦片上限 14；水面名 z≥10、路名 z≥10（线段中点，截断 8 字）；
- 右下角自适应比例尺（m/km），左下角 OSM 署名。

---

## 四、命令（可复现）

```bash
# 0) 依赖：pyosmium（离线 wheel 解压到 .scratch/osm/pylibs，$env:PYTHONPATH 指向它）
# 1) 提取（v2，含 multipolygon）
backend/.venv/Scripts/python.exe scripts/tiles/osm_extract.py \
  --input .scratch/osm/guizhou.osm.pbf --output .scratch/osm/layers.pkl --stats
# 2) 渲染全省（4 进程约 60 秒）
backend/.venv/Scripts/python.exe scripts/tiles/render_osm_tiles.py \
  --zoom 5-12 --out .scratch/osm/tiles-v2 --jobs 4
# 3) 校验权威集
backend/.venv/Scripts/python.exe scripts/tiles/verify_tiles.py \
  --dir .scratch/osm/tiles-v2 --require-min 5000 --sample 20
# 4) 打总包 + 9 市州分包（取子集，不重渲）
backend/.venv/Scripts/python.exe scripts/tiles/pack_osm_subsets.py \
  --source .scratch/osm/tiles-v2 --out-dir deliverables/osm-tiles-20261022
# 5) 逐包真导入验证（示例）
backend/.venv/Scripts/python.exe scripts/tiles/import_tiles.py \
  --source deliverables/osm-tiles-20261022/guizhou-qiannan_z7-12.zip \
  --target .scratch/osm/import-verify-v2/guizhou-qiannan_z7-12
```

> **打包铁律**：交付包必须从**同一份权威瓦片集**（`tiles-v2`）取子集生成。
> 逐包重渲会在渲染脚本变动时造成"不同包样式/数据版本不一致"（本次踩过：20:07–20:18 期间脚本在 20:14 改过，
> 早期包与后期包字节不同）。重渲只用于开发/单包调试。

---

## 五、验证记录（2026-10-22 实测）

| 项 | 结果 |
|---|---|
| v2 提取 | pkl 26.17MB / schema 2 / relations assembled 650、failed 26、holes 1,339 |
| 红枫湖 | 1,216 顶点 / **57 洞** / 55.9 km²；z12 自检图洞全部留出（洞心=背景色） |
| v2 渲染 | 5,623 张 / 60.0MB / `--jobs 4` **60.4s**（93 张/秒）；`verify_tiles --sample 20` 通过 |
| **v1 vs v2 水体**（同瓦片对比） | 构皮滩 z11 水域占比 **0.07% → 2.93%**；乌江渡 z11 **0.04% → 0.86%**；红枫湖 z12 **33.57%**（v1 无此瓦片） |
| 包一致性 | 10 个 zip 的 `tileCount == png 数`、`zoom == 实际层级`（逐包复算，全部 True） |
| 逐包导入 | 10/10 **PASS**（真 `import_tiles.py` 导入 + `verify_tiles --sample 10`） |
| 合并导入 | 10 包（含全省包）依次导入同一目录 → **5,623 张**（= 全省包）；**9 个市州包并集 = 4,391 张**，全部落在贵州省界内、**省界内缺失 0**；全省包另有 **1,232 张为邻省边缘**（考查：按瓦片中心点对 `guizhou.json` 88 个县多边形抽验，全部落在省界外） |
| 运行期 | `MAP_TILES_DIR=<合并目录>` → `/map/tile-info` `available=true / tileCount=5623 / zoomLevels 5–12`；抽查 z5/z6/z12 瓦片均 **200 image/png** |
| 前端 | `mapTiles`/`RasterTileLayer`/`MapTileManager` 单测 **65 passed**；ODbL 署名自动显示 |

---

## 六、导入到系统（三选一）

```bash
# A. UI（推荐）：管理员 → 系统管理 → 备份与存储 → 地图瓦片 → 导入瓦片包 → 选 zip
# B. 命令行导入瓦片仓
python scripts/tiles/import_tiles.py --source deliverables/osm-tiles-20261022/guizhou-all_z5-12.zip --target resources/map-tiles
# C. 打进安装包：把瓦片解到 resources/map-tiles 后 npm run build:win
#    （extraResources + PyInstaller datas + Electron MAP_TILES_DIR 均已接线）
```

多包可叠加导入（同名瓦片覆盖，不重复占空间）。导入后地图页切到「瓦片底图」即可全离线浏览。

> **导入体积上限（v1.17.4 修复）**：瓦片包上传走 multipart，中间件上限 **512MB**
> （对齐 `offline_map_service.MAX_TILE_UPLOAD_BYTES`）。此前该路径未登记在
> `MULTIPART_BODY_LIMITS`，被全局 10MB 收紧，导致市州包（7~17MB）与全省包（59MB）
> 上传报「上传内容超过大小限制 (10MB)，请拆分或压缩后重试」；v1.17.4 已修复，
> 且**非 multipart 请求仍限 10MB**（未放开 JSON 面）。前端另有 512MB 预校验。
> 若将来包体超过 512MB，需同时调整中间件条目与服务层常量，或按市州拆分导入。

---

## 六点五、内置进安装包（2026-10-22 实测）

本次按"预置进安装包"路径实际出包成功，步骤如下（Windows 环境）：

```powershell
# 1) 瓦片导入资源目录（5,623 张 / 60MB；.gitignore 已忽略瓦片本体，仅 README 入库）
python scripts/tiles/import_tiles.py --source deliverables/osm-tiles-20261022/guizhou-all_z5-12.zip --target resources/map-tiles
python scripts/tiles/verify_tiles.py --dir resources/map-tiles --require-min 5000

# 2) 重建前端（瓦片底图 UI 是新增页面代码，旧产物不含）+ 同步
cd frontend; npm run build; cd ..
robocopy frontend\dist resources\frontend /MIR     # Windows 无可用 bash 时用它替代 sync-frontend-dist.sh

# 3) 出安装包（PyInstaller + electron-builder/NSIS）
$env:TEMP='<repo>\.scratch\tmp'; $env:TMP=$env:TEMP   # 默认 %TEMP% 会 esbuild Access denied
npm run build:win
```

**结果**：

| 项 | 值 |
|---|---|
| 安装包 | `dist/electron/MRRS-Setup-1.16.4-x64.exe` → **378 MB**（上一版 1.15.15 为 230.2 MB） |
| 解包体积 | 826.4 MB（14,086 文件） |
| `resources/map-tiles`（extraResources） | 5,623 张 / 60MB + `MANIFEST.json` ✓ |
| `resources/backend/.../_internal/resources/map-tiles`（PyInstaller datas） | 5,623 张 / 60MB（**与上一份重复**） |
| 前端产物 | 含 `RasterTileLayer-*.js`、`MapTileManager-*.js`、`mapTiles-*.js` ✓ |
| 打包后端运行期实测 | 隔离 `LOCALAPPDATA` 启动 → `/health` 6s 就绪；`/api/v1/map/tile-info` → `available=true / tileCount=5623 / zooms=5..12`；`/map/tiles/12/3258/1735.png` → **200 image/png / 20,321B** |

**两个注意点**：

1. 同一台机器上如果**旧版实例仍在运行**（占用同一 `LOCALAPPDATA`），再手工启动打包后端会卡在"初始化安全密钥"
   （单实例/数据目录争用，属预期）。正常安装升级由安装器接管，不会冲突；手工冒烟请用独立 `LOCALAPPDATA` 隔离。
2. 瓦片目前被打进**两份**（Electron extraResources + PyInstaller datas），安装包多约 60MB。
   若需瘦身：把 `assistance-backend.spec` 的 map-tiles 收集改为环境变量开关（Windows Electron 靠 `MAP_TILES_DIR`
   指向 extraResources 即可），ARM64 standalone 构建再显式打开；属可选优化，本次为稳妥保留双份。

## 七、已知限制

1. **万峰湖只剩 5 个岸边碎片**：该湖跨黔/桂/滇，省域提取包缺少 18 个成员 way（关系 286450 共 67 个）；要完整湖面需更宽范围提取包。其余大型水库/湖泊完整。
2. 26 个 multipolygon 关系失败（8 个拼不出外环、18 个拼出但全被越界/退化过滤），样例会写在 `meta.relation_fail_sample_ids`。
3. 308 个洞未保留（307 个是简化后 <4 点的微型岛）。
4. 无建筑面/等高线/hillshade/POI；无沿线文字（路名仅中点横排）。
5. 注记避让为轴对齐包围盒、不做降级重排，密集城区可能偏挤（单瓦片 14 条上限兜底）。
6. 洞用页面背景色回填，会盖住洞下方原面色（不做逐层颜色回填）。
7. z11 不画 unclassified/living_street/track（按规格只在 z12 引入）；比例尺未做底衬。
8. **多包叠加导入后** `MANIFEST.json` 保留"最后导入包"的元数据，目录是并集；`verify_tiles` 对叠加目录会提示
   `tileCount` 不一致（预期）。后端 `/map/tile-info` 的 `tileCount` 走磁盘实时扫描，不受影响。

## 八、瓦片底图加载与"边缘 404"（v1.18.2）

### 8.1 现象与根因

现场曾出现：切到「瓦片底图」立即提示 **「瓦片底图加载失败，已切回矢量地图」**。
根因**不是瓦片缺失**，而是前端把**任意一张**瓦片 404 当成整体失败：

- Leaflet 视野只要有一部分落在"贵州 bbox"之外，对应瓦片必然 404（这是正确的：没有数据）；
- 旧实现未设 `bounds`/`maxBounds`，且开局固定 `zoom=7` —— 1080p 屏在 z7 的视野约 **21° 宽**，
  远超贵州 **6°** 的覆盖范围 → 一开视图就整片边缘 404 → 立即回退。

### 8.2 v1.18.2 的修复行为

- **只在覆盖范围内请求**：`bounds`（瓦片层）与 `maxBounds`（地图，外扩 0.05°）限制视野，**拖不出**贵州范围；
- **开局自适应**：`fitBounds(覆盖 bbox, maxZoom:9)`，不再固定 zoom 7；
- **边缘 404 渲染为透明**：`errorTileUrl` 用 1×1 透明 PNG，缺数据处为空白，**不破图、不回退**；
- **回退只看"真故障"**：`loaded===0 && errors>=8`（或 5s 看门狗内全 404）才回退矢量；
  有成功也有失败时，只在左下角显示非阻塞提示「部分区域超出预置瓦片范围（边缘为空白，属正常）」。

### 8.3 排障口径（`GET /api/v1/map/tile-info`）

```json
{
  "available": true,
  "tileCount": 5623,
  "zoomLevels": [5,6,7,8,9,10,11,12],
  "bbox": [103.6, 24.6, 109.6, 29.2],
  "source": "env",
  "reason": null,
  "dir": "map-tiles",
  "manifest": { "...": "..." }
}
```

| 字段 | 含义 | 典型问题 |
|---|---|---|
| `available` / `reason` | 是否可用；`dir_missing`=目录不存在、`no_tiles`=目录里没有 png | `dir_missing`：安装包缺 `resources/map-tiles`（extraResources 未打进）或 `MAP_TILES_DIR` 指向错误 |
| `source` | 目录来源：`env`（Electron 注入 `MAP_TILES_DIR`）/`meipass`（PyInstaller 内置）/`dev`（源码树） | 安装包运行时**应为 `env`**；若为 `dev`/`meipass` 说明环境变量没注入 |
| `bbox` | 该瓦片集的覆盖范围 | 与前端 `maxBounds`/`fitBounds` 一致；导入子集包后建议复查 |

> 注意：`bbox` 取自 `MANIFEST.json` 的 `region.bbox` / `bbox`，缺失时回退贵州全省 bbox；
> 若导入的是**单个市州包**，MANIFEST 的 bbox 只覆盖该市州，地图会相应缩小可拖范围（符合预期）。

### 8.4 现场快速自检

1. 浏览器/开发者工具打开 `/api/v1/map/tile-info`：`available=true` 且 `tileCount>0`；
2. 打开 `/api/v1/map/tiles/12/3258/1735.png`：应返回 PNG（`200 image/png`）；
3. 打开 `/api/v1/map/tiles/12/0/0.png`：应返回 404 —— 这是**正常**的边缘无数据，前端会渲染透明；
4. 若页面仍回退，提示里会带 `available/tileCount/source/reason`，按 8.3 对照即可判断是"没装瓦片"还是"真故障"。
