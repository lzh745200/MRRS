# 离线瓦片工具链（scripts/tiles）

给"帮扶管理信息系统"准备**安装包预置瓦片**与**离线导入/升级**的工具集。
全部为 Python 标准库实现（可选 Pillow 增强 PNG 校验），不依赖 GDAL 之外的第三方包。

## 目录约定

```
<瓦片仓>/MANIFEST.json
<瓦片仓>/<z>/<x>/<y>.png     # Web Mercator XYZ，与 Leaflet 一致
```

瓦片仓位置（后端 `_resolve_tiles_dir()` 优先级）：

1. `MAP_TILES_DIR` 环境变量（Electron 注入为安装包 `resources/map-tiles`，也可指向可写自定义目录）；
2. PyInstaller 冻结态 `sys._MEIPASS/resources/map-tiles`；
3. 源码态仓库根 `resources/map-tiles`。

## 四个脚本

| 脚本 | 场景 | 说明 |
|------|------|------|
| `fetch_tiles.py` | 联网机器 | 按 bbox+缩放抓取在线瓦片（provider=`osm`/`tianditu`/`amap`），限速/重试/断点续跑/失败清单/MANIFEST |
| `slice_tiles.py` | 完全离线 | 调 `gdal2tiles --xyz` 切本单位自有/已授权底图；无 GDAL 时给出安装提示并非零退出 |
| `import_tiles.py` | 完全离线 | 从 U 盘目录或 ZIP 导入瓦片仓：MANIFEST/SHA256/数量/体积/zip-slip/符号链接全校验 |
| `verify_tiles.py` | CI / 交付自检 | 校验 MANIFEST 一致性、缩放连续性、抽样 PNG 可解码；`--require-min N` 供 CI 强制 |

## 常用命令

```bash
# 仅统计瓦片数/预估体积，不联网不写盘
python scripts/tiles/fetch_tiles.py --dry-run
python scripts/tiles/fetch_tiles.py --provider amap --zoom 11-12 --dry-run

# 抓取（联网机器；天地图需 --key，高德为 GCJ-02 需前端坐标转换）
python scripts/tiles/fetch_tiles.py --provider tianditu --key <tk> --bbox 106.0,25.1,108.5,26.9 --zoom 6-11

# 自有底图切片（需 GDAL；先 --dry-run 检查环境）
python scripts/tiles/slice_tiles.py --source 底图.tif --zoom 10-14 --dry-run
python scripts/tiles/slice_tiles.py --source 底图.tif --zoom 10-14

# 校验（CI 默认不强制非空；强制要有瓦片时传 --require-min 1）
python scripts/tiles/verify_tiles.py
python scripts/tiles/verify_tiles.py --dir resources/map-tiles --require-min 1000 --json

# U 盘导入（先 dry-run 再正式导入）
python scripts/tiles/import_tiles.py --source D:\tiles.zip --dry-run
python scripts/tiles/import_tiles.py --source D:\tiles.zip --target resources/map-tiles
```

## 授权与合规

- `osm`：OpenStreetMap，ODbL；批量下载受 [tile usage policy](https://operations.osmfoundation.org/policies/tiles/) 限制，默认限速 2 req/s；
- `tianditu`：天地图，需单位申请授权 key，按服务条款缓存；
- `amap`：高德，坐标 GCJ-02（火星坐标），批量/商用须获授权；与系统标注（WGS-84）不一致时**前端必须转换坐标**；
- 自有底图：必须单位自有或已获授权，禁止用未授权数据切片分发。

退出码：`0` 成功；`1` 校验/抓取失败；`2` 参数错误；`3` 瓦片数不足或缺少 GDAL。
