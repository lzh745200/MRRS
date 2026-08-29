.PHONY: test test-backend test-frontend test-e2e test-e2e-docker coverage deploy-check clean \
        build-deb build-deb-amd64 build-deb-arm64 build-deb-all \
        docker-build docker-build-amd64 docker-build-arm64 docker-build-all \
        deb-clean \
        build-kylin build-kylin-arm64 kylin-clean \
        build-win-x64 build-win-x86 build-win-all

# 默认运行所有测试
test: test-backend test-frontend
	@echo "✓ 所有测试通过"

# 后端测试
test-backend:
	@echo ">>> 运行后端测试..."
	cd backend && python -m pytest tests/ -v --tb=short --cov=app --cov-fail-under=98

# 前端测试
test-frontend:
	@echo ">>> 运行前端测试..."
	cd frontend && npm run test:coverage

# E2E测试（请使用 Docker 模式）
test-e2e:
	@echo ">>> E2E 测试请使用: make test-e2e-docker"

# E2E Docker 测试（使用 Docker Compose 启动完整环境运行 E2E）
# 注意: assistance-system 服务定义于根 docker-compose.yml, 必须一并指定,
# 否则 overlay 的 depends_on 引用未定义服务直接报错; 不用 || true 掩盖失败
test-e2e-docker:
	@echo ">>> 启动 Docker E2E 测试环境..."
	docker compose -f docker-compose.yml -f docker/docker-compose.e2e.yml --profile e2e up -d --wait
	@echo ">>> 运行 E2E 测试 (Playwright)..."
	docker compose -f docker-compose.yml -f docker/docker-compose.e2e.yml --profile e2e up --abort-on-container-exit
	@echo ">>> 清理 Docker E2E 环境..."
	docker compose -f docker-compose.yml -f docker/docker-compose.e2e.yml --profile e2e down -v
	@echo "✓ E2E Docker 测试完成"

# 生成覆盖率报告（与 CI 同一 98% 门禁，防止本地报告掩盖达标缺口）
coverage:
	@echo ">>> 生成覆盖率报告..."
	cd backend && python -m pytest --cov=app --cov-report=html --cov-report=xml --cov-fail-under=98
	cd frontend && npm run test:coverage

# 部署前检查（W4-T2：每条命令独立阻断，禁止 || true 吞失败）
deploy-check:
	@echo ">>> 运行部署前检查..."
	# 后端：测试（98% 门禁真实阻断）→ flake8 → bandit
	cd backend && python -m pytest tests/ --cov=app --cov-fail-under=98 -q
	cd backend && python -m flake8 app/ --max-line-length=120
	cd backend && python -m bandit -r app/ -ll -f json -o bandit-report.json

	# 前端检查
	cd frontend && \
		npm run lint && \
		npm run type-check && \
		npm run test

	@echo "✓ 部署前检查通过"

# 安全扫描
security:
	@echo ">>> 运行安全扫描..."
	cd backend && \
		python -m bandit -r app/ -f json -o bandit-report.json && \
		pip-audit -r requirements.txt

# 清理测试产物（W4-T8：扩展根目录清理）
clean:
	@echo ">>> 清理测试产物..."
	cd backend && rm -rf .pytest_cache htmlcov coverage.xml .coverage __pycache__
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type f -name "*.pyc" -delete 2>/dev/null || true
	cd frontend && rm -rf coverage playwright-report test-results
	# 根目录 / frontend 遗留物
	-rm -f vitest-*.log vitest-*.json vitest-*.mjs test.db 2>/dev/null || true
	-find . -maxdepth 2 -name "vitest-*.log" -delete 2>/dev/null || true
	-find . -maxdepth 2 -name "vitest-*.json" -delete 2>/dev/null || true
	-find . -maxdepth 2 -name "test.db" -delete 2>/dev/null || true

# 安装依赖
install:
	@echo ">>> 安装依赖..."
	cd backend && pip install -r requirements.txt && pip install pytest pytest-cov pytest-asyncio
	cd frontend && npm ci

# 运行开发服务器
dev:
	@echo ">>> 启动开发服务器..."
	@echo "后端: http://localhost:8000"
	@echo "前端: http://localhost:5173"
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
	cd frontend && npm run dev

# 构建生产版本
build:
	@echo ">>> 构建生产版本..."
	cd frontend && npm run build
	@echo "✓ 构建完成"

# 打包 Electron
electron-build:
	@echo ">>> 打包 Electron 应用..."
	npx electron-builder --dir
	@echo "✓ Electron 打包完成"

# Windows 安装程序
win-installer: electron-build
	@echo ">>> 构建 Windows 安装程序..."
	npx electron-builder --win --x64
	@echo "✓ Windows 安装程序构建完成"

# ============================================================
# Windows 离线安装包构建（electron-builder + PyInstaller）
# 产物: dist/electron/帮扶管理系统-Setup-<version>.exe
# 依赖: 对应架构的 Python 3.11 + Node.js + 前端依赖
# ============================================================
WIN_OUTPUT_DIR := dist/electron
SYNC_FRONTEND := mkdir -p resources/frontend && cp -rf frontend/dist/* resources/frontend/

# 构建 Windows x64 离线安装包
build-win-x64:
	@echo "=== 构建 Windows x64 离线安装包 ==="
	@echo ">>> 构建前端..."
	cd frontend && npm run build
	@echo ">>> 同步前端到 resources/frontend..."
	@$(SYNC_FRONTEND)
	@echo ">>> PyInstaller 打包后端..."
	cd backend && python -m PyInstaller assistance-backend.spec --clean --noconfirm
	@echo ">>> 验证后端产物..."
	@test -f backend/dist/assistance-backend.exe && echo "  ✓ backend/dist/assistance-backend.exe" || (echo "  ✗ 后端 exe 未生成" && exit 1)
	@echo ">>> electron-builder 打包 (x64)..."
	npx electron-builder --win --x64
	@echo "=== x64 安装包构建完成 ==="
	@ls -lh $(WIN_OUTPUT_DIR)/*.exe 2>/dev/null || echo "  检查输出目录: $(WIN_OUTPUT_DIR)"

# 构建 Windows x86 离线安装包（需 32-bit Python 3.11）
build-win-x86:
	@echo "=== 构建 Windows x86 离线安装包 ==="
	@echo ">>> 构建前端..."
	cd frontend && npm run build
	@echo ">>> 同步前端到 resources/frontend..."
	@$(SYNC_FRONTEND)
	@echo ">>> PyInstaller 打包后端..."
	cd backend && python -m PyInstaller assistance-backend.spec --clean --noconfirm
	@echo ">>> 验证后端产物..."
	@test -f backend/dist/assistance-backend.exe && echo "  ✓ backend/dist/assistance-backend.exe" || (echo "  ✗ 后端 exe 未生成" && exit 1)
	@echo ">>> electron-builder 打包 (ia32)..."
	npx electron-builder --win --ia32
	@echo "=== x86 安装包构建完成 ==="
	@ls -lh $(WIN_OUTPUT_DIR)/*.exe 2>/dev/null || echo "  检查输出目录: $(WIN_OUTPUT_DIR)"

# 构建双架构安装包
build-win-all: build-win-x64 build-win-x86
	@echo "=== Windows x64 + x86 安装包全部构建完成 ==="

# ============================================================
# DEB 包构建（Docker 跨平台构建，推荐方式）
# ============================================================

VERSION := $(shell node -p "require('./package.json').version" 2>/dev/null || echo "1.5.0")
APP_NAME := assistance-management-system
OUTPUT_DIR := dist/deb

# Docker 构建 DEB (amd64)
docker-build-amd64:
	@echo "=== Docker 构建 DEB (amd64) ==="
	mkdir -p $(OUTPUT_DIR)
	docker buildx build \
		--platform linux/amd64 \
		--build-arg VERSION=$(VERSION) \
		-t $(APP_NAME)-deb:$(VERSION)-amd64 \
		-f docker/Dockerfile.deb-complete \
		--output type=local,dest=$(OUTPUT_DIR) \
		. 2>&1
	@echo ""
	@echo "=== 构建完成 ==="
	@if [ -f $(OUTPUT_DIR)/$(APP_NAME)_$(VERSION)_amd64.deb ]; then \
		echo "成功: $(OUTPUT_DIR)/$(APP_NAME)_$(VERSION)_amd64.deb"; \
		ls -lh $(OUTPUT_DIR)/$(APP_NAME)_$(VERSION)_amd64.deb; \
	else \
		echo "警告: DEB 文件可能未生成到 $(OUTPUT_DIR)"; \
		ls -lh $(OUTPUT_DIR)/ 2>/dev/null || true; \
	fi

# Docker 构建 DEB (arm64)
docker-build-arm64:
	@echo "=== Docker 构建 DEB (arm64) ==="
	mkdir -p $(OUTPUT_DIR)
	docker buildx build \
		--platform linux/arm64 \
		--build-arg VERSION=$(VERSION) \
		-t $(APP_NAME)-deb:$(VERSION)-arm64 \
		-f docker/Dockerfile.deb-complete \
		--output type=local,dest=$(OUTPUT_DIR) \
		. 2>&1
	@echo ""
	@echo "构建完成，输出到: $(OUTPUT_DIR)"

# Docker 构建（默认 amd64）
docker-build: docker-build-amd64

# Docker 多架构构建
docker-build-all:
	@echo "=== Docker 多架构构建 ==="
	@which docker-buildx > /dev/null || (echo "错误: 需要 docker-buildx" && exit 1)
	docker buildx create --use default 2>/dev/null || true
	mkdir -p $(OUTPUT_DIR)
	docker buildx build \
		--platform linux/amd64,linux/arm64 \
		--build-arg VERSION=$(VERSION) \
		-t $(APP_NAME)-deb:$(VERSION) \
		-f docker/Dockerfile.deb-complete \
		--output type=local,dest=$(OUTPUT_DIR) \
		--progress=plain \
		. 2>&1
	@echo ""
	@echo "=== 构建完成 ==="
	ls -lh $(OUTPUT_DIR)/*.deb 2>/dev/null || echo "检查输出目录: $(OUTPUT_DIR)"

# 简化目标
build-deb: docker-build-amd64
build-deb-amd64: docker-build-amd64
build-deb-arm64: docker-build-arm64
build-deb-all: docker-build-all

# 清理 DEB 构建产物
deb-clean:
	@echo "=== 清理 DEB 构建产物 ==="
	rm -rf $(OUTPUT_DIR)
	rm -rf backend/dist_x64 backend/dist_arm64 backend/dist_output
	rm -rf frontend/dist
	rm -rf pkg
	docker rmi $(APP_NAME)-deb:$(VERSION)-amd64 2>/dev/null || true
	docker rmi $(APP_NAME)-deb:$(VERSION)-arm64 2>/dev/null || true
	@echo "清理完成"

# ============================================================
# 麒麟 V10 ARM64 一体化单机版（无 Electron，纯 Web 架构）
# ============================================================
KYLIN_OUTPUT_DIR := dist/deb/kylin

# 构建麒麟 V10 ARM64 单机版 DEB
build-kylin-arm64:
	@echo "=== 构建麒麟 V10 ARM64 单机版 DEB ==="
	@echo "版本: $(VERSION)"
	@echo "架构: arm64 (aarch64)"
	@echo "模式: 无 Electron，纯 FastAPI + 系统浏览器"
	@echo ""
	@mkdir -p $(KYLIN_OUTPUT_DIR)
	docker buildx build \
		--platform linux/arm64 \
		--build-arg VERSION=$(VERSION) \
		-t $(APP_NAME)-kylin:$(VERSION) \
		-f docker/Dockerfile.kylin-standalone \
		--output type=local,dest=$(KYLIN_OUTPUT_DIR) \
		--progress=plain \
		. 2>&1
	@echo ""
	@echo "=== 构建完成 ==="
	@if [ -f $(KYLIN_OUTPUT_DIR)/$(APP_NAME)_$(VERSION)_arm64.deb ]; then \
		echo "成功: $(KYLIN_OUTPUT_DIR)/$(APP_NAME)_$(VERSION)_arm64.deb"; \
		ls -lh $(KYLIN_OUTPUT_DIR)/$(APP_NAME)_$(VERSION)_arm64.deb; \
		sha256sum $(KYLIN_OUTPUT_DIR)/$(APP_NAME)_$(VERSION)_arm64.deb; \
	else \
		echo "警告: DEB 文件可能未生成到 $(KYLIN_OUTPUT_DIR)"; \
		ls -lh $(KYLIN_OUTPUT_DIR)/ 2>/dev/null || true; \
	fi

# 简化别名
build-kylin: build-kylin-arm64

# 清理麒麟构建产物
kylin-clean:
	@echo "=== 清理麒麟 V10 构建产物 ==="
	rm -rf $(KYLIN_OUTPUT_DIR)
	rm -rf backend/dist/assistance-management-backend
	rm -rf backend/build
	docker rmi $(APP_NAME)-kylin:$(VERSION) 2>/dev/null || true
	@echo "清理完成"

# 帮助信息
help:
	@echo "帮扶管理信息系统 - Makefile"
	@echo ""
	@echo "可用目标:"
	@echo "  make test         - 运行所有测试（后端 + 前端）"
	@echo "  make test-backend - 运行后端测试"
	@echo "  make test-frontend- 运行前端测试"
	@echo "  make test-e2e     - 运行 E2E 测试"
	@echo "  make test-e2e-docker - Docker E2E 测试（完整环境）"
	@echo "  make coverage     - 生成覆盖率报告"
	@echo "  make deploy-check - 运行部署前检查"
	@echo "  make security     - 运行安全扫描"
	@echo "  make clean        - 清理测试产物"
	@echo "  make install      - 安装所有依赖"
	@echo "  make dev          - 启动开发服务器"
	@echo "  make build        - 构建生产版本"
	@echo "  make electron-build - 打包 Electron 应用"
	@echo "  make win-installer  - 构建 Windows 安装程序"
	@echo ""
	@echo "Windows 离线安装包（electron-builder + PyInstaller）:"
	@echo "  make build-win-x64  - 构建 x64 离线安装包"
	@echo "  make build-win-x86  - 构建 x86 离线安装包"
	@echo "  make build-win-all  - 构建双架构安装包"
	@echo ""
	@echo "DEB 包构建（Docker 跨平台，推荐）:"
	@echo "  make build-deb           - 构建 amd64 DEB"
	@echo "  make build-deb-amd64     - 构建 amd64 DEB"
	@echo "  make build-deb-arm64     - 构建 arm64 DEB"
	@echo "  make build-deb-all       - 构建双架构 DEB"
	@echo "  make deb-clean           - 清理 DEB 构建产物"
	@echo ""
	@echo "麒麟 V10 ARM64 单机版（无 Electron）:"
	@echo "  make build-kylin         - 构建麒麟 V10 ARM64 DEB"
	@echo "  make build-kylin-arm64   - 同上"
	@echo "  make kylin-clean         - 清理麒麟构建产物"
	@echo ""
	@echo "示例:"
	@echo "  make build-deb VERSION=1.0.4"
	@echo "  make build-deb-all VERSION=1.0.5"
	@echo ""

# 独立版 DEB (amd64)：与 kylin 同源 Dockerfile，平台改 amd64（无 QEMU，速度快）
# 用法：make build-deb-standalone-amd64 VERSION=1.10.0
build-deb-standalone-amd64:
	@mkdir -p $(KYLIN_OUTPUT_DIR)
	docker buildx build \
		--platform linux/amd64 \
		--build-arg VERSION=$(VERSION) \
		-t $(APP_NAME)-kylin:$(VERSION)-amd64 \
		-f docker/Dockerfile.kylin-amd64 \
		--output type=local,dest=$(KYLIN_OUTPUT_DIR) \
		--progress=plain \
		. 2>&1
