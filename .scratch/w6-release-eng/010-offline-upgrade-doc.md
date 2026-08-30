---
labels: [done, severity-low]
blocks: []
blocked-by: []
---

# W6-T10 OFFLINE_UPGRADE.md 升级与回滚文档

**来源**: 检测 L7（无自动更新为有意设计，但升级流程文档缺失）

**完成（2026-08-30）**:
- 新增 `docs/04-部署文档/OFFLINE_UPGRADE.md`：备份（应用内/手动/快照）→
  SHA256SUMS 校验（引用本批 W6-T5 产物清单）→ 签名校验占位（引用 W6-T1
  代码签名文档）→ Windows/麒麟覆盖安装 → 首次启动自动 Alembic 迁移验证 →
  数据兼容说明（迁移前向性）→ 回滚路径（未迁移仅回程序 / 已迁移程序+数据
  一并回退）→ 速查清单。已登记到 04-部署文档/README.md 快速链接。
- NSIS 卸载 MessageBox 加 `/SD IDNO` + `MB_DEFBUTTON2`：静默卸载
  （企业批量部署）默认保留用户数据；makensis 编译验证通过。

## 验收标准
- [x] 文档覆盖：升级前备份 → 校验签名/SHA256 → 安装 → alembic 迁移验证 → 数据兼容检查 → 回滚路径
- [x] NSIS 卸载 MessageBox 加 `/SD IDNO` 静默默认
