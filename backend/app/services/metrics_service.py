"""核心指标单一实现（W27，修复 W26-P0-2「核心指标口径不一致」）。

## 背景

W26 全栈检测确认「核心指标 4 个里 3 个口径不一致」，直接导致**对外报送数字错误**：

### 1. 人均纯收入 —— 读的表从未被写入
| 位置 | 数据源 |
|---|---|
| 工作台 `dashboard._avg_per_capita_income` | `annual_income`（**列式** `per_capita_income_2020..2025`） |
| 汇报大屏 / 统计年度对比 / 数据分析 / 成效评估（5 处） | `village_income`（**行式** `year` + `per_capita_income`） |

实测：`annual_income` **只被读、从不被写**（全仓 0 处写入），dev 库 **0 行**；
`village_income` 有真实数据（年度数据保存写入）。即"工作台的人均收入恒为 0/陈旧"，
且 `annual_income` 的年份列写死到 **2025**，2026 年起永远取不到当年值。

**决策：统一到 `village_income`（行式）**。理由：行式无需每年改模型；真实数据在行式表。

### 2. 总人口 / 总户数 —— 「每村各自最新年」只落在一处
`CONTEXT.md:47` 规定「每村取各自最新年份」。工作台已按此实现，但
`services/analytics_service.py` 仍是裸 SQL `WHERE year = (SELECT MAX(year) FROM ...)`
（全库最大年）—— 正是 W18 P0-1 被判为缺陷的形态，修复只落在一处。
本模块提供 :func:`population_totals` 作为唯一实现。

## 用法

调用方各自拥有「可访问帮扶村 id 查询」（数据域口径不同），
把该查询传给本模块即可，避免各写一套 SQL：

    village_q = db.query(SupportedVillage.id).filter(SupportedVillage.is_active.is_(True))
    village_q = data_scope.filter_by_org_ids(village_q, SupportedVillage.organization_id, ...)
    population, households = population_totals(db, village_q)
"""

import logging
from typing import Any, Optional

from sqlalchemy import and_, func

from app.models.supported_village import SupportedVillage, VillageIncome

logger = logging.getLogger(__name__)


def avg_per_capita_income(
    db: Any, village_id_query, year: Optional[int] = None
) -> float:
    """人均纯收入（唯一实现，数据源 **``village_income`` 行式表**）。

    Args:
        db: SQLAlchemy Session。
        village_id_query: 可访问帮扶村的 id 查询（调用方已按数据域过滤）。
            传 ``None`` 时返回 ``0.0`` —— fail-closed（与 W18 P0-2 语义一致）。
        year: 指定年份；``None`` 时按「每村各自最新年」取（与总人口口径一致），
            不指定时等价于"最新可用数据"。

    Returns:
        平均人均纯收入（万元）；无数据时 0.0。

    说明：值为 0 的记录参与平均（历史实现 `AVG(col)` 亦如此），保持口径不变。
    """
    if db is None or village_id_query is None:
        return 0.0

    query = db.query(VillageIncome)
    if year is None:
        latest_subq = (
            db.query(
                VillageIncome.supported_village_id.label("vid"),
                func.max(VillageIncome.year).label("max_year"),
            )
            .group_by(VillageIncome.supported_village_id)
            .subquery()
        )
        query = query.join(
            latest_subq,
            and_(
                VillageIncome.supported_village_id == latest_subq.c.vid,
                VillageIncome.year == latest_subq.c.max_year,
            ),
        )
    else:
        query = query.filter(VillageIncome.year == year)

    query = query.filter(VillageIncome.supported_village_id.in_(village_id_query))
    value = query.with_entities(
        func.coalesce(func.avg(VillageIncome.per_capita_income), 0)
    ).scalar()
    return float(value or 0)


def accessible_village_ids_query(db: Any, data_scope):
    """构造「可访问帮扶村 id 查询」（统一的前置条件，供上面两个指标复用）。

    数据域口径：``OrgScopeFilter``（组织树模型，school/household 等同款），
    ``is_active`` 过滤软删。``data_scope`` 为 ``None`` 时抛 ``ValueError`` ——
    调用方必须显式声明数据域，避免"收下形参却没用"（W18 P0-2 的历史坑）。
    """
    if data_scope is None:
        raise ValueError("accessible_village_ids_query 需要显式 data_scope（fail-closed）")
    village_q = db.query(SupportedVillage.id).filter(
        SupportedVillage.is_active == True  # noqa: E712
    )
    return data_scope.filter_by_org_ids(
        village_q,
        SupportedVillage.organization_id,
        created_by_column=SupportedVillage.created_by,
    )
