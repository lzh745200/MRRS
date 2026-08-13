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
    # SQL 全部使用参数化占位符 (:param) 防止注入
    QUERY_TEMPLATES = {
        "village_by_province": {
            "patterns": [r"(.+?省)有多少个?村", r"(.+?的)村庄"],
            "sql": "SELECT COUNT(*) as count FROM supported_villages WHERE province = :province",
            "description": "查询指定省份的村庄数量",
        },
        "village_count": {
            "patterns": [r"有多少个?村", r"村庄数量", r"村的数量"],
            "sql": "SELECT COUNT(*) as count FROM supported_villages",
            "description": "查询村庄总数",
        },
        "project_count": {
            "patterns": [r"有多少个?项目", r"项目数量"],
            "sql": "SELECT COUNT(*) as count FROM projects",
            "description": "查询项目总数",
        },
        "project_by_status": {
            "patterns": [r"(.+?)状态的项目", r"(.+?)的项目有多少"],
            "sql": "SELECT COUNT(*) as count FROM projects WHERE status = :status",
            "description": "查询指定状态的项目数量",
        },
        "total_funds": {
            "patterns": [r"总资金", r"资金总额", r"投入了多少资金"],
            "sql": "SELECT SUM(amount) as total FROM funds",
            "description": "查询资金总额",
        },
        "village_income": {
            "patterns": [r"(.+?)村的收入", r"(.+?)的人均收入"],
            "sql": """
                SELECT sv.village_name, vi.per_capita_income, vi.year
                FROM supported_villages sv
                JOIN village_income vi ON sv.id = vi.supported_village_id
                WHERE sv.village_name LIKE '%' || :village_name || '%'
                ORDER BY vi.year DESC
                LIMIT 1
            """,
            "description": "查询村庄收入",
        },
        "top_villages_by_income": {
            "patterns": [r"收入最高的.*?村", r"人均收入排名", r"收入前.*?名"],
            "sql": """
                SELECT sv.village_name, vi.per_capita_income, vi.year
                FROM supported_villages sv
                JOIN village_income vi ON sv.id = vi.supported_village_id
                WHERE vi.year = (SELECT MAX(year) FROM village_income)
                ORDER BY vi.per_capita_income DESC
                LIMIT :limit
            """,
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
                            params["province"] = match.group(1)
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

    @staticmethod
    def execute_query(db: Session, query: str) -> Dict[str, Any]:
        """
        执行自然语言查询

        Args:
            db: 数据库会话
            query: 自然语言查询

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
            # 执行SQL（参数化查询防止注入）
            stmt = text(parsed["sql"])
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
                "sql": parsed["sql"],
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
            count = data[0].get("count", 0)
            province = params.get("province", "")
            return f"{province}省共有 {count} 个村庄"

        elif template == "project_count":
            count = data[0].get("count", 0)
            return f"系统中共有 {count} 个项目"

        elif template == "project_by_status":
            count = data[0].get("count", 0)
            status = params.get("status", "")
            return f"状态为 {status} 的项目有 {count} 个"

        elif template == "total_funds":
            total = data[0].get("total", 0)
            return f"资金总额为 {total:,.2f} 元"

        elif template == "village_income":
            village_name = data[0].get("village_name", "")
            income = data[0].get("per_capita_income", 0)
            year = data[0].get("year", "")
            return f"{village_name}在 {year} 年的人均收入为 {income:,.2f} 元"

        elif template == "top_villages_by_income":
            top_village = data[0]
            count = len(data)
            per_capita = top_village.get("per_capita_income", 0)
            return (
                f"收入最高的村庄是 {top_village.get('village_name', '')}，"
                f"人均收入 {per_capita:,.2f} 元。共查询到 {count} 个村庄的数据。"
            )

        return f"查询成功，返回 {len(data)} 条记录"
