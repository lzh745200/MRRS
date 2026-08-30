#!/bin/bash
# ========================================
# 前端构建产物同步脚本 (Linux/macOS)
# 将 frontend/dist/ 复制到 resources/frontend/
# 包含完整性校验：逐文件 SHA256 manifest 比对（偏差即退出非零）
# ========================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC_DIR="$PROJECT_ROOT/frontend/dist"
DST_DIR="$PROJECT_ROOT/resources/frontend"

echo "========================================"
echo "前端构建产物同步到 resources/frontend/"
echo "========================================"
echo ""
echo "源目录: $SRC_DIR"
echo "目标目录: $DST_DIR"
echo ""

# 1. 检查源目录是否存在
if [[ ! -f "$SRC_DIR/index.html" ]]; then
    echo "[错误] 源目录不存在或为空: $SRC_DIR"
    echo "请先执行: cd frontend && npm run build"
    exit 1
fi
echo "[OK] 源目录检查通过: $SRC_DIR"

# 2. 收集源目录文件信息
echo ""
echo "[1/4] 收集源目录文件信息..."
SRC_FILE_COUNT=$(find "$SRC_DIR" -type f | wc -l)
echo "源目录: $SRC_FILE_COUNT 个文件"

# 3. 强制清理目标目录（解决文件残留和占用问题）
echo ""
echo "[2/4] 清理目标目录..."
if [[ -d "$DST_DIR" ]]; then
    rm -rf "$DST_DIR" 2>/dev/null || {
        echo "[警告] 目标目录可能被占用，尝试重命名..."
        OLD_DIR="${DST_DIR}_old_$$"
        mv "$DST_DIR" "$OLD_DIR" 2>/dev/null || {
            echo "[错误] 无法清理目标目录，请关闭所有占用文件后重试"
            echo "可能占用文件的进程: python/uvicorn, electron, nginx"
            exit 1
        }
        # 后台异步删除旧目录（不阻塞构建流程）
        (sleep 10 && rm -rf "$OLD_DIR") &
    }
fi
mkdir -p "$DST_DIR"
echo "[OK] 目标目录已清理"

# 4. 复制文件
echo ""
echo "[3/4] 复制文件..."
cp -r "$SRC_DIR"/* "$DST_DIR/" 2>/dev/null || {
    echo "[错误] 文件复制失败"
    echo "请检查磁盘空间和文件权限"
    exit 1
}
echo "[OK] 文件复制完成"

# 5. 完整性校验：逐文件 SHA256 manifest 比对（W6-T5，替代原 du 字节数粗校验）
echo ""
echo "[4/4] 完整性校验（SHA256 manifest）..."

MANIFEST_FILE="$PROJECT_ROOT/resources/frontend-manifest.sha256"
MANIFEST_TMP="$(mktemp)"
DST_TMP="$(mktemp)"

# 以源目录为准生成 manifest（sha256sum -c 兼容格式：<hash>  <相对路径>）
# sed 归一化：去掉 GNU sha256sum 的二进制标记(*)与 find 的 ./ 前缀，
# 使输出与 verify_frontend_manifest.ps1（Windows 路径）格式完全一致
(
  cd "$SRC_DIR"
  find . -type f -print0 | sort -z | xargs -0 sha256sum \
    | sed -e 's/^\(.\{64\}\) \*\.\//\1  /' -e 's/^\(.\{64\}\)  \.\//\1  /'
) > "$MANIFEST_TMP"

(
  cd "$DST_DIR"
  find . -type f -print0 | sort -z | xargs -0 sha256sum \
    | sed -e 's/^\(.\{64\}\) \*\.\//\1  /' -e 's/^\(.\{64\}\)  \.\//\1  /'
) > "$DST_TMP"

SRC_FILE_COUNT=$(wc -l < "$MANIFEST_TMP" | tr -d ' ')
echo "比对文件数: $SRC_FILE_COUNT"

if ! diff -q "$MANIFEST_TMP" "$DST_TMP" > /dev/null; then
    echo "[错误] SHA256 manifest 比对失败！以下为差异（< 源 / > 目标）："
    diff "$MANIFEST_TMP" "$DST_TMP" | head -40
    rm -f "$MANIFEST_TMP" "$DST_TMP"
    echo "[错误] 同步失败：目标目录与源目录内容不一致"
    exit 1
fi
rm -f "$DST_TMP"

# manifest 落盘，供 scripts/audit_static_assets.py --verify-manifest 复核
mv "$MANIFEST_TMP" "$MANIFEST_FILE"
echo "[OK] 完整性校验通过 - $SRC_FILE_COUNT 个文件逐文件 SHA256 一致"
echo "[OK] manifest 已写入: $MANIFEST_FILE"

# 6. 验证关键文件
echo ""
echo "验证关键文件..."
MISSING_CRITICAL=0
if [[ ! -f "$DST_DIR/index.html" ]]; then
    echo "[错误] 关键文件缺失: index.html"
    MISSING_CRITICAL=1
fi
if [[ ! -d "$DST_DIR/assets" ]]; then
    echo "[错误] 关键目录缺失: assets/"
    MISSING_CRITICAL=1
fi

if [[ "$MISSING_CRITICAL" -eq 1 ]]; then
    echo "[错误] 关键文件缺失，同步失败！"
    exit 1
fi
echo "[OK] 所有关键文件验证通过"

echo ""
echo "========================================"
echo "同步完成！"
echo "========================================"
echo "文件数: $SRC_FILE_COUNT（已逐文件 SHA256 校验一致）"
echo "目标路径: $DST_DIR"
echo "manifest: $MANIFEST_FILE"
echo ""
echo "建议：运行 python scripts/audit_static_assets.py --verify-manifest $MANIFEST_FILE 复核"
echo "========================================"

exit 0
