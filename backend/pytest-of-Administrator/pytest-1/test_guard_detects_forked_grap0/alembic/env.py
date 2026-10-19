"""
Alembic 迁移环境配置

兼容现有的 _migrate_missing_columns 机制，两者可共存：
- Alembic 用于正式的 schema 变更（新表、重命名、索引等）
- _migrate_missing_columns 用于简单的列新增（向后兼容旧版本数据库）
"""

import logging
import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 确保 backend 目录在 Python path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.models.base import Base

# 导入所有模型确保元数据完整
import app.models  # noqa: F401

# Alembic Config 对象
config = context.config

# 使用应用配置中的数据库 URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# 配置日志
# 仅当 root 尚未配置 handler 时才走 fileConfig（即 alembic CLI 独立运行场景）。
# 应用启动时通过 main._run_alembic_upgrade 程序化调用本模块，此时应用日志已由
# init_logging() 配置完毕，若再执行 fileConfig 会重置 root handler 配置；
# 且 fileConfig 默认 disable_existing_loggers=True，会把应用全部 logger 置为
# disabled，导致迁移后应用日志完全静默（生产 Bug #15，曾致测试套件 caplog 失灵）。
if config.config_file_name is not None and not logging.getLogger().handlers:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# 目标元数据
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """以 '离线' 模式运行迁移（生成 SQL 脚本，不连接数据库）"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite 需要 batch 模式
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_auto_column_migration(connectable) -> None:
    """在 Alembic 迁移前，先运行 _migrate_missing_columns 补齐缺失列。

    这确保 alembic --autogenerate 能看到完整的表结构，
    避免因 _migrate_missing_columns 已做的变更而生成重复 DDL。
    """
    import logging
    _logger = logging.getLogger(__name__)
    try:
        from app.main import _migrate_missing_columns
        from app.models.base import Base as ModelBase
        import app.models  # noqa: F401 — 确保所有模型已注册

        _migrate_missing_columns(connectable, ModelBase)
        _logger.info("Alembic env: _migrate_missing_columns completed as pre-migration step")
    except Exception as e:
        _logger.warning(f"Alembic env: _migrate_missing_columns failed (non-fatal): {e}")


def run_migrations_online() -> None:
    """以 '在线' 模式运行迁移（连接数据库直接执行）"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # 前置补列仅对 revision --autogenerate 生效：
    # autogenerate 需要看到完整表结构（含 _migrate_missing_columns 管理的列），
    # 但 upgrade/downgrade 时执行它会让迁移里的 add_column 撞上已存在的列（重复列报错）。
    _cmd = getattr(getattr(config, "cmd_opts", None), "cmd", None)
    _cmd_name = getattr(_cmd[0], "__name__", "") if _cmd else ""
    if "revision" in _cmd_name:
        _run_auto_column_migration(connectable)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite 需要 batch 模式
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
