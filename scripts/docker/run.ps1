# ============================================================
# run.ps1 - Windows Docker 运行脚本
# ============================================================

param(
    [string]$Tag = "arm64",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  帮扶管理信息系统 - 启动服务" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 停止旧容器
Write-Host "`n停止旧容器..." -ForegroundColor Yellow
docker stop assistance-system -ErrorAction SilentlyContinue
docker rm assistance-system -ErrorAction SilentlyContinue

# 创建必要目录
New-Item -ItemType Directory -Force -Path "data" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

# 检查镜像是否存在
$imageExists = docker images assistance-system:$Tag -q
if (-not $imageExists) {
    Write-Host "镜像不存在，开始构建..." -ForegroundColor Yellow
    .\build.ps1
}

# 启动容器
Write-Host "`n启动容器..." -ForegroundColor Yellow
docker run -d `
    --name assistance-system `
    -p $BackendPort`:8000 `
    -p $FrontendPort`:3000 `
    -v ${PWD}/data:/app/data `
    -v ${PWD}/logs:/app/logs `
    --restart unless-stopped `
    assistance-system:$Tag

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 启动失败！" -ForegroundColor Red
    exit 1
}

# 等待启动
Write-Host "等待服务启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 查看状态
Write-Host "`n容器状态:" -ForegroundColor Yellow
docker ps --filter name=assistance-system

# 查看日志
Write-Host "`n服务日志:" -ForegroundColor Yellow
docker logs assistance-system --tail=20

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "  ✅ 服务已启动！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "访问地址:"
Write-Host "  前端: http://localhost:$FrontendPort"
Write-Host "  后端: http://localhost:$BackendPort"
Write-Host "  API 文档: http://localhost:$BackendPort/docs"
Write-Host ""
Write-Host "默认账号: admin /（首次启动时设置密码）"
Write-Host ""
Write-Host "常用命令:"
Write-Host "  查看日志: docker logs -f assistance-system"
Write-Host "  停止服务: docker stop assistance-system"
Write-Host "  进入容器: docker exec -it assistance-system /bin/bash"
Write-Host "==========================================" -ForegroundColor Cyan
