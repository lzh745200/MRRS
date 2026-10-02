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

from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, Integer, String, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator

# ── 声明式基类 ──
Base = declarative_base()


class EncryptedText(TypeDecorator):
    """PII 字段透明加密类型（ADR-0005，确定性 AES-SIV）

    - 写入：明文 → `enc.v1:` 标记密文（确定性，等值查询可直接命中密文）
    - 读取：密文 → 明文；未标记的历史明文/异常值原样返回
    - impl 用 String：SQLite 不强制长度，长度仅供 DDL/文档语义
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int = 256, **kw):
        super().__init__(length=length, **kw)

    def process_bind_param(self, value, dialect):
        from app.core.pii_crypto import encrypt_pii

        return encrypt_pii(value)

    def process_result_value(self, value, dialect):
        from app.core.pii_crypto import decrypt_pii

        return decrypt_pii(value)


def is_datetime_type(col_type) -> bool:
    """判定列类型是否为日期/时间列，**兼容 TypeDecorator 包装**（如 `UtcDateTime`）。

    为什么需要它：`isinstance(col.type, DateTime)` 在列类型被 TypeDecorator 包装后
    会**静默失配** —— 2026-10-02 引入 `UtcDateTime` 后，数据包校验器
    （`services/package_record_validator._date_fields`）因此不再把
    `support_start_date` 识别为日期列，跳过「日期归一 ISO」，脏字符串直达批量入库、
    整批写入失败。凡按类型识别时间列的地方都必须走本函数。
    """
    candidate = col_type
    for _ in range(5):  # 防御多层包装；正常为单层
        if not isinstance(candidate, TypeDecorator):
            break
        candidate = candidate.impl
    return isinstance(candidate, (Date, DateTime))


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


class UtcDateTime(TypeDecorator):
    """DateTime 列专用类型：落库统一为 **naive UTC**，读回统一为 **aware UTC**。

    ## 为什么需要它

    SQLite 不保存时区，aware 值写下去偏移即被丢弃、读回是 naive —— 其语义是 UTC
    （见下方「时间基准强约定」）。但 naive 值一旦流出 ORM，**所有消费方都会丢掉
    「这是 UTC」这一事实**：``to_dict()`` 的 ``isoformat()`` 不带偏移、FastAPI 的
    ``jsonable_encoder`` 同理，前端 ``new Date(str)`` 便按**本地**时区解析，于是库中的
    UTC 墙钟被当作本地时间展示 —— 非 UTC 主机（UTC+8）上全部时间偏早 8 小时。

    本类型把该事实编码进类型本身，从而**一处修复、所有出口正确**：

    * ``to_dict()`` / FastAPI 序列化 → 输出带 ``+00:00``，前端按本地渲染即正确；
    * Python 级比较自动与 aware 的 ``utcnow()`` 兼容，不再静默错位（错用会**响亮地**
      抛 TypeError 而不是悄悄偏 8 小时）；
    * SQL 级比较不受影响 —— 绑定处理器本就丢弃偏移，落库字面量仍是 UTC 墙钟；
    * 导出（Excel/PDF）拿到的是 aware 值，展示前按本地渲染即可。

    存量数据**无需迁移**：库中本来就是 UTC 墙钟，本类型只补齐时区标注。
    """

    impl = DateTime
    cache_ok = True

    def __init__(self, *args, **kwargs):
        # 兼容历史写法 UtcDateTime(timezone=True)：时区语义由本类固定，忽略该参数
        kwargs.pop("timezone", None)
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        """写入：aware → 转 UTC 后去时区；naive 按约定视为 UTC 原样落库。

        ⚠️ 非 datetime 值（如数据包导入传入的脏字符串）**原样放行**交给隐含类型
        处理 —— 本装饰器只负责时区归一，不得收窄基础类型原本接受的输入范围，
        否则会以 AttributeError 的形式在批量导入等路径上误伤（2026-10-02 实测）。
        """
        if not isinstance(value, datetime):
            return value
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        """读取：补成 aware UTC（naive 即 UTC；后端返回 aware 时统一换算）。"""
        if not isinstance(value, datetime):
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


# ── 时间基准强约定（改这部分前务必读完）──────────────────────────────
# 1. **存储**：所有 DateTime 列**必须**使用 ``UtcDateTime``（落库 naive UTC、读回 aware UTC）。
#    SQLite 不保存时区，aware 值写下去偏移即被丢弃，读回是 naive —— 其语义是 UTC。
# 2. **比较**：与「当前时刻」比较必须用 UTC 口径（``app.utils.time_utils.utcnow()``）。
#    **禁止**用 ``datetime.now()``（本机本地）直接与库值比较，非 UTC 主机（如 UTC+8）上
#    会整体偏移 8 小时。历史实例：审批超时提醒晚 8 小时触发（reminder_engine）、
#    报表订阅提前派发（subscription_dispatch_service，2026-10-02）。转换入口统一在
#    ``app.utils.time_utils``，不要在各处自造实现。
#    ⚠️ 写入侧同理：``model.field = datetime.now()`` 会把**本地**墙钟写进 UTC 列，
#    必须改用 ``time_utils.utcnow()``（或 ``utcnow_naive()``）。
# 3. **展示**：``to_dict()`` 输出的时间带 ``+00:00`` 偏移，前端 ``new Date(str)``
#    会正确换算到本地时区显示。
# ────────────────────────────────────────────────────────────────
class TimestampMixin:
    """为模型添加 created_at / updated_at 字段"""

    created_at = Column(
        UtcDateTime(),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at = Column(
        UtcDateTime(),
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


# ── sync_version 自动递增 ──
# 修复增量数据包过滤失效：此前 sync_version 恒为 1，`sync_version > since` 过滤
# 永远为空。这里在每次 UPDATE 前自动递增，使增量包按版本号过滤真正生效。
from sqlalchemy import event as _sqla_event  # noqa: E402


@_sqla_event.listens_for(TimestampMixin, "before_update", propagate=True)
def _bump_sync_version_on_update(mapper, connection, target) -> None:
    """每次 UPDATE 前递增 sync_version（新行 default=1，更新即 +1）。"""
    sv = getattr(target, "sync_version", None)
    if sv is not None:
        target.sync_version = (sv or 0) + 1


# ── sync_version 对批量 UPDATE 同样递增 ──
# ORM 的 before_update 事件只覆盖"加载对象再改属性"的路径；query.update() /
# update(Model).values(...) 这类 bulk update 直接发 SQL，不触发该事件 ——
# 这些行 sync_version 不变，增量同步按 sync_version > since 过滤时会漏行
# （深审 LIVE）。这里在 SQL 层补上自增，保证两条路径语义一致。
from sqlalchemy.engine import Engine as _Engine  # noqa: E402
from sqlalchemy.sql.dml import Update as _UpdateStmt  # noqa: E402


@_sqla_event.listens_for(_Engine, "before_execute", retval=True)
def _bump_sync_version_on_bulk_update(conn, clauseelement, multiparams, params, execution_options):
    """为 bulk UPDATE 补 sync_version 自增（调用方已显式设置时不动）。"""
    if isinstance(clauseelement, _UpdateStmt):
        table = getattr(clauseelement, "table", None)
        if table is not None and "sync_version" in table.c:
            values = getattr(clauseelement, "_values", None) or {}
            if "sync_version" not in values:
                clauseelement = clauseelement.values(
                    sync_version=table.c.sync_version + 1
                )
    return clauseelement, multiparams, params


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
    deleted_at = Column(UtcDateTime(), nullable=True, comment="删除时间")
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
