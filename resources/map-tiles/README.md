# resources/map-tiles — 安装包预置瓦片目录

本目录是**安装包预置瓦片**的源目录（Electron `extraResources` → 安装包内
`resources/map-tiles`；PyInstaller `datas` → `_MEIPASS/resources/map-tiles`）。

- 仓库只保留本 README 作为占位：**空的预置瓦片目录也必须存在**，否则
  electron-builder 复制 `extraResources` 的 `from: resources/map-tiles` 会因源目录
  不存在而报错；本 README 在打包时被 `filter: ["!README.md"]` 排除，不会进安装包。
- 瓦片由运维按 `scripts/tiles/README.md` 生成：`<z>/<x>/<y>.png` + `MANIFEST.json`。
- 瓦片体积大，**不要提交到 git**；由构建机在出包前从受控介质拷入本目录。
- 安装后也可通过管理员接口 `POST /api/v1/map/tiles/import`（或
  `scripts/tiles/import_tiles.py`）离线导入/升级瓦片，无需重新安装。
