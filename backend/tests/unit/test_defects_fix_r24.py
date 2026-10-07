# -*- coding: utf-8 -*-
"""R24 缺陷修复回归测试。

覆盖 QA 工程师在分支覆盖清零过程中上报的 2 处源码潜在缺陷
（均可复现，非假阳性）。每个用例在修复前失败、修复后通过：

- 缺陷 1：`_setup_preview_entity` 对不在 project/fund/school 分发链上的
  entity_type，走到 getattr 时 EntityModel 未绑定 → NameError（500）。
  修复后入口白名单拦截，返回 400 + 明确文案。
- 缺陷 2：`recommend_fund_allocation` 在 total_score<=0（如人口数为负的脏数据）
  时跳过金额分配，排序阶段引用 x["recommended_amount"] → KeyError（500）。
  修复后排序前补 recommended_amount=0，结构稳定且正常路径语义不变。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.import_export.import_data import _setup_preview_entity
from app.services.ai.recommendation_service import RecommendationService


# ==================== 缺陷 1：预览实体分发白名单 ====================


class TestPreviewEntityWhitelist:
    """import_data.py `_setup_preview_entity` 入口白名单校验。"""

    def test_unsupported_entity_type_rejected_with_400(self):
        """修复前：NameError；修复后：HTTPException(400)。"""
        with pytest.raises(HTTPException) as ei:
            _setup_preview_entity("unknown_entity", MagicMock())
        assert ei.value.status_code == 400
        # 文案需带上不支持的类型值，便于排查
        assert "unknown_entity" in ei.value.detail
        assert "不支持的实体类型" in ei.value.detail

    def test_known_entity_type_still_dispatches(self):
        """修复不得破坏正常路径：project/fund/school 仍可正常返回三元组。"""
        db = MagicMock()
        db.query.return_value.all.return_value = []

        validator, duplicate_field, existing_names = _setup_preview_entity("fund", db)

        assert validator is not None
        assert duplicate_field  # 非空字符串
        assert existing_names == set()


# ==================== 缺陷 2：资金分配金额兜底 ====================


def _patch_scoped_filter():
    """绕过数据权限过滤（与既有 recommendation 测试口径一致）。"""
    return patch("app.services.data_scope_query.scoped_filter", side_effect=lambda query, *a, **k: query)


class TestFundAllocationAmountBackfill:
    """recommendation_service.py `recommend_fund_allocation` 排序前补键。"""

    @staticmethod
    def _db_with(villages, pop_rows, inc_rows):
        q_villages, q_pop_meta, q_pop, q_inc_meta, q_inc = (MagicMock() for _ in range(5))
        q_villages.filter.return_value.all.return_value = villages
        q_pop.join.return_value.all.return_value = pop_rows
        q_inc.join.return_value.all.return_value = inc_rows
        db = MagicMock()
        db.query.side_effect = [q_villages, q_pop_meta, q_pop, q_inc_meta, q_inc]
        return db

    def test_non_positive_total_score_no_keyerror(self):
        """修复前：排序阶段 KeyError；修复后：返回且金额补 0。"""
        villages = [SimpleNamespace(id=1, village_name="A"), SimpleNamespace(id=2, village_name="B")]
        # 村庄 1 人口为负（脏数据）→ 总分 <= 0，跳过金额分配
        pop_rows = [
            SimpleNamespace(supported_village_id=1, population=-100000, year=2024),
            SimpleNamespace(supported_village_id=2, population=0, year=2024),
        ]
        db = self._db_with(villages, pop_rows, [])

        with _patch_scoped_filter():
            result = RecommendationService.recommend_fund_allocation(db, total_budget=1000.0, village_ids=[1, 2])

        allocations = result["allocations"]
        assert len(allocations) == 2
        assert all(a["recommended_amount"] == 0.0 for a in allocations)

    def test_normal_path_allocation_unchanged(self):
        """正分场景：正常分配结果不受兜底逻辑影响（金额>0 且合计≈总预算）。"""
        villages = [SimpleNamespace(id=1, village_name="A"), SimpleNamespace(id=2, village_name="B")]
        pop_rows = [
            SimpleNamespace(supported_village_id=1, population=10000, year=2024),
            SimpleNamespace(supported_village_id=2, population=5000, year=2024),
        ]
        db = self._db_with(villages, pop_rows, [])

        with _patch_scoped_filter():
            result = RecommendationService.recommend_fund_allocation(db, total_budget=1000.0, village_ids=[1, 2])

        allocations = result["allocations"]
        assert all(a["recommended_amount"] > 0 for a in allocations)
        # 按金额降序：人口多的村庄应排在前面
        assert allocations[0]["village_id"] == 1
        assert sum(a["recommended_amount"] for a in allocations) == pytest.approx(1000.0, abs=0.02)
