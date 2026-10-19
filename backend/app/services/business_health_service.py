"""业务数据体检服务（W17-008）。

面向管理员的业务数据质量体检：把"系统体检"从基础设施延伸到业务数据本身。

设计约束（硬要求，改动时不得放宽）：

1. 只出结构化计数与入口：每项体检给出 count + 前端处理入口 entry，
   明细 items 只含实体 id、状态、金额、时间等非个人信息；不返回任何 PII
   —— 项目/经费名称、经办人、联系人、手机号、身份证号一律不出境（名称字段可能
   夹带个人姓名，故项目/经费明细只给 id）。
2. 空库/满库均可用：所有查询天然返回 0 行/0 计数，不抛异常；明细条数由
   item_limit 截断，并显式标记 items_truncated。
3. 扫描 SQL 一律走 ORM 表达式 / 参数绑定，禁止任何字符串拼接 SQL
   （避免注入面，也保证 SQLite/PG 兼容）。
4. 时间口径统一 UTC：与库中 UtcDateTime 列比较用 app.utils.time_utils.utcnow()，
   禁止本地 datetime.now()。
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.project import Project
from app.models.supported_village import (
    SupportedVillage,
    VillageIncome,
    VillagePopulation,
)
from app.utils.time_utils import utcnow

# 长期未动默认阈值（天）：半年无更新视为"长期未动"
DEFAULT_STALE_DAYS = 180
# 每项体检明细默认返回上限（响应体积与可读性的折中）
DEFAULT_ITEM_LIMIT = 50
MAX_ITEM_LIMIT = 200

# 体检项在前端对应的处理入口（与 router 中的实际路由一致）
ENTRY_VILLAGE_YEARLY = "/supported-villages/yearly"
ENTRY_PROJECTS = "/projects"
ENTRY_FUNDS = "/funds"
ENTRY_ORGANIZATIONS = "/organizations"

# 已收口状态不参与"长期未动"判定（完成/取消后不再更新属正常）
_PROJECT_CLOSED_STATUSES = ("completed", "cancelled")
_FUND_CLOSED_STATUSES = ("completed", "audited")


class BusinessHealthService:
    """业务数据体检（管理员视图；不返回 PII）。"""

    def __init__(
        self,
        db: Session,
        *,
        year: Optional[int] = None,
        stale_days: int = DEFAULT_STALE_DAYS,
        item_limit: int = DEFAULT_ITEM_LIMIT,
    ) -> None:
        self.db = db
        self.year = year or date.today().year
        self.stale_days = stale_days
        self.item_limit = item_limit
        self.cutoff = utcnow() - timedelta(days=stale_days)

    # ── 对外入口 ──────────────────────────────────────────────────────
    def collect(self) -> Dict[str, Any]:
        """执行全部体检项，返回可直接给管理员页面的结构化报告。"""
        checks = [
            self._village_annual_missing(),
            self._fund_used_exceeds_amount(),
            self._fund_negative_amount(),
            self._stale_projects(),
            self._stale_funds(),
            self._village_organization_missing(),
            self._project_organization_missing(),
            self._fund_organization_missing(),
        ]
        issue_count = sum(check["count"] for check in checks)
        affected_checks = sum(1 for check in checks if check["count"] > 0)
        return {
            "generated_at": utcnow().isoformat(),
            "year": self.year,
            "stale_days": self.stale_days,
            "item_limit": self.item_limit,
            "status": "warning" if issue_count else "healthy",
            "summary": {
                "check_count": len(checks),
                "affected_checks": affected_checks,
                "issue_count": issue_count,
            },
            "checks": checks,
        }

    # ── 检查项 ────────────────────────────────────────────────────────
    def _village_annual_missing(self) -> Dict[str, Any]:
        """村年度缺失：目标年度缺少收入/人口年度数据的帮扶村。"""
        villages = (
            self.db.query(SupportedVillage.id, SupportedVillage.village_name)
            .filter(SupportedVillage.is_active.is_(True))
            .order_by(SupportedVillage.id)
            .all()
        )
        income_ids = {
            row[0]
            for row in self.db.query(VillageIncome.supported_village_id)
            .filter(VillageIncome.year == self.year)
            .all()
        }
        population_ids = {
            row[0]
            for row in self.db.query(VillagePopulation.supported_village_id)
            .filter(VillagePopulation.year == self.year)
            .all()
        }
        count = 0
        items: List[Dict[str, Any]] = []
        for village_id, village_name in villages:
            missing_sections = []
            if village_id not in income_ids:
                missing_sections.append("income")
            if village_id not in population_ids:
                missing_sections.append("population")
            if missing_sections:
                count += 1
                if len(items) < self.item_limit:
                    items.append(
                        {
                            "id": village_id,
                            "name": village_name,
                            "missing_sections": missing_sections,
                        }
                    )
        return self._check(
            "village_annual_missing",
            "村年度数据缺失",
            count,
            items,
            ENTRY_VILLAGE_YEARLY,
            "目标年度缺收入或人口年度数据的帮扶村（年度 %s）" % self.year,
        )

    def _fund_used_exceeds_amount(self) -> Dict[str, Any]:
        """金额逻辑矛盾 1：已使用金额大于申请金额（used_amount > amount）。"""
        base = self.db.query(Fund).filter(
            Fund.is_active.is_(True),
            Fund.used_amount > Fund.amount,
        )
        count = base.count()
        rows = base.order_by(Fund.id).limit(self.item_limit).all()
        items = [
            {
                "id": fund.id,
                "amount": float(fund.amount or 0),
                "used_amount": float(fund.used_amount or 0),
                "overrun": round(float(fund.used_amount or 0) - float(fund.amount or 0), 4),
            }
            for fund in rows
        ]
        return self._check(
            "fund_used_exceeds_amount",
            "经费使用金额超过申请金额",
            count,
            items,
            ENTRY_FUNDS,
            "used_amount > amount（金额单位：万元），存在逻辑矛盾",
        )

    def _fund_negative_amount(self) -> Dict[str, Any]:
        """金额逻辑矛盾 2：申请/拨付/使用金额出现负数。"""
        negative_filter = or_(
            Fund.amount < 0,
            Fund.allocated_amount < 0,
            Fund.used_amount < 0,
        )
        base = self.db.query(Fund).filter(
            Fund.is_active.is_(True),
            negative_filter,
        )
        count = base.count()
        rows = base.order_by(Fund.id).limit(self.item_limit).all()
        items = [
            {
                "id": fund.id,
                "negative_fields": [
                    field
                    for field in ("amount", "allocated_amount", "used_amount")
                    if (
                        getattr(fund, field) is not None
                        and float(getattr(fund, field)) < 0
                    )
                ],
                "amounts": {
                    "amount": float(fund.amount or 0),
                    "allocated_amount": float(fund.allocated_amount or 0),
                    "used_amount": float(fund.used_amount or 0),
                },
            }
            for fund in rows
        ]
        return self._check(
            "fund_negative_amount",
            "经费金额出现负数",
            count,
            items,
            ENTRY_FUNDS,
            "amount / allocated_amount / used_amount 中至少一项小于 0",
        )

    def _stale_projects(self) -> Dict[str, Any]:
        """长期未动项目：超过阈值天数未更新且未收口的在册项目。"""
        base = self.db.query(Project).filter(
            Project.is_active.is_(True),
            Project.status.notin_(_PROJECT_CLOSED_STATUSES),
            Project.updated_at < self.cutoff,
        )
        count = base.count()
        rows = base.order_by(Project.updated_at).limit(self.item_limit).all()
        items = [
            {
                "id": project.id,
                "status": project.status,
                "updated_at": project.updated_at.isoformat() if project.updated_at else None,
            }
            for project in rows
        ]
        return self._check(
            "stale_projects",
            "长期未动的项目",
            count,
            items,
            ENTRY_PROJECTS,
            "超过 %s 天未更新且未完成/取消的项目" % self.stale_days,
        )

    def _stale_funds(self) -> Dict[str, Any]:
        """长期未动经费：超过阈值天数未更新且未收口的在册经费。"""
        base = self.db.query(Fund).filter(
            Fund.is_active.is_(True),
            Fund.status.notin_(_FUND_CLOSED_STATUSES),
            Fund.updated_at < self.cutoff,
        )
        count = base.count()
        rows = base.order_by(Fund.updated_at).limit(self.item_limit).all()
        items = [
            {
                "id": fund.id,
                "status": fund.status,
                "updated_at": fund.updated_at.isoformat() if fund.updated_at else None,
            }
            for fund in rows
        ]
        return self._check(
            "stale_funds",
            "长期未动的经费",
            count,
            items,
            ENTRY_FUNDS,
            "超过 %s 天未更新且未完成/审计的经费" % self.stale_days,
        )

    def _village_organization_missing(self) -> Dict[str, Any]:
        """组织归属缺失：帮扶村 organization_id 为空（影响组织级数据权限）。"""
        base = self.db.query(SupportedVillage).filter(
            SupportedVillage.is_active.is_(True),
            SupportedVillage.organization_id.is_(None),
        )
        count = base.count()
        rows = base.order_by(SupportedVillage.id).limit(self.item_limit).all()
        items = [{"id": village.id, "name": village.village_name} for village in rows]
        return self._check(
            "village_organization_missing",
            "帮扶村组织归属缺失",
            count,
            items,
            ENTRY_ORGANIZATIONS,
            "organization_id 为空，组织级数据权限与导出会 fail-closed",
        )

    def _project_organization_missing(self) -> Dict[str, Any]:
        """组织归属缺失：项目 organization_id 为空。"""
        base = self.db.query(Project).filter(
            Project.is_active.is_(True),
            Project.organization_id.is_(None),
        )
        count = base.count()
        rows = base.order_by(Project.id).limit(self.item_limit).all()
        items = [{"id": project.id} for project in rows]
        return self._check(
            "project_organization_missing",
            "项目组织归属缺失",
            count,
            items,
            ENTRY_PROJECTS,
            "organization_id 为空，部门级管理员将看不到该项目",
        )

    def _fund_organization_missing(self) -> Dict[str, Any]:
        """组织归属缺失：经费 organization_id 为空。"""
        base = self.db.query(Fund).filter(
            Fund.is_active.is_(True),
            Fund.organization_id.is_(None),
        )
        count = base.count()
        rows = base.order_by(Fund.id).limit(self.item_limit).all()
        items = [{"id": fund.id} for fund in rows]
        return self._check(
            "fund_organization_missing",
            "经费组织归属缺失",
            count,
            items,
            ENTRY_FUNDS,
            "organization_id 为空，部门级管理员将看不到该经费",
        )

    # ── 内部工具 ──────────────────────────────────────────────────────
    @staticmethod
    def _check(
        key: str,
        title: str,
        count: int,
        items: List[Dict[str, Any]],
        entry: str,
        hint: str,
        severity: str = "warning",
    ) -> Dict[str, Any]:
        """组装单项体检结果（count 为全量计数，items 为截断后的明细）。"""
        return {
            "key": key,
            "title": title,
            "severity": severity,
            "count": count,
            "entry": entry,
            "hint": hint,
            "items": items,
            "items_truncated": count > len(items),
        }
