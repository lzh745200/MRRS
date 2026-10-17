#!/bin/bash
# 帮扶管理信息系统 - 开发环境初始化 (Linux/麒麟)
set -e

echo "========================================"
echo "  帮扶管理信息系统 - 开发环境初始化"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ── 1. Python ──
echo "[1/4] 初始化 Python 虚拟环境..."
cd "$PROJECT_DIR/backend"
python3.11 -m venv .venv 2>/dev/null || python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
echo "[OK] Python 依赖安装完成"

# ── 2. Frontend ──
echo "[2/4] 安装前端依赖..."
cd "$PROJECT_DIR/frontend"
npm install --legacy-peer-deps --registry=https://registry.npmmirror.com
echo "[OK] 前端依赖安装完成"

# ── 3. Hooks ──
echo "[3/4] 安装 Git hooks..."
cd "$PROJECT_DIR"
pip install pre-commit -q
pre-commit install
echo "[OK] Pre-commit hooks 已安装"

# ── 4. Config ──
echo "[4/4] 检查环境配置..."
[ ! -f "$PROJECT_DIR/backend/.env" ] && cp "$PROJECT_DIR/backend/.env.example" "$PROJECT_DIR/backend/.env" && echo "  backend/.env 已创建"
[ ! -f "$PROJECT_DIR/frontend/.env" ] && cp "$PROJECT_DIR/frontend/.env.example" "$PROJECT_DIR/frontend/.env" && echo "  frontend/.env 已创建"

echo ""
echo "========================================"
echo "  初始化完成!"
echo "========================================"
echo ""
echo "启动开发环境:"
echo "  cd backend && source .venv/bin/activate && python start.py"
echo "  cd frontend && npm run dev"
echo ""
echo "默认账号: admin / zgcZGC733035#  (出厂口令，首次登录强制改密；可用 DEFAULT_ADMIN_PASSWORD 覆盖)"
echo "API 文档: http://localhost:8000/docs"
