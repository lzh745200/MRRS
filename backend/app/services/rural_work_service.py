"""乡村工作服务"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.core.permission_utils import is_admin
from app.models.rural_work import RuralWork, WorkStatus, WorkType
from app.schemas.rural_work import RuralWorkStatistics
from app.services.work_log_service import write_work_log
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)


def _iso(val: Any) -> Optional[str]:
    """安全地将日期/时间值转换为 ISO 字符串"""
    return val.isoformat() if val else None


def _safe_enum_value(val: Any) -> Any:
    """安全获取枚举值：有 .value 则取 .value，否则返回原值"""
    return val.value if val and hasattr(val, "value") else val


def _to_work_type(val: Any) -> WorkType:
    """将任意输入转换为 WorkType 枚举，空值/非法值回退到默认值。"""
    if isinstance(val, WorkType):
        return val
    if not val:
        return WorkType.infrastructure
    try:
        return WorkType(str(val))
    except ValueError:
        return WorkType.infrastructure


def _to_work_status(val: Any) -> WorkStatus:
    """将任意输入转换为 WorkStatus 枚举，空值/非法值回退到默认值。"""
    if isinstance(val, WorkStatus):
        return val
    if not val:
        return WorkStatus.planned
    try:
        return WorkStatus(str(val))
    except ValueError:
        return WorkStatus.planned


# RuralWork 允许通过 schema/kwargs 批量赋值的字段白名单
_WRITABLE_FIELDS = {
    "name", "description", "type", "status", "village_id",
    "responsible_person", "contact_phone", "start_date", "end_date",
    "target", "progress",
}


class RuralWorkService:
    """乡村工作服务"""

    def __init__(self, db: Session):
        self.db = db

    # ── 序列化辅助 ──
    @staticmethod
    def _to_dict(r: RuralWork) -> Dict[str, Any]:
        """将 RuralWork ORM 对象序列化为前端友好的字典。

        包含 village_name（通过 ORM relationship 懒加载），与
        RuralWorkResponse schema 及前端表格 prop="village_name" 对齐。
        """
        village_name = None
        if r.village:
            village_name = getattr(r.village, "name", None)
        return {
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "type": _safe_enum_value(r.type),
            "status": _safe_enum_value(r.status),
            "village_id": r.village_id,
            "village_name": village_name,
            "responsible_person": r.responsible_person,
            "contact_phone": r.contact_phone,
            "start_date": _iso(r.start_date),
            "end_date": _iso(r.end_date),
            "description": r.description,
            "target": r.target,
            "progress": r.progress,
            "created_at": _iso(r.created_at),
            "updated_at": _iso(r.updated_at),
            "created_by": r.created_by,
            "updated_by": r.updated_by,
        }

    def get_rural_works(
        self,
        skip: int = 0,
        limit: int = 10,
        status: Optional[str] = None,
        type: Optional[str] = None,
        village_id: Optional[int] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        year: Optional[int] = None,
        order_by: str = "created_at",
        order_desc: bool = True,
        current_user: Any = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取乡村工作列表（含筛选及数据权限）"""
        query = self.db.query(RuralWork)

        if current_user is not None and not is_admin(current_user):
            query = query.filter(RuralWork.created_by == getattr(current_user, "id", None))

        if status:
            query = query.filter(RuralWork.status == status)
        if type:
            query = query.filter(RuralWork.type == type)
        if village_id:
            query = query.filter(RuralWork.village_id == village_id)
        if search:
            like = f"%{search}%"
            query = query.filter(
                RuralWork.name.ilike(like) | RuralWork.description.ilike(like)
            )
        if start_date:
            try:
                dt = datetime.fromisoformat(start_date)
                query = query.filter(RuralWork.start_date >= dt)
            except ValueError:
                pass
        if end_date:
            try:
                dt = datetime.fromisoformat(end_date)
                query = query.filter(RuralWork.end_date <= dt)
            except ValueError:
                pass
        if year:
            query = query.filter(extract("year", RuralWork.start_date) == year)

        total = query.count()

        order_col = getattr(RuralWork, order_by, RuralWork.created_at)
        if order_desc:
            query = query.order_by(order_col.desc())
        else:
            query = query.order_by(order_col.asc())

        rows = query.offset(skip).limit(limit).all()

        items = [self._to_dict(r) for r in rows]

        return items, total

    # ── Backward-compat aliases (tests expect these method names) ──
    def get_rural_work_by_id(self, work_id: int) -> Optional[Dict[str, Any]]:
        work = self.db.query(RuralWork).filter(RuralWork.id == work_id).first()
        if not work:
            return None
        return self._to_dict(work)

    def delete_rural_work(self, work_id: int, user_id: Optional[int] = None) -> bool:
        work = self.db.query(RuralWork).filter(RuralWork.id == work_id).first()
        if not work:
            return False
        work_name = work.name
        self.db.delete(work)
        safe_commit(self.db)
        if user_id is not None:
            try:
                write_work_log(
                    self.db, "rural_work", "delete", work_id, work_name,
                    user_id=user_id, detail=f"删除乡村工作: {work_name}",
                )
            except Exception:  # noqa: B902 - 审计日志失败不应影响业务操作
                logger.debug("记录工作日志失败")
        return True

    def create_rural_work(self, data: Any, user_id: Optional[int] = None) -> Dict[str, Any]:
        """基于 RuralWorkCreate schema 创建乡村工作记录。

        Args:
            data: RuralWorkCreate schema 实例（或字典）。
            user_id: 创建人ID，写入 created_by/updated_by 并记录审计日志。

        Returns:
            创建后的工作记录字典（与路由期望的 ``work.model_dump()`` 契约一致，
            即一个可被 ``ResponseModel(data=...)`` 直接序列化的 dict）。
        """
        payload = data.model_dump() if hasattr(data, "model_dump") else dict(data)

        work = RuralWork(
            code=self._generate_code(),
            name=payload.get("name"),
            description=payload.get("description"),
            type=_to_work_type(payload.get("type")),
            status=_to_work_status(payload.get("status")),
            village_id=payload.get("village_id"),
            responsible_person=payload.get("responsible_person"),
            contact_phone=payload.get("contact_phone"),
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
            target=payload.get("target"),
            progress=payload.get("progress") or 0,
            created_by=user_id,
            updated_by=user_id,
        )
        self.db.add(work)
        safe_commit(self.db)
        self.db.refresh(work)

        if user_id is not None:
            try:
                write_work_log(
                    self.db, "rural_work", "create", work.id, work.name,
                    user_id=user_id, detail=f"创建乡村工作: {work.name}",
                )
            except Exception:  # noqa: B902 - 审计日志失败不应影响业务操作
                logger.debug("记录工作日志失败")

        return self._to_dict(work)

    def update_rural_work(
        self,
        work_id: int,
        data: Any = None,
        user_id: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """更新乡村工作记录。

        兼容两种调用方式：
            - 路由调用: ``update_rural_work(work_id, data, user_id)``，data 为
              RuralWorkUpdate schema 实例。
            - 旧式调用: ``update_rural_work(work_id, name="x", ...)``，字段通过
              kwargs 传入（向后兼容现有单元测试）。
        """
        work = self.db.query(RuralWork).filter(RuralWork.id == work_id).first()
        if not work:
            return None

        # 合并来源：Pydantic data（仅显式设置的字段）+ kwargs
        updates: Dict[str, Any] = {}
        if data is not None:
            if hasattr(data, "model_dump"):
                updates.update(data.model_dump(exclude_unset=True))
            else:
                updates.update(dict(data))
        updates.update(kwargs)

        for key, value in updates.items():
            if key not in _WRITABLE_FIELDS:
                continue
            if key == "type":
                value = _to_work_type(value)
            elif key == "status":
                value = _to_work_status(value)
            setattr(work, key, value)

        if user_id is not None:
            work.updated_by = user_id

        safe_commit(self.db)
        self.db.refresh(work)

        if user_id is not None:
            try:
                write_work_log(
                    self.db, "rural_work", "update", work.id, work.name,
                    user_id=user_id, detail=f"更新乡村工作: {work.name}",
                )
            except Exception:  # noqa: B902 - 审计日志失败不应影响业务操作
                logger.debug("记录工作日志失败")

        return self._to_dict(work)

    def get_statistics(self) -> RuralWorkStatistics:
        """获取乡村工作统计数据，返回 RuralWorkStatistics schema 实例。"""
        base = self.db.query(RuralWork)
        total = base.count()
        planned = base.filter(RuralWork.status == WorkStatus.planned).count()
        in_progress = base.filter(RuralWork.status == WorkStatus.in_progress).count()
        completed = base.filter(RuralWork.status == WorkStatus.completed).count()
        delayed = base.filter(RuralWork.status == WorkStatus.delayed).count()

        rows = (
            self.db.query(RuralWork.type, func.count(RuralWork.id))
            .group_by(RuralWork.type)
            .all()
        )
        by_type = {_safe_enum_value(t): c for t, c in rows}

        completion_rate = round(completed / total, 4) if total else 0.0

        return RuralWorkStatistics(
            total=total,
            planned=planned,
            in_progress=in_progress,
            completed=completed,
            delayed=delayed,
            by_type=by_type,
            completion_rate=completion_rate,
        )

    def get_villages_for_select(self) -> List[Dict[str, Any]]:
        """获取村庄列表（用于下拉选择）。

        系统真实村庄数据在 supported_villages 表；villages 表为 RuralWork 外键目标。
        本方法从帮扶村表读取并独立事务 upsert 到 villages 表（按名称），
        保证下拉有真实数据且外键一致。
        """
        from app.core.database import SessionLocal
        from app.models.supported_village import SupportedVillage
        from app.models.village import Village

        db = SessionLocal()
        try:
            svs = (
                db.query(SupportedVillage)
                .filter(SupportedVillage.is_active.is_(True))
                .order_by(SupportedVillage.village_name.asc())
                .all()
            )
            existing = {v.name: v.id for v in db.query(Village).all()}
            rows: List[Dict[str, Any]] = []
            for sv in svs:
                vid = existing.get(sv.name)
                if vid is None:
                    village = Village(
                        name=sv.name,
                        county=getattr(sv, "county", None),
                        township=getattr(sv, "township", None),
                        organization_id=getattr(sv, "organization_id", None),
                    )
                    db.add(village)
                    db.flush()
                    vid = village.id
                    existing[sv.name] = vid
                rows.append({
                    "id": vid,
                    "name": sv.name,
                    "county": getattr(sv, "county", None),
                })
            db.commit()
        finally:
            db.close()
        return rows

    def generate_work_report(
        self,
        year: Optional[int] = None,
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """生成工作报告汇总数据。"""
        query = self.db.query(RuralWork)
        if year:
            query = query.filter(extract("year", RuralWork.start_date) == year)
        if start_date:
            query = query.filter(RuralWork.start_date >= _coerce_datetime(start_date))
        if end_date:
            query = query.filter(RuralWork.end_date <= _coerce_datetime(end_date))

        rows = query.all()
        total = len(rows)

        by_status: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        for r in rows:
            s = _safe_enum_value(r.status) or "unknown"
            t = _safe_enum_value(r.type) or "unknown"
            by_status[s] = by_status.get(s, 0) + 1
            by_type[t] = by_type.get(t, 0) + 1

        completed = by_status.get("completed", 0)
        completion_rate = round(completed / total, 4) if total else 0.0

        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "completion_rate": completion_rate,
            # 前端统计卡兼容字段
            "summary": {
                "total": total,
                "completed": completed,
                "in_progress": by_status.get("in_progress", 0),
                "delayed": by_status.get("delayed", 0),
                "planned": by_status.get("planned", 0),
            },
            "items": [self._to_dict(r) for r in rows],
        }

    def get_available_years(self) -> List[int]:
        """获取可用年份列表（按降序）。"""
        year_col = extract("year", RuralWork.start_date).label("year")
        rows = (
            self.db.query(year_col)
            .filter(RuralWork.start_date.isnot(None))
            .distinct()
            .order_by(year_col.desc())
            .all()
        )
        return [int(r.year) for r in rows if r.year is not None]

    def batch_delete(self, ids: List[int]) -> int:
        """批量删除乡村工作，返回实际删除条数。"""
        if not ids:
            return 0
        deleted = (
            self.db.query(RuralWork)
            .filter(RuralWork.id.in_(list(ids)))
            .delete(synchronize_session=False)
        )
        safe_commit(self.db)
        return int(deleted or 0)

    @staticmethod
    def _generate_code() -> str:
        return f"RW-{uuid.uuid4().hex[:8].upper()}"


def _coerce_datetime(val: Any) -> datetime:
    """将字符串/datetime 统一转换为 datetime；无法解析时返回当前时间。"""
    if isinstance(val, datetime):
        return val
    if val:
        try:
            return datetime.fromisoformat(str(val))
        except ValueError:
            pass
    return datetime.now()
