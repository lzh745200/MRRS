#!/bin/bash
set -e

# 麒麟 V10 ARM64 构建脚本
# 产出: assistance-management-system_<version>_arm64.deb

echo "=========================================="
echo "  帮扶管理信息系统 - 麒麟 ARM64 DEB 构建"
echo "=========================================="

# 提取版本号
VERSION=$(grep -oP 'PROJECT_VERSION[^=]*=\s*"\K[^"]+' backend/app/core/config.py || echo "1.2.0")
echo "版本: $VERSION"

# 清理旧产物
rm -rf dist/deb/kylin
mkdir -p dist/deb/kylin

# 通过 Docker buildx 构建 ARM64 DEB 包
echo "步骤 1/2: 构建 ARM64 DEB 包..."
docker buildx build \
    --platform linux/arm64 \
    --build-arg VERSION="${VERSION}" \
    --target output \
    -t assistance-management-kylin:"${VERSION}" \
    -f docker/Dockerfile.kylin-standalone \
    --output type=local,dest=dist/deb/kylin \
    .

# 验证产物
echo "步骤 2/2: 验证 DEB 包..."
DEB_FILE="dist/deb/kylin/output/assistance-management-system_${VERSION}_arm64.deb"
if [ -f "$DEB_FILE" ]; then
    ls -lh "$DEB_FILE"
    file "$DEB_FILE"
    echo ""
    echo "=========================================="
    echo "构建完成！"
    echo "产物位置: $DEB_FILE"
    echo "=========================================="
else
    echo "ERROR: DEB 包未找到: $DEB_FILE"
    exit 1
fi
