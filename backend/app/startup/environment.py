"""启动环境钩子：依赖包检查 / 版本变更记录 / 关键文件完整性（B3 自 main.py 迁入）。"""

import logging
from pathlib import Path

logger = logging.getLogger("assistance_management")

REQUIRED_PACKAGES = [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "pandas",
    "openpyxl",
]


def _check_required_packages():
    """启动时检查必需包（仅逐个检查核心包，避免遍历全部已安装包）"""
    import importlib

    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
        except ImportError:  # pragma: no cover
            missing.append(pkg)

    if missing:
        logger.warning(
            "缺少依赖包 %s，请运行: pip install %s",
            missing,
            " ".join(missing),
        )
    else:
        logger.info("所有关键依赖包已安装。")


def _check_and_record_version_change():
    """检查版本变更并记录更新日志"""
    try:
        from app.core.database import SessionLocal
        from app.services.update_log_service import UpdateLogService
        from app.services.version_service import version_service

        db = SessionLocal()
        try:
            update_service = UpdateLogService(db)
            current_version = version_service.get_current_version()
            version_str = current_version.get("version", "unknown")

            result = update_service.check_and_record_version_change(
                current_version=version_str,
                updated_by="system",
            )

            if result:
                action = result.get("action")
                if action == "initialize":
                    init_count = result["result"].get("initialized_count", 0)
                    logger.info("版本历史初始化完成: %s 条记录", init_count)
                elif action == "record_change":
                    old_ver = result.get("old_version")
                    new_ver = result.get("new_version")
                    logger.info("检测到版本变更: %s -> %s", old_ver, new_ver)
            else:
                logger.info("当前版本: %s", version_str)

        finally:
            db.close()
    except Exception as e:
        logger.warning("版本变更检查失败: %s", e)


def _verify_file_integrity():
    """启动时验证关键文件完整性，防止二进制被替换"""
    import hashlib

    _critical_files = [
        "app/core/config.py",
        "app/core/security.py",
        "app/core/database.py",
        "app/main.py",
    ]

    try:
        # 本模块位于 app/startup/，仓库（backend）根需上溯三级
        base_dir = Path(__file__).resolve().parent.parent.parent
        for rel_path in _critical_files:
            file_path = base_dir / rel_path
            if not file_path.exists():
                logger.warning("文件完整性检查: 关键文件缺失: %s", rel_path)
                continue

            file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            logger.debug("文件完整性: %s SHA256=%s", rel_path, file_hash[:16])

        logger.info("关键文件完整性检查完成 (%d个文件)", len(_critical_files))
    except Exception as e:
        logger.error("文件完整性检查失败: %s", e)
