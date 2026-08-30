---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# W6-T6 PyInstaller onedir 化 + 打包冗余清理（ADR-0006）

**来源**: 检测 M4/S1 关联（onefile 每次解包 %TEMP% → 首启超 3 分钟+误报画像；datas 整个 app/ 与 collect_submodules 双份；hiddenimports 60 条手写与 collect 重复、含已删依赖 prophet）

**完成（2026-08-30，详见 docs/adr/0006-pyinstaller-onedir.md）**:
- spec 改 onedir（EXE exclude_binaries + COLLECT），本地 PyInstaller 6.19
  构建通过：assistance-backend.exe 37MB + _internal 242MB（alembic/ini/env.example
  就位，app/ 源码目录已摘除）。
- 冷启动实测：onefile 32.3s → onedir 8.6s（~3.8 倍）；/health 均正常。
- datas 摘除 app/ 与 prometheus_client；hiddenimports 删除 aiosqlite/jieba/
  bs4/prometheus_client 及 54 条被 collect_submodules('app') 覆盖的手写路由。
  **偏差说明**：工单原文"已删依赖 prophet"与现状不符——prophet 仍被
  trend_prediction_service（ai_enhanced/assessment 引用）延迟导入、CI 仍
  best-effort 安装，故保留按存在性条件收集其数据文件，仅从 hiddenimports 摘除。
- 消费方全适配：package.json extraResources（目录）、main.js getBackendExePath
  （onedir 优先 + onefile 回退）、build-windows.yml 产物验证、
  Dockerfile.backend-arm64（校验/GLIBC/output 整目录）、build-arm64.yml
  （artifact 目录上传 + prepare 结构守卫 + postinst find chmod）；
  麒麟 standalone 用独立 spec 本就 onedir，不受影响。
- 本地完整构建：electron-builder NSIS 产物 帮扶管理系统 Setup 1.10.6.exe
  （227MB）+ win-unpacked 结构核对；打包应用启动冒烟：后端自动选 8001
  （8000 被 dev 服务占用→端口兜底逻辑顺带验证）→ 登录 200 → 列表 200 →
  导出 200（有效 xlsx 5240B）。

## 验收标准
- [x] spec 改 onedir（NSIS 打目录）；冷启动实测对比记录（ADR-0006）
- [x] 移除 datas 中 app/ 目录与重复 hiddenimports、prophet（prophet 见偏差说明）
- [x] electron main.js 启动路径适配 onedir 结构
- [x] Windows 安装包本地完整构建并冒烟（登录→列表→导出，API 级全链路）
- [x] docs/adr/0006-pyinstaller-onedir.md
