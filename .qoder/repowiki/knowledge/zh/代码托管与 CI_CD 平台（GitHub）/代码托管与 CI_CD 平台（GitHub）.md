---
kind: external_dependency
name: 代码托管与 CI/CD 平台（GitHub）
slug: github
category: external_dependency
category_hints:
    - vendor_identity
    - client_constraint
scope:
    - '**'
source_files:
    - .github/workflows/build-windows.yml
    - .github/workflows/build-arm64.yml
    - .github/workflows/pr-checks.yml
    - .github/workflows/nightly-full.yml
---

### GitHub
- 仓库地址：`git@github.com:lzh745200/MRRS.git`，作为代码托管、Release 产物发布与 CI 触发源。
- 触发条件：仅对 `refs/tags/v*` 标签触发 Windows x64 安装包构建（`build-windows.yml`）与 Linux ARM64 DEB 构建（`build-arm64.yml`），PR 走 `pr-checks.yml`，每日凌晨跑 `nightly-full.yml`。
- 产物发布：通过 `softprops/action-gh-release` 将 `dist/electron/*.exe`、`*.deb` 及对应 `SHA256SUMS-*` 清单上传至 Release；Windows 构建还可选用 `CSC_LINK` / `CSC_KEY_PASSWORD` secrets 进行 Authenticode 签名。
- 客户端约束：ARM64 DEB 必须经 CI 的 Docker Buildx + QEMU 交叉编译，本地无 QEMU/Docker 无法产出；Windows 安装包可本地 PyInstaller + electron-builder 构建。