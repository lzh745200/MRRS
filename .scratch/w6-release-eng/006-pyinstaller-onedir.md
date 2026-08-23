---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: []
---

# W6-T6 PyInstaller onedir 化 + 打包冗余清理（ADR-0006）

**来源**: 检测 M4/S1 关联（onefile 每次解包 %TEMP% → 首启超 3 分钟+误报画像；datas 整个 app/ 与 collect_submodules 双份；hiddenimports 60 条手写与 collect 重复、含已删依赖 prophet）

## 验收标准
- [ ] spec 改 onedir（NSIS 打目录）；冷启动实测对比记录
- [ ] 移除 datas 中 app/ 目录与重复 hiddenimports、prophet
- [ ] electron main.js 启动路径适配 onedir 结构
- [ ] Windows 安装包本地完整构建并冒烟（登录→列表→导出）
- [ ] docs/adr/0006-pyinstaller-onedir.md
