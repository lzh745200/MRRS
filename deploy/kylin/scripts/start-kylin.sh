#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  帮扶管理信息系统 - 麒麟 V10 桌面启动入口
#  由 .desktop 文件调用，负责启动服务并打开浏览器
# ═══════════════════════════════════════════════════════════════

# 注意：不使用 set -e，允许优雅处理错误
APP_NAME="assistance-management-system"
SERVICE_NAME="${APP_NAME}.service"
HEALTH_URL="http://127.0.0.1:8000/health"
BROWSER_URL="http://127.0.0.1:8000"
MAX_WAIT=60  # 最大等待秒数（首次启动数据库初始化可能较慢）

# ── 工具函数 ──
log()  { echo "[启动] $1"; }
warn() { echo "[警告] $1"; }
err()  { echo "[错误] $1" >&2; }

# 桌面通知（如果可用）
notify() {
    local msg="$1"
    local icon="${2:-dialog-warning}"
    if command -v notify-send &>/dev/null; then
        notify-send -i "$icon" "帮扶管理信息系统" "$msg" 2>/dev/null
    elif command -v zenity &>/dev/null; then
        zenity --info --text="$msg" --title="帮扶管理信息系统" 2>/dev/null &
    fi
}

# ── 健康检查（零外部依赖：curl/wget 缺失时回退 bash /dev/tcp）──
health_ok() {
    if command -v curl &>/dev/null; then
        curl -sf "$HEALTH_URL" > /dev/null 2>&1
    elif command -v wget &>/dev/null; then
        wget -q -O /dev/null "$HEALTH_URL" 2>/dev/null
    else
        # bash 内建：/dev/tcp 探测端口可达即可（DEB 未打包 curl，麒麟最小安装常缺失）
        (exec 3<>"/dev/tcp/127.0.0.1/8000") 2>/dev/null && exec 3>&- 3<&-
    fi
}

# ── 直接启动回退函数 ──
_direct_start() {
    local BACKEND="/opt/assistance-management-system/backend/assistance-management-backend"
    if [ -x "$BACKEND" ]; then
        log "直接启动后端二进制（非 systemd 模式）..."
        cd /opt/assistance-management-system
        export FRONTEND_DIST_PATH=/opt/assistance-management-system/frontend
        # 数据/日志目录可能归 root 所有且组不可写（postinst 750）——
        # 桌面用户直接启动时降级到 $HOME，避免 SQLite/日志打开失败导致回退路径也起不来
        local DATA_DIR=/var/lib/assistance-management-system
        local LOG_BASE=/var/log/assistance-management-system
        if ! [ -w "$DATA_DIR" ] || ! [ -w "$LOG_BASE" ]; then
            DATA_DIR="$HOME/.assistance-management-system"
            LOG_BASE="$DATA_DIR/logs"
            mkdir -p "$DATA_DIR/database" "$DATA_DIR/uploads" "$DATA_DIR/exports" \
                     "$DATA_DIR/cache" "$DATA_DIR/backups" "$LOG_BASE" 2>/dev/null
            log "系统目录不可写，数据目录降级为: $DATA_DIR"
        fi
        export DATABASE_URL="sqlite:///$DATA_DIR/database/rural_revitalization.db"
        export UPLOAD_DIR="$DATA_DIR/uploads"
        export EXPORT_DIR="$DATA_DIR/exports"
        export CACHE_DIR="$DATA_DIR/cache"
        export BACKUP_DIR="$DATA_DIR/backups"
        export LOG_DIR="$LOG_BASE"
        export LOG_FILE="$LOG_BASE/app.log"
        export HOST=127.0.0.1
        export PORT=8000
        exec "$BACKEND"
    else
        err "后端可执行文件不存在: $BACKEND"
        err "请重新安装: sudo dpkg -i assistance-management-system_*.deb"
        notify "后端程序未找到，请重新安装软件包" "dialog-error"
        exit 1
    fi
}

# ── 1. 启动 systemd 服务 ──
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    log "后端服务已在运行"
else
    log "正在启动后端服务..."
    SERVICE_STARTED=false

    # 方式1: 直接 systemctl start（polkit 规则允许免密启动）
    if systemctl start "$SERVICE_NAME" 2>/dev/null; then
        SERVICE_STARTED=true
        log "服务已通过 systemctl 启动"
    # 方式2: pkexec（弹出图形化密码框）
    elif command -v pkexec &>/dev/null; then
        if pkexec systemctl start "$SERVICE_NAME" 2>/dev/null; then
            SERVICE_STARTED=true
            log "服务已通过 pkexec 启动"
        fi
    fi

    # 方式3: 直接启动二进制（最终回退）
    if [ "$SERVICE_STARTED" = "false" ]; then
        warn "无法通过 systemd 启动服务，尝试直接启动后端..."
        _direct_start &
    fi
fi

# ── 2. 等待服务就绪 ──
log "等待服务就绪..."
SERVICE_READY=false
for i in $(seq 1 $MAX_WAIT); do
    if health_ok; then
        log "服务已就绪（耗时 ${i}s）"
        SERVICE_READY=true
        break
    fi

    # 检查服务是否已崩溃（systemd 模式下）
    if [ "$SERVICE_STARTED" = "true" ] 2>/dev/null; then
        if ! systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
            # 服务已停止，可能崩溃了
            if [ $i -gt 5 ]; then
                err "服务启动后立即崩溃，可能存在兼容性问题"
                err "请查看日志: sudo journalctl -u $APP_NAME -n 50 --no-pager"
                notify "服务启动失败，请查看系统日志\nsudo journalctl -u $APP_NAME -n 50" "dialog-error"
                exit 1
            fi
        fi
    fi

    sleep 1
done

if [ "$SERVICE_READY" = "false" ]; then
    err "服务启动超时（${MAX_WAIT}s），请检查日志:"
    err "  sudo journalctl -u $APP_NAME -n 50 --no-pager"
    err "  或查看: tail -50 /var/log/assistance-management-system/app.log"
    notify "服务启动超时，请查看系统日志" "dialog-error"
    exit 1
fi

# ── 3. 打开浏览器 ──
log "正在打开浏览器..."

_open_browser() {
    local url="$1"
    # 按优先级尝试各浏览器
    for browser in kylin-browser chromium-browser chromium firefox-esr firefox google-chrome; do
        if command -v "$browser" &>/dev/null; then
            log "使用浏览器: $browser"
            "$browser" "$url" &>/dev/null &
            return 0
        fi
    done
    # 回退: xdg-open
    if command -v xdg-open &>/dev/null; then
        xdg-open "$url" &>/dev/null &
        return 0
    fi
    # 最终回退: 通知用户
    warn "未找到浏览器，请手动打开浏览器访问: $url"
    notify "系统已启动，请手动打开浏览器访问:\n$url" "dialog-information"
    return 1
}

_open_browser "$BROWSER_URL"

log "系统已启动"
log "访问地址: $BROWSER_URL"
log "关闭服务: sudo systemctl stop $APP_NAME"
