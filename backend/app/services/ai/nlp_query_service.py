"""
自然语言查询服务
将自然语言转换为SQL查询
"""

import logging
import re
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class NLPQueryService:
    """自然语言查询服务"""

    # 查询模板映射（按匹配优先级排序，更具体的模式在前）
    # SQL 全部使用参数化占位符 (:param) 防止注入；
    # {village_scope} / {scope} 由 execute_query 在运行时替换为**数据域子查询**
    # （见 _scope_subquery），保证模板 SQL 与列表/导出链路同一口径（军审红线 S2）。
    # 所有模板同时过滤软删（is_active = 1）——历史模板未过滤，软删数据仍计入统计。
    QUERY_TEMPLATES = {
        "village_by_province": {
            "patterns": [r"(.+?省)有多少个?村", r"(.+?的)村庄"],
            "sql": (
                "SELECT COUNT(*) as count FROM supported_villages "
                "WHERE province = :province AND is_active = 1 AND {village_scope}"
            ),
            "scope": "village",
            "description": "查询指定省份的村庄数量",
        },
        "village_count": {
            "patterns": [r"有多少个?村", r"村庄数量", r"村的数量"],
            "sql": "SELECT COUNT(*) as count FROM supported_villages WHERE is_active = 1 AND {village_scope}",
            "scope": "village",
            "description": "查询村庄总数",
        },
        "project_count": {
            "patterns": [r"有多少个?项目", r"项目数量"],
            "sql": "SELECT COUNT(*) as count FROM projects WHERE is_active = 1 AND {scope}",
            "scope": "project",
            "description": "查询项目总数",
        },
        "project_by_status": {
            "patterns": [r"(.+?)状态的项目", r"(.+?)的项目有多少"],
            "sql": "SELECT COUNT(*) as count FROM projects WHERE status = :status AND is_active = 1 AND {scope}",
            "scope": "project",
            "description": "查询指定状态的项目数量",
        },
        "total_funds": {
            "patterns": [r"总资金", r"资金总额", r"投入了多少资金"],
            "sql": "SELECT SUM(amount) as total FROM funds WHERE is_active = 1 AND {scope}",
            "scope": "fund",
            "description": "查询资金总额",
        },
        "village_income": {
            "patterns": [r"(.+?)村的收入", r"(.+?)的人均收入"],
            "sql": """
                SELECT sv.village_name, vi.per_capita_income, vi.year
                FROM supported_villages sv
                JOIN village_income vi ON sv.id = vi.supported_village_id
                WHERE sv.village_name LIKE '%' || :village_name || '%'
                  AND sv.is_active = 1
                  AND sv.id IN ({village_scope})
                ORDER BY vi.year DESC
                LIMIT 1
            """,
            "scope": "village",
            "description": "查询村庄收入",
        },
        "top_villages_by_income": {
            "patterns": [r"收入最高的.*?村", r"人均收入排名", r"收入前.*?名"],
            "sql": """
                SELECT sv.village_name, vi.per_capita_income, vi.year
                FROM supported_villages sv
                JOIN village_income vi ON sv.id = vi.supported_village_id
                WHERE vi.year = (SELECT MAX(year) FROM village_income)
                  AND sv.is_active = 1
                  AND sv.id IN ({village_scope})
                ORDER BY vi.per_capita_income DESC
                LIMIT :limit
            """,
            "scope": "village",
            "description": "查询收入最高的村庄",
        },
    }

    # 状态映射
    STATUS_MAP = {
        "进行中": "in_progress",
        "已完成": "completed",
        "计划中": "planned",
        "暂停": "paused",
        "取消": "cancelled",
    }

    @staticmethod
    def parse_query(query: str) -> Dict[str, Any]:
        """
        解析自然语言查询

        Args:
            query: 自然语言查询

        Returns:
            解析结果
        """
        query = query.strip()

        # 尝试匹配查询模板
        for template_name, template in NLPQueryService.QUERY_TEMPLATES.items():
            for pattern in template["patterns"]:
                match = re.search(pattern, query)
                if match:
                    # 提取参数
                    params = {}
                    if match.groups():
                        if "province" in template["sql"]:
                            # 库口径：supported_villages.province 存的是**不带"省"字**的
                            # 省份名（如"广东"），而正则捕获的是"广东省"；不归一化则
                            # 等值匹配恒空。与 STATUS_MAP 同思路：能归一就归一。
                            params["province"] = NLPQueryService._normalize_province(match.group(1))
                        elif "status" in template["sql"]:
                            status_text = match.group(1)
                            params["status"] = NLPQueryService.STATUS_MAP.get(status_text, status_text)
                        elif "village_name" in template["sql"]:
                            params["village_name"] = match.group(1)

                    # 提取数量限制
                    limit_match = re.search(r"前(\d+)", query)
                    if limit_match:
                        params["limit"] = int(limit_match.group(1))
                    else:
                        params["limit"] = 10

                    # 只保留 SQL 模板中的命名参数（非 limit 等辅助参数）
                    sql_params = {k: v for k, v in params.items()
                                  if f':{k}' in template["sql"]}

                    return {
                        "template": template_name,
                        "sql": template["sql"],
                        "params": sql_params,
                        "description": template["description"],
                    }

        return {
            "template": None,
            "sql": None,
            "params": {},
            "description": "无法理解的查询",
            "error": "未找到匹配的查询模板",
        }

    # 省级行政区后缀：库内 province 列不带后缀，用户问句常带（"广东省有多少个村"）
    _PROVINCE_SUFFIXES = ("省", "市", "自治区", "特别行政区")

    @staticmethod
    def _normalize_province(raw: str) -> str:
        """省份名归一化：去掉 省/市/自治区 等后缀，与库内口径一致。"""
        name = (raw or "").strip()
        for suffix in NLPQueryService._PROVINCE_SUFFIXES:
            if name.endswith(suffix) and len(name) > len(suffix):
                return name[: -len(suffix)]
        return name

    @staticmethod
    def _scope_subquery(db: Session, model: Any, user: Any) -> str:
        """数据域子查询文本（复用 core.data_permission 单一真源）。

        返回形如 SELECT id FROM xxx WHERE organization_id IN (...) 的文本，
        编译时 literal_binds 只产生整型字面量，无注入面；供模板 SQL 内联。
        user 为 None 时 apply_scope_filter 按"仅本人"过滤（fail-closed）。
        """
        from app.core.data_permission import apply_scope_filter

        query = apply_scope_filter(db.query(model.id), user, model, db=db)
        return str(query.statement.compile(compile_kwargs={"literal_binds": True}))

    @staticmethod
    def execute_query(db: Session, query: str, user: Any = None) -> Dict[str, Any]:
        """
        执行自然语言查询

        Args:
            db: 数据库会话
            query: 自然语言查询
            user: 当前用户（H13：模板 SQL 必须带数据域）。未传时 apply_scope_filter
                按"仅本人"处理（fail-closed），端点层必须显式透传 current_user。

        Returns:
            查询结果
        """
        # 解析查询
        parsed = NLPQueryService.parse_query(query)

        if not parsed["sql"]:
            return {
                "success": False,
                "error": parsed.get("error", "查询解析失败"),
                "query": query,
            }

        try:
            # 数据域子查询（模板按需内联；无占位符的模板不做额外查询）
            sql = parsed["sql"]
            if "{scope}" in sql or "{village_scope}" in sql:
                from app.models.fund import Fund
                from app.models.project import Project
                from app.models.supported_village import SupportedVillage

                scope_model = {
                    "village": SupportedVillage,
                    "project": Project,
                    "fund": Fund,
                }[parsed.get("scope") or "village"]
                scope_sql = NLPQueryService._scope_subquery(db, scope_model, user)
                sql = sql.replace("{village_scope}", scope_sql).replace("{scope}", scope_sql)

            # 执行SQL（参数化查询防止注入）
            stmt = text(sql)
            result = db.execute(stmt, parsed["params"])
            rows = result.fetchall()

            # 转换结果
            data = []
            if rows:
                columns = result.keys()
                for row in rows:
                    data.append(dict(zip(columns, row)))

            # 生成自然语言解释
            explanation = NLPQueryService._generate_explanation(parsed["template"], data, parsed["params"])

            return {
                "success": True,
                "data": data,
                "explanation": explanation,
                "sql": sql,
                "query": query,
            }

        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            return {"success": False, "error": str(e), "query": query}

    @staticmethod
    def _generate_explanation(template: str, data: List[Dict], params: Dict) -> str:
        """生成查询结果的自然语言解释"""
        if not data:
            return "未找到相关数据"

        if template == "village_count":
            count = data[0].get("count", 0)
            return f"系统中共有 {count} 个村庄"

        elif template == "village_by_province":
            count = data[0].get("count") or 0
            province = params.get("province", "")
            return f"{province}共有 {count} 个村庄"

        elif template == "project_count":
            count = data[0].get("count", 0)
            return f"系统中共有 {count} 个项目"

        elif template == "project_by_status":
            count = data[0].get("count", 0)
            status = params.get("status", "")
            return f"状态为 {status} 的项目有 {count} 个"

        elif template == "total_funds":
            # 空表时 SUM 返回 NULL（不是缺键）→ .get 的默认值不生效，
            # f"{None:,.2f}" 抛 TypeError 被 execute_query 的 except 吞掉，
            # 前端只看到"执行查询失败"。显式 or 0 归一。
            total = data[0].get("total") or 0
            return f"资金总额为 {float(total):,.2f} 元"

        elif template == "village_income":
            village_name = data[0].get("village_name", "")
            income = data[0].get("per_capita_income") or 0
            year = data[0].get("year", "")
            return f"{village_name}在 {year} 年的人均收入为 {float(income):,.2f} 元"

        elif template == "top_villages_by_income":
            top_village = data[0]
            count = len(data)
            per_capita = top_village.get("per_capita_income") or 0
            return (
                f"收入最高的村庄是 {top_village.get('village_name', '')}，"
                f"人均收入 {float(per_capita):,.2f} 元。共查询到 {count} 个村庄的数据。"
            )

        return f"查询成功，返回 {len(data)} 条记录"
