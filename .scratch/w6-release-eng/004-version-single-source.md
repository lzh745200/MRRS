---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# W6-T4 版本号单一事实源（9 处收敛）

**来源**: 检测 M1/M2（docker-compose.yml 硬编码、Dockerfile ARG 1.2.0、installers/*.nsi ×4、Makefile fallback 1.5.0、main.js fallback、spec 注释；sync_version.py 仅覆盖 4 处）

## 验收标准
- [ ] sync_version.py 扩展覆盖全部 9 处；根 package.json 为唯一源
- [ ] build-windows 与 build-arm64 构建起点强制执行 + 一致性校验（不一致 fail）
- [ ] 本地运行验证全处同步

## Resolution
sync_version.js 覆盖 13 处目标并作为 CI 静态检查门禁（--check）；v1.10.0 全链一致。残留 installers/*.nsi 硬编码由 W6-T8 删除处置、Makefile fallback 已修
