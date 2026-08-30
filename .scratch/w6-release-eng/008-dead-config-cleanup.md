---
labels: [done, severity-medium]
blocks: []
blocked-by: []
---

# W6-T8 死配置与遗留物清理

**来源**: 检测 S5/M6/M7/L2/L3（主 Dockerfile COPY 不存在的 electron/package.json；k8s/ 镜像名无产出、configmap DB 文件名错误；Dockerfile.fpm/arm64/deb-complete GLIBC 矛盾；installers/*.nsi 废弃；test_scripts/ 42 个一次性脚本；.qwen/.reasonix/skills-lock.json 残留）

**状态**: ✅ 已完成（2026-08-29，死代码清理会话执行，与后端/前端死代码清理同批提交）

## 验收标准
- [x] 修复或删除主 docker/Dockerfile 的 electron 构建段（二选一记录理由）
  **决定: 删除**。electron/ 目录无 package.json（只有 main.js/preload.js/worker），该阶段从未可构建；
  Electron 打包由 build-windows.yml 在 Windows runner 上用 electron-builder 完成，不经 Docker。
  原阶段位置已留注释说明（docker/Dockerfile 阶段3前）。
- [x] 删除 k8s/、installers/、test_scripts/、Dockerfile.fpm、Dockerfile.arm64（git rm，保留 git 历史）
  **纠正**: Dockerfile.deb-complete **不删**——Makefile 的 build-deb-amd64/arm64/all 仍在引用，
  原工单此处为误判。现役 Dockerfile 已在阶段注释标注用途。
- [x] 现役 Dockerfile 头部注释标注（runtime 阶段前已注明来龙去脉）
- [x] 移除 .qwen/.reasonix/skills-lock.json/environment.yml（确认无人引用后）
  另一并删除: 根 mypy.ini（CI 实际用 backend/mypy.ini）、根 .bandit（实测 bandit
  不自动加载 CWD 的 .bandit，CI 用 backend/.bandit）、resources 死图标 17 个、
  build-scripts 死脚本 4 个、scripts/ 孤儿脚本 21 个、根 tests/ 孤例子目录 5 个 + 11 个一次性脚本
- [x] 全量测试绿（确保无脚本被 CI 引用）
  后端 pytest 全量 + 前端 vitest 全量 + 前后端 lint/typecheck/build 全部门禁通过。

## 附注
- data_sync/（根）为运行时目录（backend/app/api/v1/data_sync.py 以 CWD 相对路径使用），保留。
- resources/vcredist 被 gitignore 但 electron-builder 打包需要：新 clone 后需按文档补齐（见 Phase 5 文档同步）。
