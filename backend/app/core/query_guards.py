"""软删除查询防线（统计口径统一出口）。

背景：v1.10 前累计出现约 45 处统计出口遗漏 is_active 过滤，导致软删数据
混入成效评估、KPI、报表等口径。本模块提供唯一推荐的过滤入口，
配合 scripts/check_soft_delete_usage.py 静态扫描形成双保险。

约定（AGENTS.md《Soft Delete Pattern》同步条款）：
- 任何针对软删模型（SOFT_DELETE_MODELS）的聚合/列表/导出查询，
  必须经由 active_filter() 或 guarded_query() 施加过滤；
- 按 id 取详情（_get_*_or_404）与回收站管理端点（include_deleted=true）
  属白名单场景，无需过滤但必须走 enforce_admin_include_deleted 收敛。
"""

from typing import Any

from sqlalchemy import ColumnElement

# 启用软删除的模型注册表：模型类 -> 对应 is_active 列所属表
# （供扫描脚本与运行时反射使用；新增软删模型必须登记于此）
SOFT_DELETE_MODEL_NAMES = frozenset({
    "SupportedVillage",
    "Project",
    "Fund",
    "School",
})


def active_filter(model: Any) -> ColumnElement:
    """返回 model.is_active == True 过滤条件。

    用法::

        db.query(Project).filter(
            active_filter(Project),
            Project.status == "active",
        )

    亦可与其他条件并列放入 filter()，便于静态扫描器识别。
    """
    return model.is_active == True  # noqa: E712


def guarded_query(db: Any, model: Any):
    """返回已施加软删过滤的 query（一步到位版）。"""
    return db.query(model).filter(active_filter(model))
