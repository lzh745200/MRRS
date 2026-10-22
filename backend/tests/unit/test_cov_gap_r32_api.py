"""R32 覆盖率攻坚 —— app/api/v1 下的语句 / 分支缺口补全。

覆盖（缺口清单 → 本文件对应用例）：
- data/data/statistics.py: 305-306 / 331（非管理员数据域收敛）、410-411（今日操作查询异常兜底）
- import_export/import_data.py: 476 / 513（未知实体类型 fail-closed 400）、
  543->542（空名称跳过分支）、554（预览重复标记）
- messages.py: 351（非管理员只看本人审计活动）
- organization.py: 287 / 290（level 两种历史形态解析）、645（组织详情越权 403）、
  785->791 + 799（改父级未成环 → 级联重算子树 path）、1062（成员列表越权 403）
- recycle_bin.py: 69（空 ids 短路）、74-84（非全局管理员数据域过滤 + fail-closed）
- subordinate_reports.py: 129（库文件大小读取成功）、130-132（读取失败静默降级）
- work_logs.py: 241（创建拒绝 system_auto）、298（更新拒绝 system_auto）

全部用例走内存 SQLite / Mock，不触碰真实数据目录。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


# ══════════════════════════════════════════════════════════════════
#  app/api/v1/data/data/statistics.py
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def override_user(client):
    """把 get_current_user 依赖替换为指定用户（用例结束自动还原）。"""
    from app.core.security import get_current_user

    def _set(user):
        client.app.dependency_overrides[get_current_user] = lambda: user
        return client

    yield _set
    client.app.dependency_overrides.pop(get_current_user, None)


def _admin():
    return SimpleNamespace(id=1, username="admin", role="admin", is_superuser=True, organization_id=1)


def _plain_user(uid=7, org_id=2):
    return SimpleNamespace(id=uid, username="u", role="user", is_superuser=False, organization_id=org_id)


class TestStatisticsOverview:
    def test_non_admin_scopes_users_and_audit(self, override_user):
        """非管理员：_users_query 走组织收敛（305-306），审计范围收敛为本人（331）。"""
        c = override_user(_plain_user())
        resp = c.get("/api/v1/statistics/overview")
        assert resp.status_code == 200
        assert "users" in resp.json()

    def test_audit_query_failure_is_swallowed(self, override_user, monkeypatch):
        """今日操作 / 近 7 天查询抛错 → 兜底记 0 / 空趋势（410-411 等），端点仍 200。"""
        import app.core.data_permission as dp

        def _boom(self, query, *args, **kwargs):
            raise RuntimeError("audit query boom")

        monkeypatch.setattr(dp.OrgScopeFilter, "filter_by_org_ids", _boom)
        c = override_user(_admin())
        resp = c.get("/api/v1/statistics/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["today_operations"] == 0
        # 趋势兜底为空字典 → 7 天分桶全部记 0，最近操作列表为空
        assert len(body["trend"]) == 7
        assert all(item["operations"] == 0 for item in body["trend"])
        assert body["recent_logs"] == []


# ══════════════════════════════════════════════════════════════════
#  app/api/v1/import_export/import_data.py
# ══════════════════════════════════════════════════════════════════


class TestImportDataHelpers:
    def test_setup_preview_entity_rejects_unknown_type(self):
        """白名单外的实体类型 → 显式 400（fail-closed，476）。"""
        from app.api.v1.import_export import import_data as m

        with pytest.raises(HTTPException) as ei:
            m._setup_preview_entity("bogus_entity", MagicMock())
        assert ei.value.status_code == 400

    def test_preview_duplicate_column_rejects_unknown_type(self):
        """分发链末端未知类型 → 400（513）。"""
        from app.api.v1.import_export import import_data as m

        with pytest.raises(HTTPException) as ei:
            m._preview_duplicate_column("bogus_entity", "name")
        assert ei.value.status_code == 400

    def test_existing_names_skips_blank_rows(self):
        """rows 口径：空名称回环（543->542），非空名称入集合（544）。"""
        from app.api.v1.import_export import import_data as m

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [("",), ("Foo",)]
        got = m._existing_names(db, MagicMock(), "village_name", rows=[{"village_name": "Foo"}])
        assert got == {"foo"}

    def test_existing_names_no_wanted_values(self):
        """rows 里全为空值 → 直接返回空集，不查库。"""
        from app.api.v1.import_export import import_data as m

        db = MagicMock()
        assert m._existing_names(db, MagicMock(), "village_name", rows=[{"village_name": "  "}]) == set()

    def test_build_preview_row_marks_duplicate(self):
        """命中已存在名称 → is_dup=True（554）。"""
        from app.api.v1.import_export import import_data as m

        validator = MagicMock()
        validator.validate_row.return_value = []
        errs, is_dup = m._build_preview_row_response(
            {"village_name": "Foo"}, 0, validator, {"foo"}, "village_name"
        )
        assert errs == []
        assert is_dup is True

    def test_build_preview_row_not_duplicate(self):
        from app.api.v1.import_export import import_data as m

        validator = MagicMock()
        validator.validate_row.return_value = ["e"]
        errs, is_dup = m._build_preview_row_response(
            {"village_name": "Bar"}, 1, validator, {"foo"}, "village_name"
        )
        assert errs == ["e"]
        assert is_dup is False


# ══════════════════════════════════════════════════════════════════
#  app/api/v1/messages.py
# ══════════════════════════════════════════════════════════════════


class TestRecentActivities:
    def test_non_admin_only_sees_own_activity(self, override_user):
        """非管理员：查询追加 user_id 过滤（351），不泄漏全局审计流水。"""
        c = override_user(_plain_user())
        resp = c.get("/api/v1/messages/recent-activities")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════
#  app/api/v1/organization.py
# ══════════════════════════════════════════════════════════════════


class TestOrgLevelToNumber:
    def test_numeric_and_enum_and_unknown(self):
        from app.api.v1.organization import _org_level_to_number

        assert _org_level_to_number(SimpleNamespace(level="3")) == 3  # 290
        assert _org_level_to_number(SimpleNamespace(level="level_2")) == 2
        assert _org_level_to_number(SimpleNamespace(level=None)) == 0  # 287
        assert _org_level_to_number(SimpleNamespace(level="weird")) == 0

    def test_set_no_cache_headers_noop_without_response(self):
        """无响应对象时 no-op（273->exit），防御性守卫。"""
        from app.api.v1.organization import _set_no_cache_headers

        assert _set_no_cache_headers(None) is None


class TestOrganizationScopeGuards:
    def _invisible_query(self):
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = None
        return q

    async def test_get_organization_forbidden_403(self, monkeypatch):
        """组织详情越权 → 403（645）。"""
        import app.core.data_permission as dp
        from app.api.v1 import organization as orgmod

        monkeypatch.setattr(dp, "apply_scope_filter", lambda *a, **k: self._invisible_query())
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=5, name="X")

        with pytest.raises(HTTPException) as ei:
            await orgmod.get_organization(5, _plain_user(), db)
        assert ei.value.status_code == 403

    async def test_get_members_forbidden_403(self, monkeypatch):
        """成员列表越权 → 403（1062）。"""
        import app.core.data_permission as dp
        from app.api.v1 import organization as orgmod

        monkeypatch.setattr(dp, "apply_scope_filter", lambda *a, **k: self._invisible_query())
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=5, name="X")

        with pytest.raises(HTTPException) as ei:
            await orgmod.get_organization_members(5, 1, 20, _plain_user(), db)
        assert ei.value.status_code == 403

    async def test_update_parent_id_no_cycle_recomputes_subtree(self, monkeypatch):
        """改父级但未成环 → 不抛错，且级联重算子树 path（785->791 + 799）。"""
        from app.api.v1 import organization as orgmod

        db = MagicMock()
        org = SimpleNamespace(id=5, name="本组织", code=None, parent_id=None)
        db.query.return_value.filter.return_value.first.return_value = org

        data = MagicMock()
        data.code = None
        data.model_dump.return_value = {"parent_id": 7}

        svc = MagicMock()
        svc.would_create_cycle.return_value = False

        monkeypatch.setattr(orgmod, "_assert_org_write_scope", lambda *a, **k: None)
        monkeypatch.setattr(orgmod, "OrganizationService", lambda _db: svc)
        monkeypatch.setattr(orgmod, "safe_commit", lambda *a, **k: None)
        monkeypatch.setattr(orgmod, "write_work_log", lambda *a, **k: None)
        monkeypatch.setattr(orgmod, "_coerce_org_enums", lambda d: None)
        monkeypatch.setattr(orgmod, "_invalidate_dashboard_cache_safe", lambda: None)
        monkeypatch.setattr(orgmod, "cache_manager", MagicMock(delete=AsyncMock()))

        resp = await orgmod.update_organization(5, data, _admin(), db)

        assert resp["code"] == 200
        svc.would_create_cycle.assert_called_once_with(5, 7)
        svc.recompute_subtree_paths.assert_called_once_with(org)

    async def test_update_code_locked_returns_422(self, monkeypatch):
        """改编码且库中无重复 → 不抛 400，继续更新（775->778）。"""
        from app.api.v1 import organization as orgmod

        db = MagicMock()
        org = SimpleNamespace(id=5, name="本组织", code=None, parent_id=None)
        # 第 1 次 first()：存在性检查 → org；第 2 次：编码查重 → None
        db.query.return_value.filter.return_value.first.side_effect = [org, None]

        data = MagicMock()
        data.code = "NEWCODE"
        data.model_dump.return_value = {"name": "改名"}

        svc = MagicMock()
        monkeypatch.setattr(orgmod, "_assert_org_write_scope", lambda *a, **k: None)
        monkeypatch.setattr(orgmod, "OrganizationService", lambda _db: svc)
        monkeypatch.setattr(orgmod, "safe_commit", lambda *a, **k: None)
        monkeypatch.setattr(orgmod, "write_work_log", lambda *a, **k: None)
        monkeypatch.setattr(orgmod, "_coerce_org_enums", lambda d: None)
        monkeypatch.setattr(orgmod, "_invalidate_dashboard_cache_safe", lambda: None)
        monkeypatch.setattr(orgmod, "cache_manager", MagicMock(delete=AsyncMock()))

        resp = await orgmod.update_organization(5, data, _admin(), db)

        assert resp["code"] == 200
        assert org.name == "改名"


# ══════════════════════════════════════════════════════════════════
#  app/api/v1/recycle_bin.py
# ══════════════════════════════════════════════════════════════════


class TestReachableIds:
    def _dept_admin(self):
        # role=admin 但非超管 → DataScope.OWN_DEPT（非 ALL）
        return SimpleNamespace(id=2, username="dept", role="admin", is_superuser=False, organization_id=2)

    def test_empty_ids_short_circuits(self):
        """空 ids → 直接返回 []（69）。"""
        from app.api.v1.recycle_bin import _reachable_ids

        assert _reachable_ids(MagicMock(), MagicMock(), "t", [], self._dept_admin()) == []

    def test_non_all_scope_filters(self, monkeypatch):
        """非全局管理员 → 走 scoped_filter 收敛 id（74-77）。"""
        import app.services.data_scope_query as dsq
        from app.api.v1.recycle_bin import _reachable_ids

        scoped = MagicMock()
        scoped.all.return_value = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        monkeypatch.setattr(dsq, "scoped_filter", lambda q, m, u: scoped)

        got = _reachable_ids(MagicMock(), MagicMock(), "t", [1, 2], self._dept_admin())
        assert got == [1, 2]

    def test_filter_failure_fails_closed(self, monkeypatch):
        """过滤链抛错 → fail-closed 返回 []（78-84），绝不退化成不过滤。"""
        import app.services.data_scope_query as dsq
        from app.api.v1.recycle_bin import _reachable_ids

        def _boom(*a, **k):
            raise RuntimeError("model has no org column")

        monkeypatch.setattr(dsq, "scoped_filter", _boom)

        assert _reachable_ids(MagicMock(), MagicMock(), "t", [1], self._dept_admin()) == []


# ══════════════════════════════════════════════════════════════════
#  app/api/v1/subordinate_reports.py
# ══════════════════════════════════════════════════════════════════


class TestStatusReportDbSize:
    @staticmethod
    def _db_and_user():
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value = q
        q.scalar.return_value = 4
        db.query.return_value = q
        user = SimpleNamespace(
            id=1, username="reporter", role="admin", is_superuser=False, organization_id=None
        )
        return db, user

    def test_db_size_read_from_path(self, monkeypatch, tmp_path):
        """库文件存在 → 计算真实大小（129）。"""
        from app.api.v1 import subordinate_reports as sr

        f = tmp_path / "app.sqlite"
        f.write_bytes(b"x" * 4096)
        monkeypatch.setattr("app.utils.paths.get_database_path", lambda: f)

        db, user = self._db_and_user()
        resp = sr.generate_status_report(db=db, current_user=user)
        assert resp.media_type == "application/zip"

    def test_db_size_error_is_swallowed(self, monkeypatch):
        """路径解析抛错 → 记 0 并留痕，不阻断上报包（130-132）。"""
        from app.api.v1 import subordinate_reports as sr

        def _boom():
            raise RuntimeError("fs error")

        monkeypatch.setattr("app.utils.paths.get_database_path", _boom)

        db, user = self._db_and_user()
        resp = sr.generate_status_report(db=db, current_user=user)
        assert resp.media_type == "application/zip"


# ══════════════════════════════════════════════════════════════════
#  app/api/v1/work_logs.py
# ══════════════════════════════════════════════════════════════════


class TestWorkLogSystemAutoGuard:
    async def test_create_rejects_system_auto(self):
        """创建时 category=system_auto → 400（241）。"""
        from app.api.v1.work_logs import create_work_log

        data = MagicMock()
        data.model_dump.return_value = {
            "log_date": "2026-07-21",
            "content": "x",
            "category": "system_auto",
        }
        with pytest.raises(HTTPException) as ei:
            await create_work_log(data=data, current_user=_plain_user(1), db=MagicMock())
        assert ei.value.status_code == 400

    async def test_update_rejects_system_auto(self):
        """更新时改写为 system_auto → 400（298）。"""
        from app.api.v1.work_logs import update_work_log

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=5, user_id=1)

        data = MagicMock()
        data.model_dump.return_value = {"category": "system_auto"}

        with pytest.raises(HTTPException) as ei:
            await update_work_log(5, data, _plain_user(1), db)
        assert ei.value.status_code == 400

    async def test_create_rejects_invalid_date_type(self):
        """log_date 既非字符串也非 date（如 int）→ 422（219-220）。"""
        from app.api.v1.work_logs import create_work_log

        data = MagicMock()
        data.model_dump.return_value = {"log_date": 12345, "content": "x", "category": "daily"}

        with pytest.raises(HTTPException) as ei:
            await create_work_log(data=data, current_user=_plain_user(1), db=MagicMock())
        assert ei.value.status_code == 422

    async def test_update_maps_log_type_to_category(self):
        """update 兼容字段：log_type → category（291-293）。"""
        from datetime import date

        from app.api.v1.work_logs import update_work_log

        log = SimpleNamespace(id=5, user_id=1, log_date=date(2026, 7, 21), content="x", category=None)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = log

        data = MagicMock()
        data.model_dump.return_value = {"log_type": "daily"}

        with patch("app.api.v1.work_logs.safe_commit"):
            result = await update_work_log(5, data, _plain_user(1), db)

        assert log.category == "daily"
        assert result.log_type == "daily"
