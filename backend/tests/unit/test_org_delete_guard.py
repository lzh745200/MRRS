"""组织删除级联守卫（W2-T2 / ADR-0003）验收测试

- 服务层硬删除：名下有项目/用户 → OrganizationInUseError（含计数清单）
- DB 层：projects.organization_id 外键 CASCADE→SET NULL，硬删组织不再连带删项目
- 元数据守卫：模型外键 ondelete 与迁移清单一致（防漂移）
"""
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def mem_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def _seed_org(db, name="被删组织", code="DEL01", parent_id=None):
    from app.models.organization import Organization

    org = Organization(name=name, code=code, is_active=True, parent_id=parent_id)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def test_guard_raises_with_counts(mem_db):
    from app.services.organization_service import OrganizationInUseError, OrganizationService

    org = _seed_org(mem_db)
    from app.models.project import Project
    from app.models.user import User

    mem_db.add(Project(name="名下项目", organization_id=org.id, is_active=True))
    mem_db.add(User(username="u1", hashed_password="x", organization_id=org.id, is_active=True))
    mem_db.add(Project(name="已删项目", organization_id=org.id, is_active=False))  # 软删项目不计数
    mem_db.commit()

    svc = OrganizationService(db=mem_db)
    with pytest.raises(OrganizationInUseError) as ei:
        asyncio.run(svc.delete_organization(org.id))
    assert ei.value.project_count == 1
    assert ei.value.user_count == 1
    assert "1 个项目" in str(ei.value) and "1 个用户" in str(ei.value)


def test_guard_allows_empty_org(mem_db):
    """无项目/用户的空组织可硬删除（子组织守卫仍在前）"""
    from app.services.organization_service import OrganizationService

    org = _seed_org(mem_db, code="EMPTY01")
    svc = OrganizationService(db=mem_db)
    import asyncio

    ok = asyncio.run(svc.delete_organization(org.id))
    assert ok is True


def test_db_level_set_null_survives_hard_delete(mem_db):
    """绕过应用层直接硬删组织行：项目存活、organization_id 置 NULL（SET NULL 生效）"""
    from sqlalchemy import text

    from app.models.project import Project

    org = _seed_org(mem_db, code="RAWDEL01")
    mem_db.add(Project(name="存活项目", organization_id=org.id, is_active=True))
    mem_db.commit()
    project_id = mem_db.query(Project).filter(Project.name == "存活项目").one().id

    mem_db.execute(text("PRAGMA foreign_keys=ON"))
    mem_db.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": org.id})
    mem_db.commit()

    row = mem_db.execute(
        text("SELECT organization_id FROM projects WHERE id = :i"), {"i": project_id}
    ).fetchone()
    assert row is not None, "项目被级联删除 —— SET NULL 未生效"
    assert row[0] is None


def test_model_fk_metadata_is_set_null():
    """元数据守卫：Project.organization_id 的 ondelete 必须是 SET NULL（防漂移）"""
    from app.models.project import Project

    fk = next(
        f for f in Project.__table__.foreign_keys if f.column.table.name == "organizations"
    )
    assert fk.ondelete == "SET NULL"
