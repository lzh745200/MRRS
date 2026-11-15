# v1.18.45 发布说明（2026-11-15）

**一句话**：修正 ARM64 Electron DEB 里重复携带离线地图瓦片导致的体积膨胀（-63MB），功能零变化。

## 谁需要升级

- **ARM64 / 麒麟桌面（Electron DEB）用户**：建议升级，安装包从 412MB 回落到约 349MB，磁盘占用更小。
- **Windows x64 用户**：与 v1.18.44 功能等价（Windows 包本来只带一份瓦片），可不升级。
- **纯后端 standalone deb 用户**：与 v1.18.44 等价（standalone 本来就需要内嵌瓦片），可不升级。

## 改了什么

`build-arm64.yml` 在 electron-builder 之前删除后端产物里的内嵌瓦片副本，只保留
`<resources>/map-tiles`（Electron 主进程注入 `MAP_TILES_DIR`，后端解析优先级 `env > _MEIPASS`），
并断言该目录仍存在。离线地图功能、瓦片导入升级路径均不变。

## 验证

- 装载门禁：Windows `bundled map tiles: 5623 PNG`；standalone Dockerfile `离线地图瓦片数 ≥5000`。
- 产物体积：ARM64 Electron DEB 412,481,378 B(v1.18.44) → 约 349MB。
- 校验和：Release 三份 `SHA256SUMS-*.txt` 与 GitHub API 的 per-asset digest 一致。

## 已知边界

- 安装包未做商业代码签名（自签名证书），Windows 首次运行仍可能提示「无法验证发布者」。
- 组织模块策略默认 `shadow`；`AUTHORIZE_MODE` 默认 `off`，升级零行为变化。
