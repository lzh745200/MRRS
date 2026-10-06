"""
Pagination Utilities (SQLAlchemy 2.0 升级版)

离线桌面管理系统 - 统一分页工具库
包含：
1. Keyset Pagination (游标分页)：适用于大数据量、无限滚动、深层分页场景，性能 O(log N)。
2. Offset Pagination (传统分页)：适用于需要精确页码跳转的后台管理列表。

全面支持 SQLAlchemy 2.0 的 Select 语法，完美兼容 joinedload/selectinload。
"""

import base64
import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 端点级分页上限（与 paginate_query 默认口径一致：单页最多 200 条）
MAX_PAGE_SIZE = 200


def clamp_offset_limit(skip: int, limit: int, max_page_size: int = MAX_PAGE_SIZE) -> tuple[int, int]:
    """钳制端点上的 ``skip`` / ``limit``，返回 ``(offset, limit)``。

    裸 ``.offset(skip).limit(limit)`` 在用户可控参数下有两个真实风险：
    ``limit=-1`` 在 SQLite 语义下等于「不限量」（一次拉全表，既是 DoS 面也是信息
    暴露面），``skip`` 为负则是非法偏移。仓库既有端点多用 ``max(skip, 0)`` 就地钳制、
    口径不一；此处收敛为单一事实源（与 ``paginate_query`` 的 ``max_page_size`` 一致）。

    采用**钳制**而非 422 校验：与仓库既有 ``max(skip, 0)`` 行为一致，不会让
    前端 0 基页码等历史调用突然失败。
    """
    return max(skip, 0), min(max(limit, 1), max_page_size)


# ============================================================================
# 1. Cursor 编码与解码 (用于 Keyset 分页)
# ============================================================================

def encode_cursor(value: Any) -> str:
    """
    将游标值编码为 URL 安全的 Base64 字符串。
    支持整数、字符串、日期等类型（通过 default=str 序列化）。
    """
    if value is None:
        return ""
    payload = json.dumps({"v": value}, default=str, sort_keys=True)
    # 移除末尾的 '=' 填充，使 URL 更干净
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8").rstrip("=")


def decode_cursor(cursor: Optional[str]) -> Optional[Any]:
    """解码 Base64 游标字符串，失败时返回 None 并记录警告。"""
    if not cursor:
        return None
    try:
        # 补齐 Base64 填充
        padding = 4 - len(cursor) % 4
        if padding != 4:
            cursor += "=" * padding

        payload = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        return json.loads(payload).get("v")
    except Exception as e:
        logger.warning(f"Invalid cursor '{cursor[:20]}...': {e}")
        return None


# ============================================================================
# 2. Keyset Pagination (高性能游标分页)
# ============================================================================

def keyset_paginate(
    stmt: Select,
    order_column: Any,
    page_size: int = 20,
    cursor: Optional[str] = None,
    desc: bool = True,
    max_page_size: int = 100,
    calculate_total: bool = True,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Keyset Pagination (Seek Method) - SQLAlchemy 2.0 版。

    优势：在 >10万行 的数据集上，传统 OFFSET 会退化为全表扫描 O(N)，
    而 Keyset 始终利用 B-Tree 索引进行范围查找 O(log N + page_size)。

    Args:
        stmt: SQLAlchemy 2.0 的 Select 对象 (例如: select(Fund).where(...))
        order_column: 排序列 (必须是索引列，通常是主键 ID 或 created_at)
        page_size: 每页条数
        cursor: 上一页返回的 next_cursor (None 表示第一页)
        desc: True=降序（最新在前），False=升序
        max_page_size: 允许的最大页大小
        calculate_total: 是否计算总条数。对于“无限滚动”列表，设为 False 可省去 Count 查询，极致提升性能。
        db: 数据库 Session 实例 (SQLAlchemy 2.0 必须通过 Session 执行 Select)

    Returns:
        包含 items, total, next_cursor, has_more 等字段的字典。
    """
    if db is None:
        raise ValueError("SQLAlchemy 2.0 要求传入 Session 实例来执行查询 (db=db)。")

    page_size = min(max(page_size, 1), max_page_size)

    # 1. 计算 Total (可选)
    total = 0
    if calculate_total:
        # 优化：清除 order_by，使用子查询计算总数，避免性能损耗。
        # 注意：不能用 func.literal(1)（SQLite 无 literal() 函数会报错，
        # 且 with_only_columns 会裁剪 FROM 导致计数恒为 1）。
        count_stmt = select(func.count()).select_from(
            stmt.order_by(None).subquery()
        )
        total = db.execute(count_stmt).scalar_one()

    # 2. 应用游标过滤 (Seek 核心逻辑)
    cursor_value = decode_cursor(cursor)
    if cursor_value is not None:
        if desc:
            stmt = stmt.where(order_column < cursor_value)
        else:
            stmt = stmt.where(order_column > cursor_value)

    # 3. 强制排序 (清除原有 order_by 防止冲突)
    stmt = stmt.order_by(None)
    if desc:
        stmt = stmt.order_by(order_column.desc())
    else:
        stmt = stmt.order_by(order_column.asc())

    # 4. 执行查询 (多取 1 条用于判断是否有下一页)
    stmt = stmt.limit(page_size + 1)
    result = db.execute(stmt)

    # 兼容 ORM 对象和标量查询
    try:
        items = result.scalars().unique().all()
    except Exception:
        items = result.all()

    # 5. 判断是否有下一页并截断
    has_more = len(items) > page_size
    if has_more:
        items = items[:page_size]

    # 6. 生成下一页游标
    next_cursor = None
    if has_more and items:
        last_item = items[-1]
        # 动态获取列名 (兼容 InstrumentedAttribute 和 Column)
        col_key = order_column.key if hasattr(order_column, "key") else str(order_column.name)
        # 标量 select（items 为裸值而非 ORM 对象）时 getattr 恒为默认值，
        # 此前默认 None → has_more=True 而 next_cursor=None，翻页静默卡死
        # （深审 #4）。标量分支直接以末值本身作为游标。
        last_value = getattr(last_item, col_key, last_item)
        if last_value is not None:
            next_cursor = encode_cursor(last_value)

    return {
        "items": items,
        "total": total,
        "next_cursor": next_cursor,
        "page_size": page_size,
        "has_more": has_more,
        "pagination": "keyset",
    }


# ============================================================================
# 3. Offset Pagination (传统分页，适用于后台管理列表)
# ============================================================================

def paginate_query(
    db: Session,
    model: Type[T],
    page: int,
    page_size: int,
    filters: Optional[List[Any]] = None,
    eager_loads: Optional[List[Any]] = None,
    order_by: Any = None,
    max_page_size: int = 200,
) -> Dict[str, Any]:
    """
    通用 Offset 分页工具 (SQLAlchemy 2.0 版)。

    彻底解决 N+1 查询和 joinedload 导致的分页错乱问题。
    将 Count 查询与 Data 查询分离，确保 Count 不受 eager_loads 影响。

    Args:
        db: 数据库 Session
        model: ORM 模型类 (如 Fund)
        page: 当前页码 (从 1 开始)
        page_size: 每页条数
        filters: WHERE 条件列表 (如 [Fund.status == 'pending', Fund.amount > 100])
        eager_loads: 预加载选项列表 (如 [joinedload(Fund.project), selectinload(Fund.attachments)])
        order_by: 排序规则 (如 Fund.id.desc())
        max_page_size: 最大页大小

    Returns:
        包含 items, total, page, page_size 的字典。
    """
    page_size = min(max(page_size, 1), max_page_size)
    page = max(page, 1)

    # 1. 构建 Count 查询 (不包含 eager_loads，提升 count 性能)
    count_stmt = select(func.count()).select_from(model)
    if filters:
        for f in filters:
            count_stmt = count_stmt.where(f)
    total = db.execute(count_stmt).scalar_one()

    # 2. 构建 Data 查询
    data_stmt = select(model)
    if filters:
        for f in filters:
            data_stmt = data_stmt.where(f)

    # 3. 注入 Eager Loading (解决 N+1)
    if eager_loads:
        for opt in eager_loads:
            data_stmt = data_stmt.options(opt)

    # 4. 排序与分页
    if order_by is not None:
        data_stmt = data_stmt.order_by(order_by)

    data_stmt = data_stmt.offset((page - 1) * page_size).limit(page_size)

    # 5. 执行并使用 unique() 去重 (防止 joinedload 产生笛卡尔积重复行)
    items = db.execute(data_stmt).scalars().unique().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pagination": "offset",
    }
