"""
村庄级联删除服务
由于 SQLite 外键约束未正确设置 CASCADE,需要在应用层实现级联删除
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

#: 可容忍的 schema 差异错误特征（表/列不存在）——部署版本落后于代码时出现
_MISSING_SCHEMA_HINTS = (
    "no such table",
    "no such column",
    "does not exist",
    "unknown column",
    "has no column named",
)


def _is_missing_schema_error(exc: Exception) -> bool:
    """判断异常是否为"表/列不存在"这类可容忍的 schema 差异（深审 #72）。"""
    message = str(getattr(exc, "orig", exc)).lower()
    return any(hint in message for hint in _MISSING_SCHEMA_HINTS)


class VillageCascadeDeleteService:
    """村庄级联删除服务"""

    # 需要级联删除的表(按依赖顺序)
    DEPENDENT_TABLES = [
        # 年度数据表
        ("annual_population", "supported_village_id"),
        ("annual_infrastructure", "supported_village_id"),
        ("annual_industry", "supported_village_id"),
        ("annual_income", "supported_village_id"),
        # 帮扶支持表
        ("consumption_support", "supported_village_id"),
        ("education_support", "supported_village_id"),
        ("employment_support", "supported_village_id"),
        ("force_investment", "supported_village_id"),
        ("industry_support", "supported_village_id"),
        ("infrastructure_improvement", "supported_village_id"),
        ("medical_support", "supported_village_id"),
        ("party_building_support", "supported_village_id"),
        ("support_funding", "supported_village_id"),
        # 村委会信息
        ("village_committee_members", "supported_village_id"),
        ("village_committee_info", "supported_village_id"),
        # 村庄数据
        ("village_income", "supported_village_id"),
        ("village_population", "supported_village_id"),
        # 资金和项目
        ("fund_transactions", "village_id"),
        ("fund_budgets", "village_id"),
        ("funds", "village_id"),
        ("projects", "village_id"),
        # 工作日志
        ("work_logs", "village_id"),
    ]

    def __init__(self, db: Session):
        self.db = db

    def delete_village_cascade(self, village_id: int) -> dict:
        """
        级联删除村庄及其所有相关数据

        Args:
            village_id: 村庄ID

        Returns:
            删除统计信息
        """
        logger.info(f"开始级联删除村庄 ID={village_id}")

        delete_stats = {}
        total_deleted = 0

        try:
            # 1. 删除所有依赖表的记录
            for table_name, column_name in self.DEPENDENT_TABLES:
                try:
                    result = self.db.execute(
                        text(f"DELETE FROM {table_name} WHERE {column_name} = :village_id"),  # nosec B608
                        {"village_id": village_id},
                    )
                    deleted_count = result.rowcount
                    if deleted_count > 0:
                        delete_stats[table_name] = deleted_count
                        total_deleted += deleted_count
                        logger.info(f"  删除 {table_name}: {deleted_count} 条记录")
                except (OperationalError, ProgrammingError) as e:
                    # 深审 #72：仅"表/列不存在"这类 schema 差异可容忍（部署版本
                    # 落后于代码时新表尚未建）；其余 SQL 错误（如 database is
                    # locked、约束冲突）此前也被 warning 吞掉，导致主行删除成功
                    # 但依赖行残留、计数漏报。现在只有 schema 类错误降级为警告，
                    # 其余一律回滚并向上抛出。
                    if _is_missing_schema_error(e):
                        logger.warning(f"  删除 {table_name} 跳过（表/列不存在）: {e}")
                        continue
                    raise

            # 2. 删除村庄本身
            result = self.db.execute(
                text("DELETE FROM supported_villages WHERE id = :village_id"),
                {"village_id": village_id},
            )
            village_deleted = result.rowcount

            if village_deleted == 0:
                logger.warning(f"村庄 ID={village_id} 不存在")
                return {"success": False, "message": "村庄不存在", "deleted_records": 0}

            # 3. 提交事务
            safe_commit(self.db)

            logger.info(f"级联删除完成: 村庄 ID={village_id}, 总计删除 {total_deleted + 1} 条记录")

            return {
                "success": True,
                "message": "删除成功",
                "village_id": village_id,
                "deleted_records": total_deleted + 1,
                "details": delete_stats,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"级联删除失败: {e}", exc_info=True)
            raise

    def check_village_references(self, village_id: int) -> dict:
        """
        检查村庄的引用情况

        Args:
            village_id: 村庄ID

        Returns:
            引用统计信息
        """
        reference_stats = {}
        total_refs = 0

        for table_name, column_name in self.DEPENDENT_TABLES:
            try:
                result = self.db.execute(
                    text(f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} = :village_id"),  # nosec B608
                    {"village_id": village_id},
                )
                count = result.scalar()
                if count > 0:
                    reference_stats[table_name] = count
                    total_refs += count
            except Exception as e:  # noqa: BLE001
                # 表可能不存在,忽略；其余错误留痕便于排查引用统计失真
                if "no such table" not in str(e).lower():
                    logger.warning("村引用检查查询失败(忽略): %s", e)

        return {
            "village_id": village_id,
            "total_references": total_refs,
            "details": reference_stats,
        }
