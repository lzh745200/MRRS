"""系统健壮性 API — SQLite WAL检查点、完整性校验、磁盘空间监控、表统计"""

import logging
import os
import shutil
import time
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success_response
from app.core.permission_utils import require_admin
from app.core.security import get_current_user
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system-health", tags=["系统健壮性"])

# ==================== 系统概览 ====================


@router.get("/overview")
async def get_system_overview(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取系统整体健康状态"""
    checks = {}

    # 1. 数据库连接
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "message": "数据库连接正常"}
    except Exception as e:
        checks["database"] = {"status": "error", "message": f"数据库连接异常: {str(e)}"}

    # 2. 磁盘空间
    disk = _check_disk_space()
    checks["disk"] = disk

    # 3. 数据库文件大小
    db_info = _get_db_file_info(db)
    checks["db_file"] = db_info

    # 4. WAL 文件状态
    wal_info = _check_wal_status(db)
    checks["wal"] = wal_info

    # 总体状态
    statuses = [v["status"] for v in checks.values()]
    if "error" in statuses:
        overall = "error"
    elif "warning" in statuses:
        overall = "warning"
    else:
        overall = "ok"

    return success_response(
        data={
            "overall_status": overall,
            "checks": checks,
            "timestamp": datetime.now().isoformat(),
        }
    )


# ==================== SQLite 完整性校验 ====================


@router.post("/integrity-check")
async def run_integrity_check(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """执行 SQLite 完整性校验（PRAGMA integrity_check）+ 索引数量校验"""
    require_admin(current_user, error_message="仅管理员可执行数据库维护操作")
    start = time.time()
    try:
        result = db.execute(text("PRAGMA integrity_check")).fetchall()
        elapsed = round(time.time() - start, 2)

        messages = [row[0] for row in result]
        is_ok = len(messages) == 1 and messages[0] == "ok"

        # 索引数量校验：比对预期索引与实际索引
        warnings = []
        try:
            from app.core.database_indexes import EXTRA_INDEXES

            expected_custom_indexes = set()
            # 深审 #95：EXTRA_INDEXES 元组顺序为 (表名, 索引名, 列)，原实现取第一个
            # 元素（表名）当索引名比对，missing 恒非空 → 每次完整性检查都误报缺索引。
            for _table, idx_name, _columns in EXTRA_INDEXES:
                expected_custom_indexes.add(idx_name)

            # 获取实际索引
            actual_indexes = set()
            tables = db.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            ).fetchall()
            for (tbl,) in tables:
                idx_rows = db.execute(text(f'PRAGMA index_list("{tbl}")')).fetchall()
                for idx_row in idx_rows:
                    actual_indexes.add(idx_row[1])  # index name

            # 比对差异
            missing = expected_custom_indexes - actual_indexes
            if missing:
                warnings.append(f"缺少预期索引: {', '.join(sorted(missing))}")
        except Exception as idx_err:
            logger.warning("索引数量校验失败: %s", idx_err)

        return success_response(
            data={
                "status": "ok" if is_ok else "error",
                "messages": messages,
                "warnings": warnings,
                "elapsed_seconds": elapsed,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return success_response(
            data={
                "status": "error",
                "messages": [str(e)],
                "warnings": [],
                "elapsed_seconds": round(time.time() - start, 2),
                "timestamp": datetime.now().isoformat(),
            }
        )


# ==================== WAL 检查点 ====================


@router.post("/wal-checkpoint")
async def run_wal_checkpoint(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """执行 WAL 检查点操作（PRAGMA wal_checkpoint）"""
    require_admin(current_user, error_message="仅管理员可执行数据库维护操作")
    try:
        before_wal = _check_wal_status(db)
        result = db.execute(text("PRAGMA wal_checkpoint(TRUNCATE)")).fetchone()
        after_wal = _check_wal_status(db)

        return success_response(
            data={
                "status": "ok",
                "result": {
                    "busy": result[0] if result else None,
                    "log_pages": result[1] if result else None,
                    "checkpointed_pages": result[2] if result else None,
                },
                "before": before_wal,
                "after": after_wal,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return success_response(
            data={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )


# ==================== 磁盘空间监控 ====================


@router.get("/disk-space")
async def get_disk_space(
    current_user=Depends(get_current_user),
):
    """获取磁盘空间详情"""
    return success_response(data=_check_disk_space())


# ==================== 数据库表统计 ====================


@router.get("/table-stats")
async def get_table_stats(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取各表记录数统计"""
    tables = db.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    ).fetchall()

    stats = []
    total_rows = 0
    for (table_name,) in tables:
        try:
            count = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()  # nosec B608 — sqlite_master 系统表名
            stats.append({"table": table_name, "rows": count})
            total_rows += count
        except Exception:
            stats.append({"table": table_name, "rows": -1, "error": True})

    return success_response(data={"tables": stats, "total_tables": len(stats), "total_rows": total_rows})


# ==================== VACUUM（数据库压缩） ====================


@router.post("/vacuum")
async def run_vacuum(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """执行 VACUUM 压缩数据库（可能耗时较长）"""
    require_admin(current_user, error_message="仅管理员可执行数据库维护操作")
    db_info_before = _get_db_file_info(db)
    start = time.time()
    try:
        db.execute(text("VACUUM"))
        safe_commit(db)
        elapsed = round(time.time() - start, 2)
        db_info_after = _get_db_file_info(db)
        saved = db_info_before.get("size_mb", 0) - db_info_after.get("size_mb", 0)
        return success_response(
            data={
                "status": "ok",
                "before_size_mb": db_info_before.get("size_mb"),
                "after_size_mb": db_info_after.get("size_mb"),
                "saved_mb": round(saved, 2),
                "elapsed_seconds": elapsed,
            }
        )
    except Exception as e:
        return success_response(
            data={
                "status": "error",
                "message": str(e),
                "elapsed_seconds": round(time.time() - start, 2),
            }
        )


# ==================== 内部函数 ====================


def _check_disk_space() -> dict:
    """检查数据库所在磁盘空间"""
    try:
        # 获取当前工作目录所在磁盘
        cwd = os.getcwd()
        usage = shutil.disk_usage(cwd)
        free_gb = round(usage.free / (1024**3), 2)
        total_gb = round(usage.total / (1024**3), 2)
        used_pct = round((usage.used / usage.total) * 100, 1)

        status = "ok"
        message = f"可用 {free_gb}GB / 共 {total_gb}GB"
        if free_gb < 1:
            status = "error"
            message = f"磁盘空间严重不足! 仅剩 {free_gb}GB"
        elif free_gb < 5:
            status = "warning"
            message = f"磁盘空间不足，仅剩 {free_gb}GB"

        return {
            "status": status,
            "message": message,
            "free_gb": free_gb,
            "total_gb": total_gb,
            "used_percent": used_pct,
        }
    except Exception as e:
        return {"status": "error", "message": f"无法获取磁盘信息: {str(e)}"}


def _get_db_file_info(db: Session) -> dict:
    """获取数据库文件信息"""
    try:
        db_path_row = db.execute(text("PRAGMA database_list")).fetchone()
        if db_path_row and len(db_path_row) >= 3:
            db_path = db_path_row[2]
            if db_path and os.path.exists(db_path):
                size = os.path.getsize(db_path)
                mtime = os.path.getmtime(db_path)
                return {
                    "status": "ok",
                    "path": db_path,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "last_modified": datetime.fromtimestamp(mtime).isoformat(),
                    "message": f"数据库文件 {round(size / (1024 * 1024), 2)}MB",
                }
        return {"status": "ok", "message": "内存数据库或路径未知", "size_mb": 0}
    except Exception as e:
        return {
            "status": "warning",
            "message": f"无法获取文件信息: {str(e)}",
            "size_mb": 0,
        }


def _check_wal_status(db: Session) -> dict:
    """检查 WAL 模式及文件状态"""
    try:
        mode = db.execute(text("PRAGMA journal_mode")).fetchone()
        journal_mode = mode[0] if mode else "unknown"

        if journal_mode == "wal":
            db_path_row = db.execute(text("PRAGMA database_list")).fetchone()
            wal_path = f"{db_path_row[2]}-wal" if db_path_row and len(db_path_row) >= 3 else None
            wal_size = 0
            if wal_path and os.path.exists(wal_path):
                wal_size = round(os.path.getsize(wal_path) / (1024 * 1024), 2)

            status = "ok"
            if wal_size > 100:
                status = "warning"

            return {
                "status": status,
                "journal_mode": journal_mode,
                "wal_size_mb": wal_size,
                "message": f"WAL模式，WAL文件 {wal_size}MB",
            }

        return {
            "status": "ok",
            "journal_mode": journal_mode,
            "message": f"日志模式: {journal_mode}",
        }
    except Exception as e:
        return {"status": "warning", "message": f"无法检查WAL状态: {str(e)}"}
