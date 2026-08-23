"""全局搜索 API — 聚合多模块关键词搜索"""

import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.data_permission import filter_by_data_scope
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.fund import Fund
from app.models.policy import Policy
from app.models.project import Project
from app.models.school import School
from app.models.supported_village import SupportedVillage
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["全局搜索"])

# 搜索关键词最大允许长度，防止超长字符串导致数据库压力
_MAX_Q_LEN = 100
# 每类最少返回条数
_MIN_ITEMS_PER_TYPE = 3


def _append_village_results(items: List, q: str, each: int, db: Session, current_user) -> None:
    """搜索帮扶村并追加到结果列表"""
    try:
        village_q = filter_by_data_scope(
            db.query(SupportedVillage),
            SupportedVillage,
            current_user,
            org_field="organization_id",
            db=db,
        ).filter(
            SupportedVillage.is_active.is_(True),
            or_(
                SupportedVillage.village_name.ilike(f"%{q}%"),
                SupportedVillage.county.ilike(f"%{q}%"),
            ),
        )
        for r in village_q.limit(each).all():
            items.append(
                SearchItem(
                    id=r.id,
                    type="village",
                    title=r.village_name,
                    subtitle=f"{r.province or ''} {r.city or ''} {r.county or ''}".strip() or None,
                    link=f"/villages/{r.id}",
                )
            )
    except Exception as e:
        logger.warning("搜索帮扶村失败: %s", e)


def _append_project_results(items: List, q: str, each: int, db: Session, current_user) -> None:
    """搜索帮扶项目并追加到结果列表"""
    try:
        project_q = filter_by_data_scope(
            db.query(Project),
            Project,
            current_user,
            org_field="organization_id",
            db=db,
        ).filter(
            Project.is_active == True,  # noqa: E712
            or_(
                Project.name.ilike(f"%{q}%"),
                Project.code.ilike(f"%{q}%"),
            ),
        )
        for r in project_q.limit(each).all():
            items.append(
                SearchItem(
                    id=r.id,
                    type="project",
                    title=r.name,
                    subtitle=f"项目编号：{r.code}" if r.code else None,
                    link=f"/projects/{r.id}",
                )
            )
    except Exception as e:
        logger.warning("搜索帮扶项目失败: %s", e)


def _append_policy_results(items: List, q: str, each: int, db: Session) -> None:
    """搜索政策法规并追加到结果列表（全局公开）"""
    try:
        rows = (
            db.query(Policy)
            .filter(
                or_(
                    Policy.title.ilike(f"%{q}%"),
                    Policy.keywords.ilike(f"%{q}%"),
                    Policy.issuing_authority.ilike(f"%{q}%"),
                )
            )
            .limit(each)
            .all()
        )
        for r in rows:
            items.append(
                SearchItem(
                    id=r.id,
                    type="policy",
                    title=r.title,
                    subtitle=r.issuing_authority or None,
                    link=f"/policies/{r.id}",
                )
            )
    except Exception as e:
        logger.warning("搜索政策法规失败: %s", e)


def _append_school_results(items: List, q: str, each: int, db: Session, current_user) -> None:
    """搜索帮扶学校并追加到结果列表"""
    try:
        school_q = filter_by_data_scope(
            db.query(School),
            School,
            current_user,
            org_field="organization_id",
            db=db,
        ).filter(School.is_active == True, School.name.ilike(f"%{q}%"))  # noqa: E712
        for r in school_q.limit(each).all():
            items.append(
                SearchItem(
                    id=r.id,
                    type="school",
                    title=r.name,
                    subtitle=" ".join(part for part in (r.province, r.city, r.district) if part) or None,
                    link=f"/schools/{r.id}",
                )
            )
    except Exception as e:
        logger.warning("搜索帮扶学校失败: %s", e)


def _append_fund_results(items: List, q: str, each: int, db: Session, current_user) -> None:
    """搜索资金并追加到结果列表"""
    try:
        fund_q = filter_by_data_scope(
            db.query(Fund),
            Fund,
            current_user,
            org_field="organization_id",
            db=db,
        ).filter(
            Fund.is_active == True,  # noqa: E712
            or_(
                Fund.name.ilike(f"%{q}%"),
                Fund.code.ilike(f"%{q}%"),
                Fund.project_name.ilike(f"%{q}%"),
            ),
        )
        for r in fund_q.limit(each).all():
            items.append(
                SearchItem(
                    id=r.id,
                    type="fund",
                    title=r.name or r.code or f"资金 #{r.id}",
                    subtitle=r.project_name or None,
                    link=f"/funds/{r.id}",
                )
            )
    except Exception as e:
        logger.warning("搜索资金失败: %s", e)


def _append_user_results(items: List, q: str, each: int, db: Session, is_superuser: bool) -> None:
    """搜索用户并追加到结果列表（仅超级管理员可见）"""
    if not is_superuser:
        return
    try:
        rows = (
            db.query(User)
            .filter(
                User.is_active == True,  # noqa: E712
                or_(
                    User.username.ilike(f"%{q}%"),
                    User.full_name.ilike(f"%{q}%"),
                ),
            )
            .limit(each)
            .all()
        )
        for r in rows:
            items.append(
                SearchItem(
                    id=r.id,
                    type="user",
                    title=r.full_name or r.username,
                    subtitle=r.username if r.full_name else None,
                    link="/system/users",
                )
            )
    except Exception as e:
        logger.warning("搜索用户失败: %s", e)


class SearchItem(BaseModel):
    id: int
    type: Literal["village", "project", "policy", "school", "fund", "user"]
    title: str
    subtitle: Optional[str] = None
    link: str


class SearchResponse(BaseModel):
    total: int
    items: List[SearchItem]


@router.get("", response_model=SearchResponse)
async def global_search(
    q: str = Query(..., min_length=1, max_length=_MAX_Q_LEN),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    全局关键词搜索，聚合帮扶村、项目、政策法规、资金、用户、学校六类数据。

    - q: 搜索关键词（1~100个字符）
    - limit: 最大返回条数（默认20，最大50）
    """
    q = q.strip()
    if not q:
        return SearchResponse(total=0, items=[])

    if len(q) > _MAX_Q_LEN:
        raise HTTPException(status_code=422, detail="搜索关键词过长")

    # 每类最少3条，最多 limit/6 条
    each = max(limit // 6, _MIN_ITEMS_PER_TYPE)
    is_superuser = current_user.is_superuser

    # 并行执行 6 个独立搜索查询（响应时间从 sum→max）
    import asyncio
    from app.core.database import SessionLocal

    def _search_villages():
        sess = SessionLocal()
        try:
            result = []
            _append_village_results(result, q, each, sess, current_user)
            return result
        finally:
            sess.close()

    def _search_projects():
        sess = SessionLocal()
        try:
            result = []
            _append_project_results(result, q, each, sess, current_user)
            return result
        finally:
            sess.close()

    def _search_policies():
        sess = SessionLocal()
        try:
            result = []
            _append_policy_results(result, q, each, sess)
            return result
        finally:
            sess.close()

    def _search_schools():
        sess = SessionLocal()
        try:
            result = []
            _append_school_results(result, q, each, sess, current_user)
            return result
        finally:
            sess.close()

    def _search_funds():
        sess = SessionLocal()
        try:
            result = []
            _append_fund_results(result, q, each, sess, current_user)
            return result
        finally:
            sess.close()

    def _search_users():
        sess = SessionLocal()
        try:
            result = []
            _append_user_results(result, q, each, sess, is_superuser)
            return result
        finally:
            sess.close()

    village_items, project_items, policy_items, school_items, fund_items, user_items = await asyncio.gather(
        asyncio.to_thread(_search_villages),
        asyncio.to_thread(_search_projects),
        asyncio.to_thread(_search_policies),
        asyncio.to_thread(_search_schools),
        asyncio.to_thread(_search_funds),
        asyncio.to_thread(_search_users),
    )

    items: List[SearchItem] = village_items + project_items + policy_items + school_items + fund_items + user_items
    items = items[:limit]
    return SearchResponse(total=len(items), items=items)
