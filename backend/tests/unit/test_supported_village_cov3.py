"""app.api.v1.supported_village 三轮覆盖补全

覆盖缺口（基线 miss）：
- 425：_process_import_row 字段超长 → 行级失败
- 515：list_villages year_start 年份过滤
- 860 / 865：update_village update_dict 含 id 键 continue 与未知字段 warning 跳过
- 1011：purge_village 级联删除 success=False → 404
- 1123-1144：delete_yearly_section 全分支（未知板块 400 / 数据不存在 404 /
  行不存在跳过物理删除 / 正常删除+审计）
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.supported_village as sv


def _admin():
    return SimpleNamespace(id=1, role="super_admin", username="admin", organization_id=10)


def _q(**kw):
    q = MagicMock()
    for attr in ("filter", "order_by", "offset", "limit"):
        getattr(q, attr).return_value = q
    q.options.return_value = q
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    q.count.return_value = kw.get("count", 0)
    return q


class TestProcessImportRowTooLong:
    def test_field_exceeds_max_length(self):
        # 覆盖 supported_village.py:425 —— village_name 超 200 字符限制
        ok, msg = sv._process_import_row(
            row=("A" * 201,),
            col_map={"village_name": 0},
            db=MagicMock(),
            row_idx=3,
        )
        assert ok is False
        assert "长度超过" in msg
        assert "village_name" in msg
        assert "第3行" in msg

    def test_bool_field_empty_cell_keeps_none(self):
        # 覆盖 supported_village.py:410 —— 布尔导入字段空单元格保持 None（不写 False）
        db = MagicMock()
        db.query.return_value = _q(first=None)  # 无重复村
        ok, msg = sv._process_import_row(
            row=("村A", None, ""),
            col_map={
                "village_name": 0,
                "is_revitalization_tier": 1,  # None 单元格
                "is_three_regions": 2,        # 空字符串单元格
            },
            db=db,
            row_idx=1,
            current_user=_admin(),
        )
        assert ok is True
        db.add.assert_called_once()
        added = db.add.call_args.args[0]
        # 空值布尔字段不写入（None 被 433 行过滤）
        assert not hasattr(added, "is_revitalization_tier") or added.is_revitalization_tier is None


class TestListVillagesYearStart:
    async def test_year_start_filter_applied(self):
        # 覆盖 supported_village.py:515 —— year_start 按 strftime('%Y') 过滤
        village = MagicMock()
        village.to_dict.return_value = {"id": 1, "villageName": "村A"}
        db = MagicMock()
        db.query.return_value = _q(all=[village], count=1)
        with (
            patch.object(sv, "apply_scope_filter", side_effect=lambda q, *a, **k: q),
            patch("app.core.cache.get_cache_service", AsyncMock(return_value=None)),
        ):
            result = await sv.list_villages(
                page=1, page_size=20, keyword=None, department=None, county=None,
                year_start=2024, is_revitalization_tier=None, is_three_regions=None,
                include_deleted=False, current_user=_admin(), db=db,
            )
        assert result is not None
        # year_start 过滤产生额外 filter 调用（is_active + year_start）
        assert db.query.return_value.filter.called


class TestUpdateVillageDictGuards:
    async def test_id_key_skipped_and_unknown_field_warned(self):
        # 覆盖 supported_village.py:860（id 键 continue）与 865（未知字段 warning 跳过）
        village = SimpleNamespace(id=1, village_name="村A")
        fake_data = SimpleNamespace(
            model_dump=lambda exclude_unset=False: {
                "id": 999,          # 860：id 键跳过
                "village_name": "新名",
                "department": "某部门",  # 865：village 上不存在 → warning 跳过
            }
        )
        db = MagicMock()
        with (
            patch.object(sv, "_get_village_or_404", return_value=village),
            patch.object(sv, "safe_commit"),
            patch.object(sv, "_invalidate_village_cache", AsyncMock()),
            patch.object(sv, "_record_village_change"),
            patch.object(sv, "submit_entity_change_approval", return_value=77),
        ):
            result = await sv.update_village(
                1, data=fake_data, current_user=_admin(), db=db
            )
        assert village.id == 1          # id 未被 update_dict 覆盖
        assert village.village_name == "新名"
        assert not hasattr(village, "department")  # 未知字段未 setattr
        assert result["data"]["approval_task_id"] == 77


class TestPurgeVillageStatsFailure:
    async def test_stats_failure_404(self):
        # 覆盖 supported_village.py:1011 —— 级联删除 success=False → 404
        village = SimpleNamespace(is_active=False, village_name="村A")
        data = SimpleNamespace(confirm_password="pw")
        db = MagicMock()
        with (
            patch("app.core.security.verify_password", return_value=True),
            patch.object(sv, "_get_village_or_404", return_value=village),
            patch(
                "app.services.village_cascade_delete_service.VillageCascadeDeleteService"
            ) as m_svc,
        ):
            m_svc.return_value.delete_village_cascade.return_value = {
                "success": False, "message": "关联数据校验失败",
            }
            with pytest.raises(HTTPException) as exc_info:
                await sv.purge_village(1, data=data, current_user=_admin(), db=db)
        assert exc_info.value.status_code == 404
        assert "关联数据校验失败" in exc_info.value.detail


class TestDeleteYearlySection:
    async def test_unknown_section_400(self):
        # 覆盖 supported_village.py:1123-1124 —— 未知板块名 → 400
        with pytest.raises(HTTPException) as exc_info:
            await sv.delete_yearly_section(
                1, 2026, "bad-section", current_user=_admin(), db=MagicMock()
            )
        assert exc_info.value.status_code == 400

    async def test_data_missing_404(self):
        # 覆盖 supported_village.py:1128-1129 —— 年度数据不存在 → 404
        db = MagicMock()
        with (
            patch.object(sv, "_get_village_or_404"),
            patch.object(sv, "_get_section_data", return_value=None),
            pytest.raises(HTTPException) as exc_info,
        ):
            await sv.delete_yearly_section(
                1, 2026, "population", current_user=_admin(), db=db
            )
        assert exc_info.value.status_code == 404

    async def test_row_missing_still_succeeds(self):
        # 覆盖 1135 行为假分支 —— 数据存在但行对象缺失 → 跳过物理删除仍成功
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with (
            patch.object(sv, "_get_village_or_404"),
            patch.object(sv, "_get_section_data", return_value={"x": 1}),
            patch.object(sv, "_record_village_change"),
            patch.object(sv, "_invalidate_village_cache", AsyncMock()),
        ):
            result = await sv.delete_yearly_section(
                1, 2026, "population", current_user=_admin(), db=db
            )
        assert "已删除" in result["message"]
        db.delete.assert_not_called()

    async def test_success_deletes_row_and_audits(self):
        # 覆盖 supported_village.py:1130-1144 —— 物理删除 + 审计留痕
        row = SimpleNamespace(id=5)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = row
        with (
            patch.object(sv, "_get_village_or_404"),
            patch.object(sv, "_get_section_data", return_value={"x": 1}),
            patch.object(sv, "_record_village_change") as m_record,
            patch.object(sv, "_invalidate_village_cache", AsyncMock()),
            patch.object(sv, "safe_commit"),
        ):
            result = await sv.delete_yearly_section(
                1, 2026, "population", current_user=_admin(), db=db
            )
        db.delete.assert_called_once_with(row)
        m_record.assert_called_once()
        assert "population" in result["message"]
