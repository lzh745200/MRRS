"""app.api.v1.supported_village 覆盖率攻坚测试（缺口补丁）

覆盖：_get_section_data 列循环与村委会成员分支、_save_section_data 成员替换、
_get_village_or_404 越权 403、_invalidate_village_cache 真实缓存路径、
list_villages 缓存读写与异常降级、dropdown 下拉端点、update_village 过渡状态
审批+审计（bug#12 修复后真实可达）、validate_yearly_data 校验与同比预警、
download_section_attachment 三分支。
"""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import app.api.v1.supported_village as sv
from app.models.supported_village import (
    VillageCommitteeInfo,
    VillageCommitteeMember,
    VillageIncome,
)


def _admin():
    return SimpleNamespace(id=1, role="super_admin", username="admin", organization_id=10)


def _q(**kw):
    q = MagicMock()
    for attr in ("filter", "order_by", "offset", "limit"):
        getattr(q, attr).return_value = q
    q.options.return_value = q  # _get_village_or_404 走 .options(selectinload(...)).first() 链
    q.first.return_value = kw.get("first")
    q.all.return_value = kw.get("all", [])
    q.count.return_value = kw.get("count", 0)
    return q


class TestGetSectionData:
    def test_column_loop_skips_metadata_and_camelizes(self):
        row = VillageIncome(per_capita_income=1.5, collective_income=10.0)
        db = MagicMock()
        db.query.return_value = _q(first=row)
        result = sv._get_section_data(db, VillageIncome, 1, 2026)
        assert result["perCapitaIncome"] == 1.5
        assert result["collectiveIncome"] == 10.0
        assert "supported_village_id" not in result
        assert "supportedVillageId" not in result

    def test_committee_loads_members(self):
        info = VillageCommitteeInfo(id=9, overview="概况")
        member = VillageCommitteeMember(name="张三", position="主任", phone="123",
                                        is_veteran=True, remark="备注")
        db = MagicMock()
        db.query = MagicMock(side_effect=[_q(first=info), _q(all=[member])])
        result = sv._get_section_data(db, VillageCommitteeInfo, 1, 2026)
        assert result["members"][0]["name"] == "张三"
        assert result["members"][0]["isVeteran"] is True


class TestSaveSectionDataMembers:
    def test_replace_committee_members(self):
        existing = VillageCommitteeInfo(id=9)
        db = MagicMock()
        db.query.return_value = _q(first=existing)
        data = {
            "overview": "新概况",
            "members": [
                {"name": "李四", "position": "委员", "phone": "1",
                 "isVeteran": True, "remark": "r"},
                "not-a-dict",  # 非 dict 成员被跳过
            ],
        }
        row = sv._save_section_data(db, VillageCommitteeInfo, 1, 2026, data)
        assert row is existing
        assert row.overview == "新概况"
        added = [c.args[0] for c in db.add.call_args_list]
        assert any(getattr(a, "name", None) == "李四" for a in added)


class TestGetVillageOr404:
    def test_forbidden_when_record_access_denied(self):
        db = MagicMock()
        db.query.return_value = _q(first=SimpleNamespace(id=1))
        with patch.object(sv, "check_record_access", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                sv._get_village_or_404(db, 1, _admin())
        assert exc_info.value.status_code == 403


class TestInvalidateVillageCache:
    async def test_deletes_list_cache(self):
        cache = MagicMock()
        cache.delete_by_prefix = AsyncMock()
        with (
            patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}),
            patch("app.core.cache.get_cache_service", AsyncMock(return_value=cache)),
        ):
            await sv._invalidate_village_cache()
        cache.delete_by_prefix.assert_awaited_once_with("villages:list:")

    async def test_cache_error_swallowed(self):
        with (
            patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}),
            patch("app.core.cache.get_cache_service", AsyncMock(side_effect=Exception("down"))),
        ):
            await sv._invalidate_village_cache()  # 不向外抛


class TestListVillagesCache:
    def _db(self, villages):
        db = MagicMock()
        db.query.return_value = _q(all=villages, count=len(villages))
        return db

    async def test_cache_miss_then_set(self):
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        village = MagicMock()
        village.to_dict.return_value = {"id": 1, "villageName": "村A"}
        with (
            patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}),
            patch("app.core.cache.get_cache_service", AsyncMock(return_value=cache)),
            patch.object(sv, "apply_scope_filter", side_effect=lambda q, *a, **k: q),
        ):
            result = await sv.list_villages(
                page=1, page_size=20, keyword=None, department=None, county=None,
                is_revitalization_tier=None, is_three_regions=None, include_deleted=False,
                current_user=_admin(), db=self._db([village]),
            )
        cache.set.assert_awaited_once()
        assert result is not None

    async def test_cache_hit_short_circuits(self):
        cache = MagicMock()
        cache.get = AsyncMock(return_value={"cached": True})
        with (
            patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}),
            patch("app.core.cache.get_cache_service", AsyncMock(return_value=cache)),
        ):
            result = await sv.list_villages(
                page=1, page_size=20, keyword=None, department=None, county=None,
                is_revitalization_tier=None, is_three_regions=None, include_deleted=False,
                current_user=_admin(), db=MagicMock(),
            )
        assert result == {"cached": True}

    async def test_cache_type_error_degrades_to_db(self):
        cache = MagicMock()
        cache.get = AsyncMock(side_effect=TypeError("bad cache"))
        village = MagicMock()
        village.to_dict.return_value = {"id": 2, "villageName": "村B"}
        with (
            patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}),
            patch("app.core.cache.get_cache_service", AsyncMock(return_value=cache)),
            patch.object(sv, "apply_scope_filter", side_effect=lambda q, *a, **k: q),
        ):
            result = await sv.list_villages(
                page=1, page_size=20, keyword=None, department=None, county=None,
                is_revitalization_tier=None, is_three_regions=None, include_deleted=False,
                current_user=_admin(), db=self._db([village]),
            )
        cache.set.assert_not_called()  # _ckey 已置 None，跳过回写
        assert result is not None


class TestVillageDropdown:
    async def test_dropdown_items(self):
        db = MagicMock()
        db.query.return_value = _q(all=[(1, "村A", "县X"), (2, "村B", None)])
        with patch.object(sv, "apply_scope_filter", side_effect=lambda q, *a, **k: q):
            result = await sv.get_village_dropdown(current_user=_admin(), db=db)
        text = str(result)
        assert "村A" in text and "村B" in text and "县X" in text


class TestUpdateVillageTransition:
    def _db(self, village):
        db = MagicMock()
        db.query.return_value = _q(first=village)
        return db

    async def test_transition_change_requires_manager_and_audits(self):
        village = SimpleNamespace(id=1, transition_status="none", village_name="村A")
        data = sv.SupportedVillageUpdate(transition_status="entering")
        with (
            patch.object(sv, "check_record_access", return_value=True),
            patch("app.utils.audit_logger.AuditLogger.log") as audit_log,
        ):
            result = await sv.update_village(1, data=data, current_user=_admin(),
                                             db=self._db(village))
        audit_log.assert_called_once()
        assert village.transition_status == "entering"
        assert result["message"] == "更新成功"

    async def test_transition_change_forbidden_for_non_manager(self):
        village = SimpleNamespace(id=1, transition_status="none", village_name="村A")
        data = sv.SupportedVillageUpdate(transition_status="entering")
        user = SimpleNamespace(id=2, role="viewer", username="v", organization_id=10,
                               is_superuser=False)
        with (
            patch.object(sv, "check_record_access", return_value=True),
            pytest.raises(HTTPException) as exc_info,
        ):
            await sv.update_village(1, data=data, current_user=user, db=self._db(village))
        assert exc_info.value.status_code == 403


class TestValidateYearlyData:
    @staticmethod
    def _db_sequence(records):
        """按调用顺序返回预置 first() 结果的 db mock。"""
        db = MagicMock()
        db.query = MagicMock(side_effect=[_q(first=r) for r in records])
        return db

    async def test_all_sections_missing(self):
        n = len(sv._SECTION_MODEL)
        db = self._db_sequence([None] * (n * 2))  # 当年 + 前一年均无记录
        with patch.object(sv, "_get_village_or_404"):
            result = await sv.validate_yearly_data(1, 2026, current_user=_admin(), db=db)
        assert result["data"]["valid"] is False
        assert len(result["data"]["errors"]) == n
        assert result["data"]["warnings"] == []

    async def test_negative_value_error_and_yoy_warning(self):
        n = len(sv._SECTION_MODEL)
        # _SECTION_MODEL 顺序：population, income, ... —— income 在索引 1
        current = [None, SimpleNamespace(per_capita_income=-5.0)] + [None] * (n - 2)
        previous = [None, SimpleNamespace(per_capita_income=100.0)] + [None] * (n - 2)
        db = self._db_sequence(current + previous)
        with patch.object(sv, "_get_village_or_404"):
            result = await sv.validate_yearly_data(1, 2026, current_user=_admin(), db=db)
        assert any("不能为负数" in e["message"] for e in result["data"]["errors"])
        assert any("同比变动" in w["message"] for w in result["data"]["warnings"])


class TestDownloadSectionAttachment:
    async def test_download_success(self):
        attachment = SimpleNamespace(file_path="/tmp/x.txt", file_name="x.txt",
                                     mime_type="text/plain")
        db = MagicMock()
        db.query.return_value = _q(first=attachment)
        with (
            patch.object(sv, "_get_village_or_404"),
            patch("os.path.exists", return_value=True),
        ):
            resp = await sv.download_section_attachment(
                1, "income", 3, current_user=_admin(), db=db)
        assert resp.media_type == "text/plain"

    async def test_attachment_not_found_404(self):
        db = MagicMock()
        db.query.return_value = _q(first=None)
        with (
            patch.object(sv, "_get_village_or_404"),
            pytest.raises(HTTPException) as exc_info,
        ):
            await sv.download_section_attachment(1, "income", 3, current_user=_admin(), db=db)
        assert exc_info.value.status_code == 404

    async def test_file_missing_404(self):
        attachment = SimpleNamespace(file_path="/tmp/gone.txt", file_name="g.txt",
                                     mime_type=None)
        db = MagicMock()
        db.query.return_value = _q(first=attachment)
        with (
            patch.object(sv, "_get_village_or_404"),
            patch("os.path.exists", return_value=False),
            pytest.raises(HTTPException) as exc_info,
        ):
            await sv.download_section_attachment(1, "income", 3, current_user=_admin(), db=db)
        assert exc_info.value.status_code == 404
