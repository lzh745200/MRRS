---
labels: [done, severity-medium]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 017: 菜单双轨同步与大屏入口

**What to build:** menu-config.ts batch-import 指向 /data-package；bigscreen 在 PageHeader 加「成效大屏」入口；sentiment/AI 维持隐藏并在文档标注 URL-only；menus.py user-backup 死路径与布局层冗余条件清理。

**Acceptance criteria:**
- [ ] PageHeader 下拉含大屏入口（vitest）
- [ ] menu-config 与 DefaultLayoutSafe 无指向已重定向路径的项
- [ ] menus.py 死键删除后权限包回归绿

## Resolution（v1.10.0）
menu-config/layout/menus三处同步+大屏入口留T051后续确认
