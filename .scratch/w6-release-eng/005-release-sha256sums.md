---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# W6-T5 Release 产物完整性链（SHA256SUMS）

**来源**: 检测建议6（军队分发最低要求；sync 脚本仅 du 字节数比对且 >5% 只警告不退出）

**完成（2026-08-30）**:
- 三个发布产物族各生成独立命名的 SHA256 清单（避免同一 Release 内同名覆盖）：
  - build-windows.yml → `SHA256SUMS-windows-x64.txt`（pwsh Get-FileHash，UTF-8 无 BOM
    保持 sha256sum -c 兼容；随 artifact 上传并附到 Release，Release 说明附校验指引）
  - build-arm64.yml build-electron-deb → `SHA256SUMS-electron-deb-arm64.txt`
  - build-arm64.yml standalone-deb → `SHA256SUMS-standalone-deb-arm64.txt`
- sync-frontend-dist.sh：du 字节粗校验（5% 仅警告）改为逐文件 SHA256 manifest 比对，
  任何缺失/多出/哈希偏差即 exit 1；manifest 落盘
  `resources/frontend-manifest.sha256`（sha256sum -c 兼容格式，已做二进制标记与
  `./` 前缀归一化，与 Windows 路径输出格式一致）。
- sync-frontend-dist.bat（.sh 孪生）：同步改为调用新抽取的
  `scripts/build/verify_frontend_manifest.ps1` 校验核心（同格式 manifest）。
- audit_static_assets.py 新增 `--verify-manifest <path>` 模式：逐文件复核落盘
  manifest，缺失/哈希不匹配/多出文件均退出非零。
- 验证：沙箱三连测（同步落盘格式 / 审计通过 / 篡改检出 exit 1）+ ps1 核心
  匹配与失配两路径 + 真实仓库 bat 同步 623 文件 → audit --verify-manifest 全一致
  exit 0。两个 workflow YAML 解析通过，bash -n / flake8（scripts 不在 CI 门禁，
  C901 为存量且与本次无关）通过。

## 验收标准
- [x] 两个 build workflow 在 Release 前生成 SHA256SUMS.txt 一并上传（3 个产物族独立命名清单）
- [x] sync-frontend-dist.sh 改为 SHA256 manifest 校验，偏差即退出非零
- [x] audit_static_assets.py 补哈希校验能力（--verify-manifest 模式）
