---
labels: [done, severity-high]
blocks: []
blocked-by: ["w12-system-compliance/046-wal-safe-restore.md", "w13-docs-release/052-full-regression-e2e.md"]
---

# 053: 版本发布与双平台产包

**What to build:** sync_version.py 升 v1.10.0 + 手工补点清单（根 .env/electron main.js/README 徽章等）；make win-installer + make build-kylin；纯净环境安装冒烟（重点：1.9.0→1.10.0 覆盖安装数据保留 + alembic 迁移 + 登录）；提交推送 CI 绿。

**Acceptance criteria:**
- [ ] version.txt/package.json/config.py 等八处一致脚本核验
- [ ] 两安装包产物存在且体积合理
- [ ] 升级安装后 %LOCALAPPDATA% 库完好可登录
- [ ] pr-checks 工作流绿色

## Resolution
v1.10.0 双平台安装包产出（deliverables/SHA256SUMS-1.10.0.txt 三产物，commit d9efa135/3961eabc）；升级冒烟记录见发布说明
