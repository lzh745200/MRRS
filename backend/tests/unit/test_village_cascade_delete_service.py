"""村庄级联删除服务单元测试"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.village_cascade_delete_service import VillageCascadeDeleteService


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service(mock_db):
    return VillageCascadeDeleteService(db=mock_db)


class TestDeleteVillageCascade:
    def test_success_deletes_all_dependents_and_village(self, service, mock_db):
        mock_execute = mock_db.execute
        mock_execute.return_value.rowcount = 2
        mock_village_result = MagicMock()
        mock_village_result.rowcount = 1
        mock_db.execute.side_effect = [mock_execute.return_value] * len(service.DEPENDENT_TABLES) + [mock_village_result]
        result = service.delete_village_cascade(1)
        assert result["success"] is True
        assert result["village_id"] == 1
        assert result["deleted_records"] == len(service.DEPENDENT_TABLES) * 2 + 1
        mock_db.commit.assert_called_once()

    def test_individual_table_exception_logs_warning(self, service, mock_db):
        """schema 差异（表不存在）可容忍：跳过该表继续删除其余。

        深审 #72：原实现 `except Exception` 无差别吞掉所有 SQL 错误，
        这里改为只容忍 OperationalError 且特征为"表/列不存在"。
        """
        from sqlalchemy.exc import OperationalError

        normal_result = MagicMock()
        normal_result.rowcount = 1
        side_effects = []
        for i, _ in enumerate(service.DEPENDENT_TABLES):
            if i == 0:
                side_effects.append(
                    OperationalError("DELETE FROM x", {}, Exception("no such table: x"))
                )
            else:
                side_effects.append(normal_result)
        side_effects.append(MagicMock(rowcount=1))
        mock_db.execute.side_effect = side_effects
        with patch("app.services.village_cascade_delete_service.logger") as mock_logger:
            result = service.delete_village_cascade(1)
        assert result["success"] is True
        mock_logger.warning.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_non_schema_sql_error_is_fail_loud(self, service, mock_db):
        """非 schema 类 SQL 错误（如 database is locked）必须回滚并上抛。

        原实现在这里只 warning 后继续，主行删除成功但依赖行残留、计数漏报 ——
        调用方拿到 success=True 的假成功（深审 #72）。
        """
        from sqlalchemy.exc import OperationalError

        locked = OperationalError("DELETE FROM x", {}, Exception("database is locked"))
        mock_db.execute.side_effect = [locked] + [MagicMock(rowcount=1)] * (
            len(service.DEPENDENT_TABLES) + 1
        )
        with patch("app.services.village_cascade_delete_service.logger"):
            with pytest.raises(OperationalError):
                service.delete_village_cascade(1)
        mock_db.rollback.assert_called_once()
        mock_db.commit.assert_not_called()

    def test_arbitrary_exception_is_fail_loud(self, service, mock_db):
        """非 SQLAlchemy 异常同样不得被静默吞掉。"""
        mock_db.execute.side_effect = RuntimeError("unexpected")
        with patch("app.services.village_cascade_delete_service.logger"):
            with pytest.raises(RuntimeError):
                service.delete_village_cascade(1)
        mock_db.rollback.assert_called_once()
        mock_db.commit.assert_not_called()

    def test_village_not_found_returns_error(self, service, mock_db):
        mock_db.execute.return_value.rowcount = 0
        mock_village_result = MagicMock()
        mock_village_result.rowcount = 0
        normal_result = MagicMock()
        normal_result.rowcount = 0
        side_effects = [normal_result] * len(service.DEPENDENT_TABLES) + [mock_village_result]
        mock_db.execute.side_effect = side_effects
        result = service.delete_village_cascade(1)
        assert result["success"] is False
        assert result["message"] == "村庄不存在"
        assert result["deleted_records"] == 0
        mock_db.commit.assert_not_called()

    def test_exception_triggers_rollback_and_raises(self, service, mock_db):
        mock_db.execute.side_effect = RuntimeError("database locked")
        with pytest.raises(RuntimeError, match="database locked"):
            service.delete_village_cascade(1)
        mock_db.rollback.assert_called_once()
        mock_db.commit.assert_not_called()

    def test_delete_with_zero_dependent_rows(self, service, mock_db):
        normal_result = MagicMock()
        normal_result.rowcount = 0
        side_effects = [normal_result] * len(service.DEPENDENT_TABLES)
        side_effects.append(MagicMock(rowcount=1))
        mock_db.execute.side_effect = side_effects
        result = service.delete_village_cascade(1)
        assert result["success"] is True
        assert result["deleted_records"] == 1
        assert result["details"] == {}


class TestCheckVillageReferences:
    def test_has_references(self, service, mock_db):
        mock_scalar = MagicMock()
        mock_scalar.scalar.return_value = 3
        normal_result = MagicMock()
        normal_result.scalar.return_value = 0
        side_effects = [mock_scalar] + [normal_result] * (len(service.DEPENDENT_TABLES) - 1)
        mock_db.execute.side_effect = side_effects
        result = service.check_village_references(1)
        assert result["village_id"] == 1
        assert result["total_references"] == 3
        table_name = service.DEPENDENT_TABLES[0][0]
        assert result["details"][table_name] == 3

    def test_no_references(self, service, mock_db):
        normal_result = MagicMock()
        normal_result.scalar.return_value = 0
        mock_db.execute.return_value = normal_result
        result = service.check_village_references(1)
        assert result["total_references"] == 0
        assert result["details"] == {}

    def test_exception_during_query_ignored(self, service, mock_db):
        normal_result = MagicMock()
        normal_result.scalar.return_value = 0
        side_effects = [Exception("table not found")] + [normal_result] * (len(service.DEPENDENT_TABLES) - 1)
        mock_db.execute.side_effect = side_effects
        result = service.check_village_references(1)
        assert result["total_references"] == 0
