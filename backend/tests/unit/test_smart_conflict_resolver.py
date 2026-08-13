import pytest
from unittest.mock import MagicMock, patch

from app.services.smart_conflict_resolver import (
    SmartConflictResolver,
    ConflictStrategy,
    DataConflict,
    ConflictDetectionResult,
    BUSINESS_KEY_FIELDS,
)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def resolver(mock_db):
    return SmartConflictResolver(db=mock_db)


class MockModelBase:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockVillage(MockModelBase):
    id = 1
    code = "V001"
    village_name = "V001"
    name = "Test Village"
    province = "Guizhou"
    county = "County X"
    created_at = None
    updated_at = None
    created_by = None
    updated_by = None


class MockProject(MockModelBase):
    id = 2
    code = "P001"
    name = "Test Project"
    status = "active"
    created_at = None
    updated_at = None
    created_by = None
    updated_by = None


class MockFund(MockModelBase):
    id = 3
    code = "F001"
    amount = 100000
    created_at = None
    updated_at = None
    created_by = None
    updated_by = None


class MockSchool(MockModelBase):
    id = 4
    code = "S001"
    name = "Test School"
    created_at = None
    updated_at = None
    created_by = None
    updated_by = None


class MockRecordWithUpdatedAt(MockModelBase):
    id = 5
    code = "R001"
    name = "Old Name"
    updated_at = "2025-01-01"
    value = None
    created_at = None
    created_by = None
    updated_by = None


MODEL_MAP = {
    "villages": MockVillage,
    "projects": MockProject,
    "funds": MockFund,
    "schools": MockSchool,
}


class TestConflictStrategy:
    def test_constants(self):
        assert ConflictStrategy.SKIP == "SKIP"
        assert ConflictStrategy.OVERWRITE == "OVERWRITE"
        assert ConflictStrategy.KEEP_BOTH == "KEEP_BOTH"
        assert ConflictStrategy.MERGE == "MERGE"


class TestDataConflict:
    def test_init(self):
        conflict = DataConflict(
            data_type="villages",
            business_key={"code": "V001"},
            local_record="local",
            import_record={"code": "V001", "name": "New"},
            differences=["name"],
        )
        assert conflict.data_type == "villages"
        assert conflict.business_key == {"code": "V001"}
        assert conflict.local_record == "local"
        assert conflict.import_record == {"code": "V001", "name": "New"}
        assert conflict.differences == ["name"]


class TestConflictDetectionResult:
    def test_init(self):
        result = ConflictDetectionResult(
            new_records=[{"a": 1}],
            conflict_records=["c1"],
            no_conflict_records=[{"b": 2}],
        )
        assert result.new_records == [{"a": 1}]
        assert result.conflict_records == ["c1"]
        assert result.no_conflict_records == [{"b": 2}]


@patch("app.services.smart_conflict_resolver.DATA_TYPE_MODELS", MODEL_MAP)
class TestSmartConflictResolver:
    def test_constructor(self, resolver, mock_db):
        assert resolver.db is mock_db

    def test_detect_conflicts_by_business_key_invalid_data_type(self, resolver):
        with pytest.raises(ValueError, match="不支持的数据类型"):
            resolver.detect_conflicts_by_business_key([], "invalid_type")

    def test_detect_conflicts_by_business_key_no_business_key(self, resolver, mock_db):
        with patch.dict(BUSINESS_KEY_FIELDS, {"test_type": []}):
            with patch.dict(MODEL_MAP, {"test_type": MockVillage}):
                with pytest.raises(ValueError, match="未定义业务键"):
                    resolver.detect_conflicts_by_business_key([], "test_type")

    def test_detect_conflicts_by_business_key_new_records(self, resolver, mock_db):
        records = [{"village_name": "New Village"}]
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = resolver.detect_conflicts_by_business_key(records, "villages")
        assert len(result.new_records) == 1
        assert result.new_records[0] == records[0]
        assert len(result.conflict_records) == 0
        assert len(result.no_conflict_records) == 0

    def test_detect_conflicts_by_business_key_no_valid_key(self, resolver, mock_db):
        records = [{"name": "No Code"}]
        result = resolver.detect_conflicts_by_business_key(records, "villages")
        assert len(result.new_records) == 1
        assert result.new_records[0] == records[0]

    def test_detect_conflicts_by_business_key_conflict(self, resolver, mock_db):
        local = MockVillage()
        records = [{"village_name": "Different Name"}]
        mock_db.query.return_value.filter.return_value.first.return_value = local
        result = resolver.detect_conflicts_by_business_key(records, "villages")
        assert len(result.new_records) == 0
        assert len(result.conflict_records) == 1
        assert len(result.no_conflict_records) == 0
        assert result.conflict_records[0].differences == ["village_name"]

    def test_detect_conflicts_by_business_key_no_conflict(self, resolver, mock_db):
        local = MockVillage()
        local.village_name = "Same Name"
        records = [{"village_name": "Same Name"}]
        mock_db.query.return_value.filter.return_value.first.return_value = local
        result = resolver.detect_conflicts_by_business_key(records, "villages")
        assert len(result.new_records) == 0
        assert len(result.conflict_records) == 0
        assert len(result.no_conflict_records) == 1

    def test_detect_conflicts_by_business_key_projects(self, resolver, mock_db):
        records = [{"code": "P001", "name": "New Project"}]
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = resolver.detect_conflicts_by_business_key(records, "projects")
        assert len(result.new_records) == 1

    def test_detect_conflicts_by_business_key_funds(self, resolver, mock_db):
        records = [{"code": "F001", "amount": 50000}]
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = resolver.detect_conflicts_by_business_key(records, "funds")
        assert len(result.new_records) == 1

    def test_detect_conflicts_by_business_key_schools(self, resolver, mock_db):
        records = [{"code": "S001", "name": "New School"}]
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = resolver.detect_conflicts_by_business_key(records, "schools")
        assert len(result.new_records) == 1

    def test_find_differences_skips_ignore_fields(self, resolver):
        local = MockVillage()
        import_record = {
            "id": 999,
            "created_at": "2025-01-01",
            "updated_at": "2025-01-02",
            "created_by": 1,
            "updated_by": 2,
            "code": "V001",
            "name": "Test Village",
        }
        diffs = resolver._find_differences(local, import_record)
        assert "id" not in diffs
        assert "created_at" not in diffs
        assert "updated_at" not in diffs
        assert "created_by" not in diffs
        assert "updated_by" not in diffs

    def test_find_differences_both_none(self, resolver):
        local = MockVillage()
        local.some_field = None
        diffs = resolver._find_differences(local, {"code": "V001", "some_field": None})
        assert "some_field" not in diffs

    def test_find_differences_equal(self, resolver):
        local = MockVillage()
        local.name = "Same"
        diffs = resolver._find_differences(local, {"code": "V001", "name": "Same"})
        assert "name" not in diffs

    def test_find_differences_different(self, resolver):
        local = MockVillage()
        diffs = resolver._find_differences(local, {"code": "V001", "name": "Different"})
        assert "name" in diffs

    def test_find_differences_no_attribute(self, resolver):
        local = MockVillage()
        diffs = resolver._find_differences(local, {"code": "V001", "nonexistent": "val"})
        assert "nonexistent" not in diffs

    def test_find_differences_str_conversion(self, resolver):
        local = MockVillage()
        local.numeric = 100
        diffs = resolver._find_differences(local, {"code": "V001", "numeric": "100"})
        assert "numeric" not in diffs

    def test_find_differences_type_coercion(self, resolver):
        local = MockVillage()
        local.int_val = 42
        diffs = resolver._find_differences(local, {"code": "V001", "int_val": "42"})
        assert "int_val" not in diffs

    def test_find_differences_true_vs_string(self, resolver):
        local = MockVillage()
        local.flag = True
        diffs = resolver._find_differences(local, {"code": "V001", "flag": "True"})
        assert "flag" not in diffs

    def test_resolve_conflicts_skip(self, resolver, mock_db):
        local = MockVillage()
        conflict = DataConflict("villages", {"code": "V001"}, local, {"id": 10, "code": "V001"}, [])
        result = resolver.resolve_conflicts_with_strategy([conflict], ConflictStrategy.SKIP)
        assert result == {"villages": {10: 1}}

    def test_resolve_conflicts_overwrite(self, resolver, mock_db):
        local = MockVillage()
        conflict = DataConflict(
            "villages", {"code": "V001"}, local,
            {"id": 10, "code": "V001", "name": "Overwritten Name", "created_at": "x", "created_by": 99},
            ["name"]
        )
        result = resolver.resolve_conflicts_with_strategy([conflict], ConflictStrategy.OVERWRITE)
        assert result == {"villages": {10: 1}}
        assert local.name == "Overwritten Name"
        mock_db.flush.assert_called_once()

    def test_resolve_conflicts_keep_both(self, resolver, mock_db):
        local = MockVillage()
        conflict = DataConflict(
            "villages", {"village_name": "V001"}, local,
            {"id": 10, "village_name": "V001", "name": "New Copy"},
            ["name"]
        )
        with patch("app.services.smart_conflict_resolver.time.time", return_value=1234567890):
            result = resolver.resolve_conflicts_with_strategy([conflict], ConflictStrategy.KEEP_BOTH)
        assert result == {"villages": {10: 1}}
        mock_db.add.assert_called_once()
        added = mock_db.add.call_args[0][0]
        assert isinstance(added, MockVillage)
        assert added.village_name == "V001_imp_1234567890"
        assert added.name == "New Copy"

    def test_resolve_conflicts_keep_both_no_code_field(self, resolver, mock_db):
        local = MockVillage()
        conflict = DataConflict(
            "villages", {"code": None}, local,
            {"id": 10, "name": "No Code Copy"},
            ["name"]
        )
        with patch("app.services.smart_conflict_resolver.time.time", return_value=1234567890):
            result = resolver.resolve_conflicts_with_strategy([conflict], ConflictStrategy.KEEP_BOTH)
        assert result == {"villages": {10: 1}}
        mock_db.add.assert_called_once()
        added = mock_db.add.call_args[0][0]
        assert isinstance(added, MockVillage)
        assert added.name == "No Code Copy"

    def test_resolve_conflicts_merge_local_none(self, resolver, mock_db):
        local = MockRecordWithUpdatedAt()
        conflict = DataConflict(
            "villages", {"code": "R001"}, local,
            {"id": 10, "code": "R001", "name": "Updated Name", "value": "New Value", "updated_at": "2025-06-01"},
            ["name"]
        )
        result = resolver.resolve_conflicts_with_strategy([conflict], ConflictStrategy.MERGE)
        assert result == {"villages": {10: 5}}
        assert local.value == "New Value"
        mock_db.flush.assert_called_once()

    def test_resolve_conflicts_merge_import_older(self, resolver, mock_db):
        local = MockRecordWithUpdatedAt()
        local.name = "Existing Name"
        conflict = DataConflict(
            "villages", {"code": "R001"}, local,
            {"id": 10, "code": "R001", "name": "Older Name", "updated_at": "2024-01-01"},
            ["name"]
        )
        result = resolver.resolve_conflicts_with_strategy([conflict], ConflictStrategy.MERGE)
        assert local.name == "Existing Name"
        mock_db.flush.assert_called_once()

    def test_resolve_conflicts_merge_import_newer(self, resolver, mock_db):
        local = MockRecordWithUpdatedAt()
        local.name = "Existing Name"
        conflict = DataConflict(
            "villages", {"code": "R001"}, local,
            {"id": 10, "code": "R001", "name": "Newer Name", "updated_at": "2025-06-01"},
            ["name"]
        )
        result = resolver.resolve_conflicts_with_strategy([conflict], ConflictStrategy.MERGE)
        assert local.name == "Newer Name"
        mock_db.flush.assert_called_once()

    def test_resolve_conflicts_merge_import_value_none(self, resolver, mock_db):
        local = MockRecordWithUpdatedAt()
        local.name = "Existing Name"
        conflict = DataConflict(
            "villages", {"code": "R001"}, local,
            {"id": 10, "code": "R001", "name": None, "updated_at": "2025-06-01"},
            ["name"]
        )
        result = resolver.resolve_conflicts_with_strategy([conflict], ConflictStrategy.MERGE)
        assert local.name == "Existing Name"
        mock_db.flush.assert_called_once()

    def test_resolve_conflicts_merge_no_updated_at_local(self, resolver, mock_db):
        local = MockVillage()
        local.name = None
        conflict = DataConflict(
            "villages", {"code": "V001"}, local,
            {"id": 10, "code": "V001", "name": "New Name", "updated_at": "2025-06-01"},
            ["name"]
        )
        result = resolver.resolve_conflicts_with_strategy([conflict], ConflictStrategy.MERGE)
        assert local.name == "New Name"
        mock_db.flush.assert_called_once()

    def test_get_code_field(self, resolver):
        assert resolver._get_code_field("villages") == "village_name"
        assert resolver._get_code_field("projects") == "code"
        assert resolver._get_code_field("funds") == "code"
        assert resolver._get_code_field("schools") == "code"
        assert resolver._get_code_field("unknown") is None

    def test_import_new_records_with_fk_update(self, resolver, mock_db):
        records = [{"id": 10, "code": "P001", "name": "Project", "village_id": 5}]
        id_mapping = {"villages": {5: 99}}
        result = resolver._import_new_records(records, "projects", id_mapping)
        assert 10 in result["projects"]
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_import_new_records_no_fk(self, resolver, mock_db):
        records = [{"id": 20, "code": "V002", "name": "Village"}]
        result = resolver._import_new_records(records, "villages", {})
        assert 20 in result["villages"]
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_update_foreign_keys_missing_type(self, resolver):
        data = {"village_id": 5}
        resolver._update_foreign_keys(data, "schools", {"villages": {5: 99}})
        assert data["village_id"] == 5

    def test_update_foreign_keys_missing_fk(self, resolver):
        data = {"some_field": "value"}
        resolver._update_foreign_keys(data, "projects", {"villages": {5: 99}})
        assert data["some_field"] == "value"

    def test_update_foreign_keys_empty_fk(self, resolver):
        data = {"village_id": None}
        resolver._update_foreign_keys(data, "projects", {"villages": {5: 99}})
        assert data["village_id"] is None

    def test_update_foreign_keys_ref_not_in_mapping(self, resolver):
        data = {"village_id": 5}
        resolver._update_foreign_keys(data, "projects", {})
        assert data["village_id"] == 5

    def test_update_foreign_keys_ref_old_id_not_in_mapping(self, resolver):
        data = {"village_id": 5}
        resolver._update_foreign_keys(data, "projects", {"villages": {99: 100}})
        assert data["village_id"] == 5

    def test_update_foreign_keys_projects_village(self, resolver):
        data = {"village_id": 5}
        resolver._update_foreign_keys(data, "projects", {"villages": {5: 99}})
        assert data["village_id"] == 99

    def test_update_foreign_keys_funds_project(self, resolver):
        data = {"project_id": 7}
        resolver._update_foreign_keys(data, "funds", {"projects": {7: 77}})
        assert data["project_id"] == 77

    def test_import_with_id_mapping_missing_data_type(self, resolver, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = resolver.import_with_id_mapping({"villages": [{"code": "V001", "name": "V"}]})
        assert "villages" in result

    def test_import_with_id_mapping_empty_records(self, resolver):
        result = resolver.import_with_id_mapping({"villages": []})
        assert result == {}

    def test_import_with_id_mapping_unknown_type_skipped(self, resolver):
        result = resolver.import_with_id_mapping({"unknown": [{"code": "X"}]})
        assert result == {}

    def test_import_with_id_mapping_datetime_conversion(self, resolver, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        records = [{
            "code": "V001",
            "name": "Village",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-06-01T12:00:00+00:00",
        }]
        result = resolver.import_with_id_mapping({"villages": records})
        assert "villages" in result

    def test_import_with_id_mapping_bad_datetime(self, resolver, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        records = [{
            "code": "V001",
            "name": "Village",
            "created_at": "not-a-datetime",
            "updated_at": 12345,
        }]
        result = resolver.import_with_id_mapping({"villages": records})
        assert "villages" in result

    def test_import_with_id_mapping_all_types(self, resolver, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        data = {
            "villages": [{"code": "V001", "name": "V"}],
            "schools": [{"code": "S001", "name": "S"}],
            "projects": [{"code": "P001", "name": "P"}],
            "funds": [{"code": "F001", "amount": 100}],
        }
        result = resolver.import_with_id_mapping(data)
        for dtype in ["villages", "schools", "projects", "funds"]:
            assert dtype in result

    def test_import_with_id_mapping_conflict_and_new(self, resolver, mock_db):
        local = MockVillage()
        mock_db.query.return_value.filter.return_value.first.side_effect = [local, None]
        data = {
            "villages": [
                {"village_name": "V001", "name": "Changed Name"},
                {"village_name": "V002", "name": "Brand New"},
            ]
        }
        result = resolver.import_with_id_mapping(data)
        assert "villages" in result

    def test_detect_conflicts_mixed_types(self, resolver, mock_db):
        local = MockVillage()
        mock_db.query.return_value.filter.return_value.first.side_effect = [local, None, None]
        records = [
            {"village_name": "V001", "name": "Changed"},
            {"village_name": "V002", "name": "New"},
            {"village_name": "V003", "name": "Another"},
        ]
        result = resolver.detect_conflicts_by_business_key(records, "villages")
        assert len(result.conflict_records) == 1
        assert len(result.new_records) == 2

    def test_import_with_id_mapping_strategy_skip(self, resolver, mock_db):
        local = MockVillage()
        mock_db.query.return_value.filter.return_value.first.return_value = local
        data = {"villages": [{"code": "V001", "name": "Skip Me"}]}
        result = resolver.import_with_id_mapping(data, strategy=ConflictStrategy.SKIP)
        assert "villages" in result
