---
labels: [done, severity-critical]
blocks: []
blocked-by: []
---

# W6-T2 vcredist 移出 git 改 CI 拉取 + SHA256 固定

**来源**: 检测 S2（37.7MB 二进制入库、NSIS 管理员静默执行无校验）

**完成（2026-08-30，commit 9d87f560）**: 钉扎常量唯一维护点为
`build-scripts/electron-builder-nsis-hook.nsh` 头部 `!define` 段；
拉取脚本 `scripts/build/fetch_vcredist.ps1`（CI 9.6 步 + Makefile fetch-vcredist
共用，两条路径均实测通过）；NSIS 钩子安装期 Get-FileHash 复核、不匹配弹窗中止
（makensis 编译验证通过）；本地指引写入 build-scripts/README.md 与构建打包指南。
注：工单原文提到的 build_windows_complete.bat 已在 W6-T8 清理中删除，
本地构建路径现为 Makefile。

## 验收标准
- [x] workflow 构建起点从微软官方固定 URL 下载 vc_redist.{x64,x86}.exe 并比对内置 SHA256
- [x] `git rm --cached resources/vcredist/*.exe`；.gitignore 生效确认
- [x] NSIS 钩子在哈希不匹配时中止安装
- [x] 本地构建路径（build_windows_complete.bat）同样支持下载逻辑或给出明确指引
