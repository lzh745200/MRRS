# -*- coding: utf-8 -*-
"""诊断包导出 API（P0-7，2026-10-17）。

现场排障时，运维需要把「版本 / 迁移状态 / 数据库健康 / 日志尾部 / 资源快照」
一次性带回，而不是隔着电话逐个问用户要。本模块提供两个端点（**均仅管理员**）：

* ``GET /api/v1/system/diagnostics/summary`` —— 结构化诊断摘要（JSON）；
* ``GET /api/v1/system/diagnostics/bundle`` —— 诊断包 ZIP 下载（含 SHA256 校验单）。

安全边界（硬要求，改动时不得放宽）：

1. **仅管理员**：两个端点第一行 ``require_admin``；
2. **不携带任何凭据**：不输出配置项（``Settings`` 只取版本号这一个白名单字段），
   自然不包括 SECRET_KEY / ENCRYPTION_KEY / DATABASE_URL 等；
3. **日志与文本出站前脱敏**：手机号 / 身份证号 / 口令类键值对打码 ——
   日志里出现过 SQL 原文与用户输入，直接打包会把 PII 带出机器；
4. **异常只出境类名**（``type(exc).__name__``），不出原文：
   无认证的 ``/health`` 系列早已按此收敛，本模块沿用同一口径；
5. **导出动作写审计**（``write_work_log``），写审计失败也不阻断导出（但留日志）。

为什么端点是 **同步 ``def``**：``psutil.cpu_percent(interval>0)`` 是阻塞采样
（内部 sleep），在 ``async def`` 里直接调用会冻结事件循环；同步端点由 FastAPI
丢进线程池执行，阻塞是安全的（与 2026-09-03 工单的结论一致）。
"""

import hashlib
import io
import json
import logging
import os
import platform
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.permission_utils import require_admin
from app.core.response import success_response
from app.core.security import get_current_user
from app.services.work_log_service import write_work_log
from app.utils import paths

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["系统诊断"])

# 日志尾部行数上限（诊断包体积与信息量的折中：500 行 ≈ 100KB 级）
TAIL_LINES = 500
# 表行数清单的表数上限（防御性：正常部署远小于 300 张表）
MAX_TABLES = 300

# ── 脱敏规则 ────────────────────────────────────────────────────────────────
# 手机号：保留前 3 位（运营商可辨），其余打码。
# 用 (?<!\d)/(?!\d) 而不是 \b —— 中文日志里 "电话13812345678" 的中文与数字
# 都算 \w，\b 在它们之间不成立，实测会漏脱敏（2026-10-17 单测抓到）。
_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)\d{8}(?!\d)")
# 身份证号（18 位，末位可为 X）
_ID_CARD_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
# 口令/令牌类键值对：`password=xxx` / `"token": "xxx"` / `Authorization: Bearer xxx`
# 值取 1~2 个 token：`Authorization: Bearer <jwt>` 两段都要盖住。
_SECRET_KV_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|token|secret|access[_-]?key|api[_-]?key|authorization)\b"
    r"(\s*[\"']?\s*[:=]\s*[\"']?)"
    r"([^\s\"',]+(?:\s+[^\s\"',]+)?)"
)


def redact_text(raw: str) -> str:
    """诊断出站文本脱敏：手机号 / 身份证号 / 口令类键值对。"""
    masked = _PHONE_RE.sub(lambda m: m.group(1) + "*" * 8, raw)
    masked = _ID_CARD_RE.sub("*" * 18, masked)
    masked = _SECRET_KV_RE.sub(lambda m: m.group(1) + m.group(2) + "***", masked)
    return masked


def _safe_size(path: Optional[Path]) -> Optional[int]:
    """文件大小（不存在/不可读 → None，绝不抛）。"""
    if path is None:
        return None
    try:
        return path.stat().st_size
    except OSError:
        return None


def _resolve_log_file() -> Optional[Path]:
    """定位当前日志文件：Settings.LOG_FILE 优先，其次运行时日志目录。

    两者都可能为 None/不存在（打包环境路径由 Electron 注入），
    故返回 Optional 交给调用方降级。
    """
    candidates = [Path(settings.LOG_FILE), paths.get_log_path("app.log")]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:  # pragma: no cover - 极端非法路径（长度/权限）
            continue
    return None


def _tail_lines(path: Path, limit: int) -> list:
    """读文件尾部若干行（errors=replace：日志可能是混合编码）。"""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    return lines[-limit:]


def _runtime_db_path() -> Optional[Path]:
    """运行时数据库路径（以 DATABASE_URL 解析链为准，见 utils/paths.py）。"""
    try:
        return paths.get_database_path()
    except Exception as exc:  # noqa: BLE001 - 诊断不允许因路径解析失败而整体失败
        logger.warning("诊断：解析数据库路径失败（%s）", type(exc).__name__)
        return None


def _build_snapshot() -> dict:
    """构建信息（版本/git hash/构建时间/构建者）。"""
    try:
        from app.core.build_info import get_build_info

        info = get_build_info() or {}
    except Exception as exc:  # noqa: BLE001 - 体检单项失败降级为 error_type 返回，不中断整轮体检
        return {"error_type": type(exc).__name__}
    return {key: info.get(key) for key in ("version", "git_hash", "build_time", "builder")}


def _platform_snapshot() -> dict:
    """运行环境（不含主机名 —— 主机名可反查单位，诊断包要外发，不采集）。"""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_version": sys.version.split()[0],
        "frozen": bool(getattr(sys, "frozen", False)),
    }


def _migration_snapshot() -> dict:
    """Alembic 迁移状态（复用 main 的模块级状态，不重复跑迁移）。"""
    try:
        from app.main import _migration_status
    except Exception as exc:  # noqa: BLE001 - 体检单项失败降级为 error_type 返回，不中断整轮体检
        return {"error_type": type(exc).__name__}
    return {
        "at_head": _migration_status.get("at_head"),
        "head": _migration_status.get("head"),
        "error_type": _migration_status.get("error_type"),
    }


def _database_snapshot(db: Session, db_path: Optional[Path]) -> dict:
    """数据库健康：文件大小 / 完整性检查 / 各表行数（截断）。"""
    snapshot: dict = {
        "path": str(db_path) if db_path else None,
        "exists": bool(db_path is not None and db_path.is_file()),
        "size_bytes": _safe_size(db_path),
    }
    try:
        snapshot["integrity_check"] = str(db.execute(text("PRAGMA integrity_check")).scalar())
    except Exception as exc:  # noqa: BLE001 - 体检单项失败降级为 error_type 返回，不中断整轮体检
        snapshot["integrity_check"] = None
        snapshot["integrity_error_type"] = type(exc).__name__

    try:
        bind = db.get_bind()
        preparer = bind.dialect.identifier_preparer
        names = sorted(sa_inspect(bind).get_table_names())
        snapshot["table_count"] = len(names)
        snapshot["tables_truncated"] = len(names) > MAX_TABLES
        counts = {}
        for name in names[:MAX_TABLES]:
            # 表名取自 sqlite_master（不是用户输入），再经 dialect 的标识符引号器转义。
            # nosec 必须与 bandit 报出的**同一行**，写在上一行会被忽略并照旧报 B608
            # （2026-10-17 本地 bandit -ll 实测抓到）。
            quoted = preparer.quote(name)
            count_sql = text(f"SELECT COUNT(*) FROM {quoted}")  # nosec B608 - sqlite_master 表名 + dialect 引号器
            counts[name] = int(db.execute(count_sql).scalar() or 0)
        snapshot["tables"] = counts
    except Exception as exc:  # noqa: BLE001 - 体检单项失败降级为 error_type 返回，不中断整轮体检
        snapshot["tables"] = {}
        snapshot["tables_error_type"] = type(exc).__name__
    return snapshot


def _log_snapshot(log_file: Optional[Path]) -> dict:
    """日志文件概况。"""
    if log_file is None:
        return {"available": False}
    try:
        modified_at = datetime.fromtimestamp(log_file.stat().st_mtime, tz=timezone.utc).isoformat(
            timespec="seconds"
        )
    except OSError:
        modified_at = None
    return {
        "available": True,
        "file": str(log_file),
        "size_bytes": _safe_size(log_file),
        "modified_at": modified_at,
    }


def _resource_snapshot() -> dict:
    """资源快照（读不到就降级为 error_type，不拖垮整份诊断）。"""
    snapshot: dict = {"cpu_percent": None, "memory_percent": None, "disk_percent": None}
    try:
        import psutil

        snapshot["cpu_percent"] = psutil.cpu_percent(interval=0.2)
        snapshot["memory_percent"] = psutil.virtual_memory().percent
        # 跨平台取根分区：Windows 取系统盘（SystemDrive），Linux/麒麟取 "/"
        # （硬编码 "C:\\" 回退在麒麟上会直接 FileNotFoundError，2026-09-03 工单已收敛）
        root = os.environ.get("SystemDrive") or os.path.abspath(os.sep)
        snapshot["disk_percent"] = psutil.disk_usage(root).percent
    except Exception as exc:  # noqa: BLE001 - 体检单项失败降级为 error_type 返回，不中断整轮体检
        snapshot["error_type"] = type(exc).__name__
    return snapshot


def _business_snapshot(db: Session) -> dict:
    """业务运行状态（W18 P1-3）：备份 / 调度器 / 失败任务 / 数据包占用。

    原诊断包只有基础设施快照（版本/平台/迁移/数据库/日志/资源），现场最常问的
    三句答不出来：「昨晚备份成功了吗」「提醒为什么没发」「导入为什么失败」。
    本段补齐业务侧状态，并沿用既有的脱敏边界：只出**数量/时间/类型/类名**，
    不出异常原文、数据库路径与文件名。
    """
    business: dict = {}

    # ── 备份：最近一次时间 + 数量（失败与否看 last_backup_status）──
    try:
        from app.services.backup_service import BackupService

        backups = BackupService(db).list_backups()
        last = backups[0] if backups else None
        business["backup"] = {
            "count": len(backups),
            "last_backup_at": str(last.created_at) if last is not None else None,
            "last_backup_size_bytes": getattr(last, "file_size", None),
            "last_backup_type": getattr(last, "backup_type", None),
        }
    except Exception as exc:  # noqa: BLE001 - 诊断不允许因单段失败而整体失败
        business["backup"] = {"error_type": type(exc).__name__}

    # ── 调度器：是否在跑 + 已登记的周期任务 ──
    try:
        from app.services import backup_scheduler as sched

        timers = list(getattr(sched, "_timers", []))
        business["scheduler"] = {
            "started": bool(getattr(sched, "_scheduler_started", False)),
            "job_count": len(timers),
            "alive_count": sum(1 for t in timers if hasattr(t, "is_alive") and t.is_alive()),
            "jobs": sorted({t.name for t in timers if getattr(t, "name", None)}),
        }
    except Exception as exc:  # noqa: BLE001 - 体检单项失败降级为 error_type 返回，不中断整轮体检
        business["scheduler"] = {"error_type": type(exc).__name__}

    # ── 后台任务：失败数量与最近失败类型 ──
    try:
        from app.api.v1.system.tasks import get_tasks_diagnostics

        business["tasks"] = get_tasks_diagnostics()
    except Exception as exc:  # noqa: BLE001 - 体检单项失败降级为 error_type 返回，不中断整轮体检
        business["tasks"] = {"error_type": type(exc).__name__}

    # ── 数据包占用：导出目录体积（P1-6 保留策略的可见化）──
    try:
        from app.services.data_package_service import DataPackageService

        svc = DataPackageService(db)
        business["data_packages"] = {
            "export_dir_size_mb": round(svc.get_upload_dir_size() / (1024 * 1024), 2),
        }
    except Exception as exc:  # noqa: BLE001 - 体检单项失败降级为 error_type 返回，不中断整轮体检
        business["data_packages"] = {"error_type": type(exc).__name__}

    # ── PII 加密：密钥指纹 + 存量密文可解性 ──
    # 换机/重装后最典型的事故是"能登录、能看列表，但身份证号全是乱码"。
    # 指纹用于比对（不泄露密钥），可解性用启动预检的同一判据，避免两套口径。
    try:
        from app.core.pii_crypto import decrypt_failure_stats, key_fingerprint
        from app.startup.preflight import _check_encryption_key

        business["pii_encryption"] = {
            "key_fingerprint": key_fingerprint(),
            **_check_encryption_key(),
            # W18-offline P1-1：运行期解密失败累计（换机/重装后密钥漂移的事实证据）
            "decrypt_failures": decrypt_failure_stats(),
        }
    except Exception as exc:  # noqa: BLE001 - 体检单项失败降级为 error_type 返回，不中断整轮体检
        business["pii_encryption"] = {"error_type": type(exc).__name__}

    return business


def collect_diagnostics(db: Session) -> dict:
    """汇总一份完整诊断（summary 端点与 bundle 包共用同一份数据）。"""
    db_path = _runtime_db_path()
    log_file = _resolve_log_file()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": settings.PROJECT_VERSION,
        "build": _build_snapshot(),
        "platform": _platform_snapshot(),
        "database": _database_snapshot(db, db_path),
        "migration": _migration_snapshot(),
        "logs": _log_snapshot(log_file),
        "resources": _resource_snapshot(),
        "business": _business_snapshot(db),
    }


def _build_bundle_zip(summary: dict) -> bytes:
    """把诊断摘要 + 日志尾部打包为 ZIP（含 `sha256sum -c` 兼容的校验单）。"""
    files = {
        "summary.json": json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8"),
    }
    log_file = _resolve_log_file()
    if log_file is None:
        files["app.log.tail.missing"] = "未找到日志文件（LOG_FILE/LOG_DIR 可能未配置）".encode("utf-8")
    else:
        try:
            redacted = "".join(redact_text(line) for line in _tail_lines(log_file, TAIL_LINES))
            files["app.log.tail"] = redacted.encode("utf-8", errors="replace")
        except OSError as exc:
            files["app.log.tail.unreadable"] = type(exc).__name__.encode("utf-8")

    checksums = "".join(
        "%s  %s\n" % (hashlib.sha256(data).hexdigest(), name) for name, data in sorted(files.items())
    )
    files["checksums.txt"] = checksums.encode("utf-8")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _audit_export(db: Session, current_user) -> None:
    """导出动作写审计（失败不阻断导出，但必须留痕）。"""
    try:
        write_work_log(
            db,
            "system",
            "export",
            0,
            "diagnostics-bundle",
            user_id=getattr(current_user, "id", None),
            username=getattr(current_user, "username", ""),
            detail="导出系统诊断包",
        )
    except Exception as exc:  # noqa: BLE001 - 体检单项失败降级为 error_type 返回，不中断整轮体检
        logger.error("诊断包导出审计写入失败: %s", type(exc).__name__, exc_info=True)


@router.get("/summary", summary="诊断摘要（仅管理员）")
def diagnostics_summary(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回结构化诊断摘要（版本/迁移/数据库/日志/资源）。"""
    require_admin(current_user)
    return success_response(data=collect_diagnostics(db))


@router.get("/bundle", summary="诊断包下载（仅管理员）")
def diagnostics_bundle(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回诊断包 ZIP（summary.json + 脱敏日志尾部 + SHA256 校验单）。"""
    require_admin(current_user)
    payload = _build_bundle_zip(collect_diagnostics(db))
    _audit_export(db, current_user)
    filename = "diagnostics-%s.zip" % datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="%s"' % filename},
    )
