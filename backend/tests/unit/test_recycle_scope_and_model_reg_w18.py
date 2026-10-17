"""W18-D6 回归：回收站**单条** restore/purge 必须限定数据域（跨组织越权）。

背景（.scratch/w18-deep-probe/01-data-integrity.md D6）
  R28-M3 只给**批量**端点接入了 `_reachable_ids`；单条 `/{rid}/restore` 与
  `/{rid}/purge` 仍只做"存在 + 在回收站"校验 —— 部门级管理员可直接物理删除
  （不可逆）其它组织的回收站记录。

本文件用真实 SQLite 驱动数据域判定，验证：
  * 本组织记录 → 放行；
  * 他组织记录（部门级 admin）→ 404；
  * 全局管理员 → 任何组织都放行。
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _admin(org_id, superuser=False):
    from types import SimpleNamespace

    return SimpleNamespace(
        id=99, username="admin", role="admin", is_superuser=superuser,
        organization_id=org_id, data_scope="org", is_active=True,
    )


def _village(db, org_id, active=False):
    from app.models.supported_village import SupportedVillage

    v = SupportedVillage(
        village_name=f"村{org_id}-{active}", organization_id=org_id, is_active=active,
        created_by=1,
    )
    db.add(v)
    db.commit()
    return v


class TestSingleRecordReachability:
    def test_own_org_record_is_reachable(self, db):
        from app.api.v1.recycle_bin import _require_reachable
        from app.models.supported_village import SupportedVillage

        v = _village(db, org_id=5)
        # 不应抛错
        _require_reachable(db, SupportedVillage, "supported_villages", v.id, _admin(5))

    def test_other_org_record_is_rejected(self, db):
        """"核心：部门级 admin 不得触碰他组织回收站记录（原缺陷可物理删除）。"""
        from app.api.v1.recycle_bin import _require_reachable
        from app.models.supported_village import SupportedVillage

        v = _village(db, org_id=9)
        with pytest.raises(HTTPException) as ei:
            _require_reachable(db, SupportedVillage, "supported_villages", v.id, _admin(5))
        assert ei.value.status_code == 404

    def test_super_admin_can_reach_any_org(self, db):
        from app.api.v1.recycle_bin import _require_reachable
        from app.models.supported_village import SupportedVillage

        v = _village(db, org_id=9)
        _require_reachable(
            db, SupportedVillage, "supported_villages", v.id, _admin(None, superuser=True)
        )

    def test_nonexistent_id_is_rejected(self, db):
        from app.api.v1.recycle_bin import _require_reachable
        from app.models.supported_village import SupportedVillage

        with pytest.raises(HTTPException) as ei:
            _require_reachable(db, SupportedVillage, "supported_villages", 999999, _admin(5))
        assert ei.value.status_code == 404


class TestModelRegistration:
    """W18-P3-1：模型必须全部登记进 _MODULE_MAP，否则全新安装不建表。"""

    def test_sentiment_news_is_registered(self):
        import app.models as models

        assert "SentimentNews" in models._MODULE_MAP
        assert models.SentimentNews.__tablename__ == "sentiment_news"

    def test_machine_code_permission_is_registered(self):
        import app.models as models

        assert "MachineCodePermission" in models._MODULE_MAP
        assert models.MachineCodePermission.__tablename__ == "machine_code_permissions"

    def test_all_declared_tables_are_registered(self):
        """全量守卫：models/ 下所有真实模型类都必须出现在 _MODULE_MAP。"""
        import ast
        import io
        import os

        import app.models as models

        models_dir = os.path.dirname(models.__file__)
        missing = []
        for fname in os.listdir(models_dir):
            if not fname.endswith(".py") or fname == "__init__.py":
                continue
            path = os.path.join(models_dir, fname)
            try:
                tree = ast.parse(io.open(path, encoding="utf-8").read())
            except Exception:
                continue
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                bases = [getattr(b, "id", None) or getattr(b, "attr", None) or "" for b in node.bases]
                if not any(x in ("Base", "BaseModel") for x in bases):
                    continue
                if node.name not in models._MODULE_MAP:
                    missing.append(f"{fname}::{node.name}")
        assert missing == [], f"未登记进 _MODULE_MAP 的模型（新装会缺表）: {missing}"
