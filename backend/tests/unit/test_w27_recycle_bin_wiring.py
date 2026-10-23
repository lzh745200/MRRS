"""W27 P1 回归：4 个功能的回收站接入（政策 / 结对 / 消费 / 一户一档）。

## 缺陷
`register_recycle_bin_routes`（通用回收站）早已实现，但**全仓从未被调用** ——
只有帮扶村/学校/项目/经费有自己的回收站端点。以下 4 类记录的删除都是软删
（`is_active=False`），却没有恢复通道：误删只能直接改数据库。

## 修复
在 4 个模块末尾挂接通用回收站路由（`/{rid}/restore`、`/{rid}/purge[/preview]`、
`/batch-restore`、`/batch-purge`），均限管理员 + 彻底删除需二次确认密码 + 审计。

## 本文件锁定
1. 5 个路由在 4 个 router 上都确实注册（防"忘记调用"）；
2. `/{rid}/restore` 能真正把软删记录恢复（`is_active=True`、`deleted_at=None`）；
3. **不重复注册**：同一 router 上注册两次会产生同名路径，后者被永久遮蔽
   （pairing 的 VisitRecord 因此**有意未注册**，需独立前缀，见模块注释）。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client(router):
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _admin():
    return SimpleNamespace(
        id=1, username="admin", role="super_admin", is_superuser=True,
        hashed_password="h", org_id=1, organization_id=1,
    )


MODULES = [
    ("app.api.v1.policy", "/policies", "Policy"),
    ("app.api.v1.pairing", "/pairings", "PairingRecord"),
    ("app.api.v1.consumption", "/consumption", "ConsumptionRecord"),
    ("app.api.v1.households", "/households", "Household"),
]


class TestRoutesRegistered:
    @pytest.mark.parametrize("mod_path,prefix,_model", MODULES)
    def test_recycle_routes_present(self, mod_path, prefix, _model):
        import importlib

        mod = importlib.import_module(mod_path)
        paths = {r.path for r in mod.router.routes}
        assert f"{prefix}/{{rid}}/restore" in paths
        assert f"{prefix}/{{rid}}/purge" in paths
        assert f"{prefix}/{{rid}}/purge/preview" in paths
        assert f"{prefix}/batch-restore" in paths
        assert f"{prefix}/batch-purge" in paths

    @pytest.mark.parametrize("mod_path,prefix,_model", MODULES)
    def test_no_duplicate_restore_path(self, mod_path, prefix, _model):
        """同名路径只能出现一次 —— 否则后者被遮蔽（假注册）。"""
        import importlib

        mod = importlib.import_module(mod_path)
        paths = [r.path for r in mod.router.routes]
        target = f"{prefix}/{{rid}}/restore"
        assert paths.count(target) == 1, f"{prefix} 的 restore 路径重复注册，后者不可达"


class TestRestoreActuallyWorks:
    """恢复端点确实改回 is_active 并清 deleted_at（不是只注册了路径）。"""

    @pytest.mark.parametrize("mod_path,prefix,model_path", [
        ("app.api.v1.policy", "/policies", "app.models.policy.Policy"),
        ("app.api.v1.pairing", "/pairings", "app.models.pairing.PairingRecord"),
        ("app.api.v1.consumption", "/consumption", "app.models.consumption.ConsumptionRecord"),
        ("app.api.v1.households", "/households", "app.models.household.Household"),
    ])
    def test_restore_sets_active_and_clears_deleted_at(
        self, mod_path, prefix, model_path
    ):
        import importlib

        from app.api.v1 import deps
        from app.api.v1.deps import get_db

        mod = importlib.import_module(mod_path)
        app = FastAPI()
        app.include_router(mod.router)
        app.dependency_overrides[deps.get_current_user] = _admin

        rec = MagicMock()
        rec.id = 7
        rec.is_active = False
        rec.deleted_at = "2024-01-01"

        db = MagicMock()
        # 端点先用 db.query(...).first() 做存在性/回收站判定，再用 db.get() 取实体
        db.query.return_value.filter.return_value.first.return_value = rec
        db.get.return_value = rec
        app.dependency_overrides[get_db] = lambda: db

        with patch("app.api.v1.recycle_bin._require_reachable"), \
                patch("app.services.cascade_purge_service.CascadePurgeService"), \
                patch("app.core.transaction.safe_commit"), \
                patch("app.utils.audit_logger.AuditLogger.log"):
            resp = TestClient(app).post(f"{prefix}/7/restore")

        assert resp.status_code == 200, resp.text[:200]
        assert rec.is_active is True
        assert rec.deleted_at is None

    def test_restore_requires_admin(self):
        """非管理员不能恢复（与彻底删除同权限门槛）。"""
        from app.api.v1 import deps
        from app.api.v1.deps import get_db
        from app.api.v1 import households as mod

        app = FastAPI()
        app.include_router(mod.router)
        app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(
            id=2, username="user", role="user", is_superuser=False, org_id=1,
        )
        app.dependency_overrides[get_db] = lambda: MagicMock()

        resp = TestClient(app).post("/households/7/restore")
        assert resp.status_code in (403, 404)


class TestPairingVisitSeparatePrefix:
    """走访记录走**独立子路由前缀** `/pairings/visits`（W27）。

    教训：两张表若注册在同一 router 上，通用回收站的路径完全同名
    （`/{rid}/restore`、`/batch-restore`），后者会被先注册者永久遮蔽 ——
    表面"注册了"，实际调不到（正是 P0-6 那类"看着有、其实不成立"的形态）。
    """

    def test_visit_routes_use_separate_prefix(self):
        from app.api.v1 import pairing as mod

        paths = {r.path for r in mod.router.routes}
        # 结对记录
        assert "/pairings/{rid}/restore" in paths
        # 走访记录（独立前缀）
        assert "/pairings/visits/{rid}/restore" in paths
        assert "/pairings/visits/{rid}/purge" in paths
        assert "/pairings/visits/batch-restore" in paths

    def test_no_path_registered_twice(self):
        """同名路径只能出现一次，否则后者不可达。"""
        from app.api.v1 import pairing as mod

        paths = [r.path for r in mod.router.routes]
        for target in ("/pairings/{rid}/restore", "/pairings/visits/{rid}/restore"):
            assert paths.count(target) == 1, f"{target} 重复注册"

    def test_visit_restore_actually_works(self):
        """走访记录的恢复端点真能改回 is_active 并清 deleted_at。"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.v1 import deps
        from app.api.v1 import pairing as mod
        from app.api.v1.deps import get_db

        app = FastAPI()
        app.include_router(mod.router)
        app.dependency_overrides[deps.get_current_user] = _admin

        rec = MagicMock()
        rec.id = 9
        rec.is_active = False
        rec.deleted_at = "2024-01-01"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = rec
        db.get.return_value = rec
        app.dependency_overrides[get_db] = lambda: db

        with patch("app.api.v1.recycle_bin._require_reachable"), \
                patch("app.core.transaction.safe_commit"), \
                patch("app.utils.audit_logger.AuditLogger.log"):
            resp = TestClient(app).post("/pairings/visits/9/restore")

        assert resp.status_code == 200, resp.text[:200]
        assert rec.is_active is True
        assert rec.deleted_at is None
