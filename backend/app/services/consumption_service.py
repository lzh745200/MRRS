"""消费帮扶台账服务层（W22 v1.14.0）。

职责：
- 数据域查询基座（列表 / 统计 / 导出统一走 ``data_scope.filter_by_org_ids``）；
- 记录级权限校验（404 / 403 fail-closed）与关联帮扶村可达性校验；
- 年度 / 品类 / 村 / 关键词筛选；
- 统计口径（总额、笔数、品类分布、村分布）；
- 导出行组装（xlsx/csv 共用，API 层只负责写文件）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from app.core.data_permission import OrgScopeFilter, require_data_permission
from app.core.errors import AppError
from app.models.consumption import ConsumptionRecord
from app.models.supported_village import SupportedVillage


def consumption_base_query(
    db: Session, data_scope: OrgScopeFilter, *, include_deleted: bool = False
) -> Query:
    """消费帮扶查询基座：软删过滤 + 数据域过滤。"""
    query = db.query(ConsumptionRecord)
    if not include_deleted:
        query = query.filter(ConsumptionRecord.is_active == True)  # noqa: E712
    return data_scope.filter_by_org_ids(
        query,
        ConsumptionRecord.organization_id,
        created_by_column=ConsumptionRecord.created_by,
    )


def apply_consumption_filters(
    query: Query,
    *,
    year: Optional[int] = None,
    category: Optional[str] = None,
    village_id: Optional[int] = None,
    keyword: Optional[str] = None,
) -> Query:
    """列表 / 导出共用筛选条件。"""
    if year:
        query = query.filter(ConsumptionRecord.year == year)
    if category:
        query = query.filter(ConsumptionRecord.category == category)
    if village_id:
        query = query.filter(ConsumptionRecord.supported_village_id == village_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(
                ConsumptionRecord.item_name.like(like),
                ConsumptionRecord.buyer.like(like),
                ConsumptionRecord.seller.like(like),
            )
        )
    return query


def attach_village_names(db: Session, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """为台账行补充帮扶村名称（批量查询，避免 N+1；软删村不再解析名称）。"""
    village_ids = {r.get("supported_village_id") for r in rows if r.get("supported_village_id")}
    names: Dict[int, str] = {}
    if village_ids:
        name_rows = (
            db.query(SupportedVillage.id, SupportedVillage.village_name)
            .filter(
                SupportedVillage.id.in_(village_ids),
                SupportedVillage.is_active == True,  # noqa: E712
            )
            .all()
        )
        names = {row[0]: row[1] for row in name_rows}
    for row in rows:
        row["village_name"] = names.get(row.get("supported_village_id"))
    return rows


def consumption_statistics(
    db: Session,
    data_scope: OrgScopeFilter,
    *,
    year: Optional[int] = None,
    include_deleted: bool = False,
) -> Dict[str, Any]:
    """消费帮扶统计（口径跟随当前用户数据域）。

    返回 ``total_amount`` / ``record_count`` / ``by_category`` / ``by_village``；
    类别与村分布均按成交金额降序，村分布仅统计已关联帮扶村的记录。
    """
    query = consumption_base_query(db, data_scope, include_deleted=include_deleted)
    if year:
        query = query.filter(ConsumptionRecord.year == year)

    record_count, total_amount = query.with_entities(
        func.count(ConsumptionRecord.id),
        func.coalesce(func.sum(ConsumptionRecord.amount), 0),
    ).one()

    category_rows = (
        query.with_entities(
            ConsumptionRecord.category,
            func.count(ConsumptionRecord.id),
            func.coalesce(func.sum(ConsumptionRecord.amount), 0),
        )
        .group_by(ConsumptionRecord.category)
        .order_by(func.coalesce(func.sum(ConsumptionRecord.amount), 0).desc())
        .all()
    )
    by_category = [
        {
            "category": category,
            # 兼容两种消费方字段命名（W22 与前端 task-15 对齐）
            "record_count": count,
            "count": count,
            "amount": float(amount or 0),
            "total_amount": float(amount or 0),
        }
        for category, count, amount in category_rows
    ]

    village_rows = (
        query.with_entities(
            ConsumptionRecord.supported_village_id,
            func.count(ConsumptionRecord.id),
            func.coalesce(func.sum(ConsumptionRecord.amount), 0),
        )
        .filter(ConsumptionRecord.supported_village_id.isnot(None))
        .group_by(ConsumptionRecord.supported_village_id)
        .order_by(func.coalesce(func.sum(ConsumptionRecord.amount), 0).desc())
        .all()
    )
    village_names: Dict[int, str] = {}
    village_ids = [row[0] for row in village_rows]
    if village_ids:
        name_rows = (
            db.query(SupportedVillage.id, SupportedVillage.village_name)
            .filter(
                SupportedVillage.id.in_(village_ids),
                SupportedVillage.is_active == True,  # noqa: E712
            )
            .all()
        )
        village_names = {row[0]: row[1] for row in name_rows}
    by_village = [
        {
            # 前端优先用 village_name；supported_village_id / village_id 双字段兼容
            "supported_village_id": village_id,
            "village_id": village_id,
            "village_name": village_names.get(village_id),
            "record_count": count,
            "count": count,
            "amount": float(amount or 0),
            "total_amount": float(amount or 0),
        }
        for village_id, count, amount in village_rows
    ]

    return {
        "total_amount": float(total_amount or 0),
        "record_count": int(record_count or 0),
        "by_category": by_category,
        "by_village": by_village,
    }


def get_consumption_or_404(
    db: Session, record_id: int, current_user, error_message: str
) -> ConsumptionRecord:
    """按 ID 取记录并做数据域校验（不存在 404 / 越权 403）。"""
    record = db.query(ConsumptionRecord).filter(ConsumptionRecord.id == record_id).first()
    if not record:
        raise AppError.not_found("消费帮扶记录")
    require_data_permission(
        current_user,
        record.organization_id,
        record.created_by,
        db,
        error_message=error_message,
    )
    return record


def ensure_village_accessible(db: Session, village_id: Optional[int], current_user) -> None:
    """校验关联帮扶村存在（未软删）且在当前用户数据域内；village_id 为空直接放行。"""
    if not village_id:
        return
    village = db.query(SupportedVillage).filter(SupportedVillage.id == village_id).first()
    if village is None or village.is_active is False:
        raise AppError.not_found("帮扶村")
    require_data_permission(
        current_user,
        village.organization_id,
        village.created_by,
        db,
        error_message="无权关联该帮扶村",
    )


#: 导出列定义（顺序即表格列顺序）
EXPORT_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("id", "ID"),
    ("year", "年度"),
    ("record_date", "成交日期"),
    ("category", "品类"),
    ("item_name", "产品名称"),
    ("quantity", "数量"),
    ("unit", "单位"),
    ("amount", "金额(元)"),
    ("buyer", "采购方"),
    ("seller", "供货方"),
    ("seller_type", "供货方类型"),
    ("village_name", "帮扶村"),
    ("remarks", "备注"),
)

#: 枚举中文标签（导出用）
CATEGORY_LABELS = {
    "agriculture": "农产品",
    "livestock": "畜禽",
    "handicraft": "手工制品",
    "other": "其他",
}
SELLER_TYPE_LABELS = {
    "farmer": "农户",
    "cooperative": "合作社",
    "enterprise": "企业",
}


def build_export_table(rows: List[Dict[str, Any]]) -> Tuple[List[str], List[List[Any]]]:
    """把台账行组装为导出表头 + 数据行（xlsx / csv 共用）。"""
    headers = [label for _key, label in EXPORT_COLUMNS]
    data_rows: List[List[Any]] = []
    for row in rows:
        values: List[Any] = []
        for key, _label in EXPORT_COLUMNS:
            value = row.get(key)
            if key == "category":
                value = CATEGORY_LABELS.get(value, value)
            elif key == "seller_type":
                value = SELLER_TYPE_LABELS.get(value, value)
            if isinstance(value, str) and value.startswith("="):
                # 防公式注入：Excel 中以 = 开头的文本按字面量输出
                value = "'" + value
            values.append(value)
        data_rows.append(values)
    return headers, data_rows
