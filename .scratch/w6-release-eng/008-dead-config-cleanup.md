---
labels: [ready-for-agent, severity-medium]
blocks: []
blocked-by: []
---

# W6-T8 死配置与遗留物清理

**来源**: 检测 S5/M6/M7/L2/L3（主 Dockerfile COPY 不存在的 electron/package.json；k8s/ 镜像名无产出、configmap DB 文件名错误；Dockerfile.fpm/arm64/deb-complete GLIBC 矛盾；installers/*.nsi 废弃；test_scripts/ 42 个一次性脚本；.qwen/.reasonix/skills-lock.json 残留）

## 验收标准
- [ ] 修复或删除主 docker/Dockerfile 的 electron 构建段（二选一记录理由）
- [ ] 删除 k8s/、installers/、test_scripts/、Dockerfile.fpm、Dockerfile.arm64、Dockerfile.deb-complete（git rm，保留 git 历史）
- [ ] 现役 Dockerfile 头部注释标注"现役 + GLIBC 目标"
- [ ] 移除 .qwen/.reasonix/skills-lock.json/environment.yml（确认无人引用后）
- [ ] 全量测试绿（确保无脚本被 CI 引用）
