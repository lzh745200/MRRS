"""
数据库模型基类模块

提供所有模型共用的基类、混入类:
- Base: SQLAlchemy 声明式基类
- TimestampMixin: 创建/更新时间戳
- SoftDeleteMixin: 软删除支持
- VersionMixin: 乐观锁版本号
- BaseModel: 带 id + 时间戳的完整基类
"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

# ── 声明式基类 ──
Base = declarative_base()


def _base_to_dict(self) -> dict:
    """将模型实例转为字典（所有列）。BaseModel 覆盖此方法增加 datetime 处理。"""
    result = {}
    for attr in self.__mapper__.column_attrs:
        val = getattr(self, attr.key, None)
        result[attr.key] = val
    return result


Base.to_dict = _base_to_dict


def _utcnow():
    """返回当前 UTC 时间（timezone-aware）"""
    return datetime.now(timezone.utc)


# ── 时间戳混入 ──
class TimestampMixin:
    """为模型添加 created_at / updated_at 字段"""

    created_at = Column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )
    sync_version = Column(
        BigInteger,
        default=1,
        server_default=text("1"),
        nullable=False,
        comment="同步版本号（增量同步依据）",
    )


# ── 软删除混入 ──
class SoftDeleteMixin:
    """为模型添加软删除支持。

    提供 ``is_deleted`` / ``deleted_at`` / ``deleted_by`` 三个字段，
    以及 ``soft_delete()`` / ``restore()`` 便捷方法。

    兼容性说明：
        - 实际业务模型（``SupportedVillage``、``School`` 等）使用 ``is_active``
          列（``is_active=False`` 表示已删除），而非本混入的 ``is_deleted``。
          这是因为历史迁移已使用 ``is_active`` 命名，改为 ``is_deleted`` 需要
          Alembic 迁移且影响所有查询。
        - 本混入预留给**新模型**使用；已有模型可逐步迁移到本混入。
        - ``is_active`` 与 ``is_deleted`` 互为反值：``is_active = not is_deleted``。

    审计追踪（9.5.7 预留）：
        ``deleted_by`` 字段记录执行软删除的用户 ID，便于审计追踪。
        通过 ``soft_delete(deleted_by=user.id)`` 传入。
    """

    is_deleted = Column(Boolean, default=False, nullable=False, comment="是否已删除")
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment="删除时间")
    deleted_by = Column(Integer, nullable=True, comment="删除操作人用户ID（审计追踪）")

    def soft_delete(self, deleted_by: int | None = None) -> None:
        """执行软删除。

        Args:
            deleted_by: 执行删除的用户 ID（可选，用于审计追踪）。
        """
        self.is_deleted = True
        self.deleted_at = _utcnow()
        if deleted_by is not None:
            self.deleted_by = deleted_by

    def restore(self) -> None:
        """恢复软删除（清除 deleted_by 审计字段）。"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None


# ── 版本号混入（乐观锁） ──
class VersionMixin:
    """为模型添加乐观锁版本号"""

    version = Column(Integer, default=1, nullable=False, comment="版本号（乐观锁）")


# ── 完整基类（id + 时间戳） ──
class BaseModel(Base, TimestampMixin):
    """
    所有业务模型的推荐基类。

    提供:
    - id: 自增主键
    - created_at: 创建时间
    - updated_at: 更新时间
    """

    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    def to_dict(self, camel_case: bool = True):
        """将模型实例转换为字典（默认 camelCase 键名，供前端使用）"""
        from app.utils.common import dict_keys_to_camel
        result = {}
        for attr in self.__mapper__.column_attrs:
            val = getattr(self, attr.key, None)
            if isinstance(val, datetime):
                val = val.isoformat()
            result[attr.key] = val
        return dict_keys_to_camel(result) if camel_case else result

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"
