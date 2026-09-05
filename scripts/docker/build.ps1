# ============================================================
# build.ps1 - Windows Docker 构建脚本
# ============================================================

param(
    [string]$Version = "1.11.5",
    [string]$Tag = "arm64"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  帮扶管理信息系统 - Windows Docker 构建" -ForegroundColor Cyan
Write-Host "  版本: $Version" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 检查 Docker 是否运行
Write-Host "`n步骤 1/6: 检查 Docker 状态..." -ForegroundColor Yellow
try {
    docker info
} catch {
    Write-Host "错误: Docker 未运行！请启动 Docker Desktop" -ForegroundColor Red
    exit 1
}

# 创建必要目录
Write-Host "`n步骤 2/6: 创建必要目录..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "data" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
New-Item -ItemType Directory -Force -Path "backups" | Out-Null
New-Item -ItemType Directory -Force -Path "config" | Out-Null
Write-Host "✅ 目录创建完成" -ForegroundColor Green

# 清理旧镜像
Write-Host "`n步骤 3/6: 清理旧镜像..." -ForegroundColor Yellow
docker rmi assistance-system:$Tag -ErrorAction SilentlyContinue
Write-Host "✅ 清理完成" -ForegroundColor Green

# 构建镜像
Write-Host "`n步骤 4/6: 构建 Docker 镜像（这可能需要 10-20 分钟）..." -ForegroundColor Yellow
docker build -f docker/Dockerfile -t assistance-system:$Tag .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 构建失败！" -ForegroundColor Red
    exit 1
}
Write-Host "✅ 构建完成" -ForegroundColor Green

# 查看镜像
Write-Host "`n步骤 5/6: 查看镜像信息..." -ForegroundColor Yellow
docker images assistance-system:$Tag

# 导出镜像
Write-Host "`n步骤 6/6: 导出镜像..." -ForegroundColor Yellow
docker save assistance-system:$Tag -o assistance-system-$Tag.tar
Write-Host "✅ 镜像已导出: assistance-system-$Tag.tar" -ForegroundColor Green

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "  ✅ 构建完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "运行方式:"
Write-Host "  1. 直接运行: docker run -p 8000:8000 -p 3000:3000 assistance-system:$Tag"
Write-Host "  2. 使用 compose: docker-compose up -d"
Write-Host "  3. 运行脚本: .\run.ps1"
Write-Host ""
Write-Host "默认账号: admin /（首次启动时设置密码）"
Write-Host "访问地址: http://localhost:8000"
Write-Host "==========================================" -ForegroundColor Cyan
