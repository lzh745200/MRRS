---
labels: [ready-for-agent, severity-critical]
blocks: []
blocked-by: []
---

# W6-T2 vcredist 移出 git 改 CI 拉取 + SHA256 固定

**来源**: 检测 S2（37.7MB 二进制入库、NSIS 管理员静默执行无校验）

## 验收标准
- [ ] workflow 构建起点从微软官方固定 URL 下载 vc_redist.{x64,x86}.exe 并比对内置 SHA256
- [ ] `git rm --cached resources/vcredist/*.exe`；.gitignore 生效确认
- [ ] NSIS 钩子在哈希不匹配时中止安装
- [ ] 本地构建路径（build_windows_complete.bat）同样支持下载逻辑或给出明确指引
