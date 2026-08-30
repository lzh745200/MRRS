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

**追记（2026-08-30 晚，v1.11.0 真机安装失败复盘）**:
安装期哈希校验上线后在真机产生假阳性中止。两层根因：
1. **NSIS C 风格转义**：双引号字符串内 `\r`/`\v`/`\n` 会被真实转换——
   路径 `$INSTDIR\resources\vcredist\...` 实际传出 CR/VT 损坏字符，
   Get-FileHash 恒定报错 exit 1，被误判为"哈希不匹配"。修复：路径反斜杠
   全部 `\\`；本文件新增"NSIS 转义铁律"注释。
2. **行内 -Command 脆弱**：PS 行内脚本要过 NSIS/命令行/PS 多层解析。修复：
   安装时以 FileWrite 写出 .ps1 后 `-File` 执行（异常自行落盘
   verify_*.err.txt 供诊断），执行后删除脚本。
校验语义改为三态：0=匹配静默安装；1=确证不匹配弹窗中止（/SD IDOK）；
3 或 error=校验基础设施不可用 → 跳过 redist 安装但不阻断部署
（不执行无法校验的二进制，应用由 Layer 1 PyInstaller 捆绑 DLL 兜底）。
本机全链路实测：静默安装 exit 0、哈希校验通过、redist 执行、快捷方式
创建（perMachine 下在公共桌面）、静默卸载零残留。
