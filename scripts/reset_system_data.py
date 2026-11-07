"""清空 MRRS 业务数据并重建可登录的空系统。

用法：
    python scripts/reset_system_data.py --yes

安全约束：
- 默认先打包实际运行目录 + 工作区旧目录到 .pre-clean-archive/<timestamp>/，再清空。
- 保留所有 runtime_secrets.json（PII/备份加密密钥），否则归档备份不可读。
- 只清理运行数据，不碰代码、配置、dist、node_modules。

注意：本仓 backend/.env 的 DATABASE_URL 是相对路径，实际生效库是
backend/data/rural_revitalization.db；脚本以 settings 解析结果为准，同时
清理工作区根 data/ 的历史遗留，避免“清了 A 库、应用仍读 B 库”。
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.core.config import settings  # noqa: E402
from app.utils.paths import get_backup_path, get_runtime_uploads_path  # noqa: E402

# settings 已按 backend/.env + 动态默认值解析出真实路径
_db_url = settings.DATABASE_URL
if not _db_url.startswith("sqlite:///"):
    raise SystemExit(f"仅支持 SQLite，当前 DATABASE_URL={_db_url}")
DB_PATH = Path(_db_url[len("sqlite:///") :]).resolve()
RUNTIME_DATA = DB_PATH.parent
RUNTIME_UPLOADS = Path(settings.UPLOAD_DIR).resolve()
RUNTIME_BACKUPS = Path(get_backup_path()).resolve()
ROOT_DATA = ROOT / "data"
ROOT_UPLOADS = ROOT / "uploads"
ROOT_BACKUPS = ROOT / "backups"
ROOT_DATA_SYNC = ROOT / "data_sync"
ROOT_LOGS = ROOT / "logs"
RUNTIME_LOGS = BACKEND / "logs"

KEEP_NAMES = {"runtime_secrets.json"}


def _unique(paths):
    seen = set()
    out = []
    for p in paths:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(rp)
    return out


ARCHIVE_DIRS = _unique([
    RUNTIME_DATA, RUNTIME_UPLOADS, RUNTIME_BACKUPS,
    ROOT_DATA, ROOT_UPLOADS, ROOT_BACKUPS, ROOT_DATA_SYNC, ROOT_LOGS, RUNTIME_LOGS,
])
CLEAR_DATA_DIRS = _unique([RUNTIME_DATA, ROOT_DATA])
CLEAR_OTHER_DIRS = _unique([
    RUNTIME_UPLOADS, RUNTIME_BACKUPS, ROOT_UPLOADS, ROOT_BACKUPS,
    ROOT_DATA_SYNC, ROOT_LOGS, RUNTIME_LOGS,
])


def _archive(timestamp: str) -> Path:
    archive_dir = ROOT / ".pre-clean-archive" / timestamp
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / "mrrs-runtime-data.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for directory in ARCHIVE_DIRS:
            if not directory.exists():
                continue
            for path in directory.rglob("*"):
                if not path.is_file():
                    continue
                if path.parent == directory and path.name in KEEP_NAMES:
                    continue
                zf.write(path, path.relative_to(ROOT).as_posix())
    return archive_path


def _clear_dir(directory: Path, *, keep_secrets: bool = False) -> list[str]:
    """清空目录；被占用/只读的文件跳过并返回，避免单个日志锁阻断整个重建。"""
    skipped: list[str] = []
    directory.mkdir(parents=True, exist_ok=True)
    for child in directory.iterdir():
        if keep_secrets and child.name in KEEP_NAMES:
            continue
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except OSError as exc:
            skipped.append(f"{child}: {exc}")
    return skipped


def _clear_all() -> list[str]:
    skipped: list[str] = []
    for directory in CLEAR_DATA_DIRS:
        skipped.extend(_clear_dir(directory, keep_secrets=True))
    for directory in CLEAR_OTHER_DIRS:
        skipped.extend(_clear_dir(directory))
    return skipped


def _seed_empty_system() -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"

    from app.main import _init_database_tables  # noqa: PLC0415
    from app.core.database import SessionLocal  # noqa: PLC0415
    from app.models.organization import Organization  # noqa: PLC0415
    from app.startup.seed import _seed_default_admin  # noqa: PLC0415
    from app.services.system_config_service import SystemConfigService  # noqa: PLC0415

    _init_database_tables()
    db = SessionLocal()
    try:
        org = Organization(
            name="默认组织",
            code="DEFAULT",
            level="level_1",
            org_type="department",
            is_active=True,
        )
        db.add(org)
        db.commit()
        db.refresh(org)
    finally:
        db.close()

    _seed_default_admin()

    # 初始化状态接口从 SystemConfig 读组织名/系统名；只建 org 不写配置会显示“未知单位”。
    db = SessionLocal()
    try:
        cfg = SystemConfigService(db)
        cfg.set("organization_name", "默认组织", "初始化单位名称")
        cfg.set("system_name", "帮扶管理信息系统", "系统名称")
        cfg.set("init_timestamp", datetime.now().isoformat(), "初始化时间")
    finally:
        db.close()


def _verify() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        admin = conn.execute(
            "SELECT username, is_superuser, must_change_password FROM users WHERE username='admin'"
        ).fetchone()
        org = conn.execute(
            "SELECT name, code FROM organizations WHERE code='DEFAULT'"
        ).fetchone()
    finally:
        conn.close()

    assert "users" in tables and "organizations" in tables
    assert admin == ("admin", 1, 1), f"默认管理员异常: {admin}"
    assert org == ("默认组织", "DEFAULT"), f"默认组织异常: {org}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="确认清空，不可恢复")
    parser.add_argument("--no-backup", action="store_true", help="跳过归档（不推荐）")
    args = parser.parse_args()
    if not args.yes:
        print("拒绝执行：请加 --yes 确认清空所有业务数据。")
        return 2

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if not args.no_backup:
        archive = _archive(timestamp)
        print(f"[OK] 已归档: {archive}")

    skipped = _clear_all()
    print(f"[OK] 已清空实际库 {DB_PATH} 及其 uploads/backups/logs")
    if skipped:
        print(f"[WARN] 有 {len(skipped)} 个被占用文件未能删除（通常是日志/编辑器占用）：")
        for item in skipped[:10]:
            print(f"  - {item}")

    _seed_empty_system()
    _verify()
    print("[OK] 空库初始化完成：默认组织 DEFAULT，管理员 admin（首次登录强制改密）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
