# 图标资源说明

本目录存放应用程序图标，用于 Electron 打包和系统集成。

## 实际存在的文件

| 文件名 | 用途 | 引用位置 |
|--------|------|---------|
| `app-circle.ico` | Windows 应用/安装程序图标（含多尺寸层） | `package.json` → `win.icon` / `nsis.installerIcon` / `nsis.uninstallerIcon` |
| `app-circle-256.png` | 应用主图标（256x256 PNG） | `package.json` → `files`、`extraResources`、`linux.icon` |
| `icon.png` | 通用 PNG 图标 | `package.json` → linux 目标 `icon` |
| `bz-circle.png` | 圆形化图标（备用素材） | 保留素材，当前未被 `package.json` 引用 |

> ⚠️ **本文档曾经过期**：早期版本描述的是 `app.ico` / `app.png` / `app.icns` 三个文件，
> 但仓库中从未存在这三个文件名；macOS 目标（`.icns`）本项目也未使用（仅交付 Windows x64 与麒麟 ARM64）。
> 请以本表与实际 `ls resources/icons/` 的结果为准。

## 规格要求

- **ICO** 必须包含多个尺寸层：16x16、32x32、48x48、128x128、256x256（否则任务栏/开始菜单会糊）
- **PNG** 建议透明背景，尺寸不小于 256x256
- 图标设计应在小尺寸（16x16）下仍清晰可辨

## 如何替换图标

1. 准备一张 1024x1024 的 PNG 源图；
2. 生成各尺寸（可用 [electron-icon-builder](https://www.npmjs.com/package/electron-icon-builder)）：
   ```bash
   npx electron-icon-builder --input=icon-source.png --output=./resources/icons/
   ```
3. **按本表改名**为上表中的文件名（工具生成的默认文件名通常不是本项目使用的名字）；
4. 改了 `app-circle.ico` / `app-circle-256.png` 后需重新打包安装程序，图标才会体现；
5. 打包后建议实机安装一次确认图标显示正常。
