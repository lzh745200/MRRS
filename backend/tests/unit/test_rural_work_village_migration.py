"""W22 乡村工作/任务：村关联从遗留 villages 迁移到 supported_villages。

锁定口径（契约 §1.6）：
- 模型只保留 ``supported_village_id``（FK supported_villages SET NULL），不再有 ``village_id``；
- 关系对象为 SupportedVillage（遗留 Village 模型/表已删除）；
- 服务层按新列筛选、校验帮扶村存在；面板下拉直接用帮扶村 id；
- 端点响应同时输出 ``supported_village_id``/``village_id`` 与派生 ``village_name``。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def test_rural_models_only_expose_supported_village_id():
    from app.models.rural_task import RuralTask
    from app.models.rural_work import RuralWork
    from app.models.supported_village import SupportedVillage

    for model in (RuralWork, RuralTask):
        columns = model.__table__.c
        assert "supported_village_id" in columns
        assert "village_id" not in columns
        fk = next(iter(columns["supported_village_id"].foreign_keys))
        assert fk.target_fullname == "supported_villages.id"
        assert fk.ondelete == "SET NULL"
        assert columns["supported_village_id"].nullable is True
        # relationship 指向帮扶村
        assert model.supported_village.property.mapper.class_ is SupportedVillage


def test_legacy_village_models_are_deleted():
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.models.village")

    from app.models import Base

    for table in ("villages", "villagers", "industries", "sentiment_news"):
        assert table not in Base.metadata.tables


def test_services_and_router_have_no_legacy_imports():
    """关键消费方（服务/端点）不再 import 遗留 Village 模型。"""
    import inspect

    import app.api.v1.report_templates as report_templates
    import app.services.rural_work_service as rural_work_service

    assert "app.models.village" not in inspect.getsource(report_templates)
    assert "app.models.village" not in inspect.getsource(rural_work_service)


@pytest.fixture
def db():
    from app.models import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _mk_village(db, name="幸福村"):
    from app.models.supported_village import SupportedVillage

    village = SupportedVillage(village_name=name, organization_id=1, is_active=True)
    db.add(village)
    db.commit()
    db.refresh(village)
    return village


class TestRuralWorkServiceVillageMigration:
    def test_filter_uses_supported_village_id(self, db):
        from app.models.rural_work import RuralWork
        from app.services.rural_work_service import RuralWorkService

        village = _mk_village(db)
        matched = RuralWork(name="关联村工作", supported_village_id=village.id)
        other = RuralWork(name="无村工作")
        db.add_all([matched, other])
        db.commit()

        service = RuralWorkService(db)
        items, total = service.get_rural_works(village_id=village.id)
        assert total == 1
        assert items[0]["name"] == "关联村工作"
        assert items[0]["supported_village_id"] == village.id
        assert items[0]["village_id"] == village.id        # 旧前端字段兼容
        assert items[0]["village_name"] == "幸福村"

    def test_validate_village_id_against_supported_villages(self, db):
        from app.services.rural_work_service import RuralWorkService

        village = _mk_village(db)
        service = RuralWorkService(db)
        assert service._validate_village_id(None) is None
        assert service._validate_village_id(village.id) is None
        with pytest.raises(ValueError, match="所选帮扶村不存在"):
            service._validate_village_id(999999)

    def test_create_accepts_legacy_village_id_field(self, db):
        """schema 仍用旧字段名 village_id，服务层归一写入 supported_village_id。"""
        from app.models.rural_work import RuralWork
        from app.services.rural_work_service import RuralWorkService

        village = _mk_village(db)
        service = RuralWorkService(db)
        result = service.create_rural_work({"name": "新工作", "village_id": village.id})
        assert result["supported_village_id"] == village.id
        row = db.query(RuralWork).filter(RuralWork.name == "新工作").one()
        assert row.supported_village_id == village.id

    def test_get_villages_for_select_returns_supported_village_ids(self, db):
        from app.services.rural_work_service import RuralWorkService

        village = _mk_village(db)
        rows = RuralWorkService(db).get_villages_for_select()
        assert rows == [{"id": village.id, "name": "幸福村", "county": None}]


class TestRuralTasksEndpointResponseFields:
    def test_task_response_has_new_and_legacy_fields(self):
        from types import SimpleNamespace

        from app.api.v1.rural_tasks import _task_to_response

        class Task:
            supported_village_id = 9
            supported_village = SimpleNamespace(village_name="幸福村")
            rural_work = SimpleNamespace(name="产业帮扶")

            def to_dict(self):
                return {"id": 1, "title": "任务"}

        payload = _task_to_response(Task())
        assert payload["supported_village_id"] == 9
        assert payload["village_id"] == 9
        assert payload["village_name"] == "幸福村"
        assert payload["rural_work_name"] == "产业帮扶"

    def test_task_response_without_relations(self):
        from app.api.v1.rural_tasks import _task_to_response

        class Task:
            supported_village_id = None
            supported_village = None
            rural_work = None

            def to_dict(self):
                return {"id": 2}

        payload = _task_to_response(Task())
        assert payload["village_name"] is None
        assert payload["rural_work_name"] is None
