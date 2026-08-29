"""Tests for app/services/audit_event_handler.py — 目标 100% 覆盖。"""
from unittest.mock import ANY, MagicMock, PropertyMock, patch

import pytest
from sqlalchemy import event

from app.models.supported_village import SupportedVillage
from app.models.user import User


# ---------------------------------------------------------------------------
# _resolve_actor_id
# ---------------------------------------------------------------------------

class TestResolveActorId:
    def test_with_user_context(self):
        from app.services.audit_event_handler import _resolve_actor_id
        with patch("app.middleware.audit_context.get_current_user", return_value=42):
            uid, is_system = _resolve_actor_id()
            assert uid == 42
            assert is_system is False

    def test_system_when_context_is_none(self):
        from app.services.audit_event_handler import _resolve_actor_id
        with patch("app.middleware.audit_context.get_current_user", return_value=None):
            uid, is_system = _resolve_actor_id()
            assert uid is None
            assert is_system is True

    def test_system_when_import_fails(self):
        from app.services.audit_event_handler import _resolve_actor_id
        with patch("app.middleware.audit_context.get_current_user", side_effect=Exception("import fail")):
            uid, is_system = _resolve_actor_id()
            assert uid is None
            assert is_system is True


# ---------------------------------------------------------------------------
# _get_entity_name
# ---------------------------------------------------------------------------

class TestGetEntityName:
    def test_name_attr(self):
        from app.services.audit_event_handler import _get_entity_name
        inst = MagicMock()
        inst.name = "红星村"
        inst.id = 5
        result = _get_entity_name(inst)
        assert result == "红星村"

    def test_title_attr(self):
        from app.services.audit_event_handler import _get_entity_name
        inst = MagicMock()
        inst.configure_mock(name=None, title="标题名称", id=3)
        result = _get_entity_name(inst)
        assert result == "标题名称"

    def test_fallback_to_class_name(self):
        from app.services.audit_event_handler import _get_entity_name
        inst = MagicMock()
        inst.configure_mock(name=None, title=None)
        result = _get_entity_name(inst)
        assert isinstance(result, str)
        assert "MagicMock" in result
        assert "#" in result

    def test_non_string_attr_skipped(self):
        from app.services.audit_event_handler import _get_entity_name
        inst = MagicMock()
        inst.configure_mock(name=12345, title=None, village_name=12345, username="实际用户名")
        result = _get_entity_name(inst)
        assert result == "实际用户名"


# ---------------------------------------------------------------------------
# _get_entity_type
# ---------------------------------------------------------------------------

class TestGetEntityType:
    def test_known_mapping(self):
        from app.services.audit_event_handler import _get_entity_type
        inst = SupportedVillage()
        assert _get_entity_type(inst) == "village"

    def test_fallback_to_lowercase(self):
        from app.services.audit_event_handler import _get_entity_type

        class CustomModel:
            pass

        inst = CustomModel()
        result = _get_entity_type(inst)
        assert result == "custommodel"

    @pytest.mark.parametrize("cls_name,expected", [
        ("FundBudget", "fund_budget"),
        ("FundTransferVoucher", "voucher"),
        ("FundAllocationOrder", "allocation"),
        ("FundContract", "contract"),
        ("FundAnomaly", "anomaly"),
        ("ScholarshipStudent", "scholarship"),
        ("SchoolProject", "school_project"),
        ("ApprovalTask", "approval"),
        ("ApprovalWorkflow", "approval_workflow"),
        ("RbacRole", "role"),
        ("UserPermission", "permission"),
        ("UserRole", "user_role"),
        ("Organization", "org"),
    ])
    def test_all_mappings(self, cls_name, expected):
        from app.services.audit_event_handler import _get_entity_type
        inst = type(cls_name, (), {})()
        assert _get_entity_type(inst) == expected


# ---------------------------------------------------------------------------
# _write_audit_from_event
# ---------------------------------------------------------------------------

class TestWriteAuditFromEvent:
    def test_system_operation_logs_only(self, svc_audit_module):
        from app.services.audit_event_handler import _write_audit_from_event
        mapper = MagicMock()
        connection = MagicMock()
        target = MagicMock(spec=SupportedVillage, name="红星村", id=5)
        with patch("app.services.audit_event_handler._resolve_actor_id", return_value=(None, True)):
            with patch("app.services.audit_event_handler.logger.info") as mock_info:
                _write_audit_from_event(mapper, connection, target, "delete")
                mock_info.assert_called_once()

    def test_user_operation_writes_to_work_logs(self, svc_audit_module):
        from app.services.audit_event_handler import _write_audit_from_event
        mapper = MagicMock()
        connection = MagicMock()
        local_table = MagicMock()
        mapper.local_table = local_table
        target = MagicMock(spec=SupportedVillage, name="红星村", id=5)
        with patch("app.services.audit_event_handler._resolve_actor_id", return_value=(42, False)):
            _write_audit_from_event(mapper, connection, target, "create")
            connection.execute.assert_called_once()

    def test_exception_handling(self, svc_audit_module):
        from app.services.audit_event_handler import _write_audit_from_event
        mapper = MagicMock()
        connection = MagicMock()
        connection.execute.side_effect = Exception("db error")
        target = MagicMock(spec=SupportedVillage, name="红星村", id=5)
        with patch("app.services.audit_event_handler._resolve_actor_id", return_value=(42, False)):
            _write_audit_from_event(mapper, connection, target, "update")


# ---------------------------------------------------------------------------
# 事件监听回调
# ---------------------------------------------------------------------------

class TestEventCallbacks:
    @pytest.fixture(autouse=True)
    def _setup(self, svc_audit_module):
        self.mapper = MagicMock()
        self.connection = MagicMock()
        self.target = MagicMock(name="测试对象")

    def test_after_insert(self):
        from app.services.audit_event_handler import _after_insert
        with patch("app.services.audit_event_handler._write_audit_from_event") as mock:
            _after_insert(self.mapper, self.connection, self.target)
            mock.assert_called_once_with(self.mapper, self.connection, self.target, "create")

    def test_after_update(self):
        from app.services.audit_event_handler import _after_update
        with patch("app.services.audit_event_handler._write_audit_from_event") as mock:
            _after_update(self.mapper, self.connection, self.target)
            mock.assert_called_once_with(self.mapper, self.connection, self.target, "update")

    def test_after_delete(self):
        from app.services.audit_event_handler import _after_delete
        with patch("app.services.audit_event_handler._write_audit_from_event") as mock:
            _after_delete(self.mapper, self.connection, self.target)
            mock.assert_called_once_with(self.mapper, self.connection, self.target, "delete")


# ---------------------------------------------------------------------------
# setup_audit_events / teardown_audit_events
# ---------------------------------------------------------------------------

class TestAuditEventLifecycle:
    def test_setup_default_models(self):
        """默认模型列表 + 事件注册。"""
        from app.services.audit_event_handler import setup_audit_events
        with patch("app.services.audit_event_handler.event.listen") as mock_listen:
            result = setup_audit_events()
            # 26 个默认模型 * 3 个事件 = 78
            assert result == 26
            assert mock_listen.call_count == 78

    def test_setup_custom_models(self):
        from app.services.audit_event_handler import setup_audit_events
        dummy = MagicMock()
        with patch("app.services.audit_event_handler.event.listen") as mock_listen:
            result = setup_audit_events([dummy])
            assert result == 1
            call_args = mock_listen.call_args_list[0]
            assert call_args[0][0] is dummy
            assert call_args[0][1] == "after_insert"
            assert callable(call_args[0][2])




# ---------------------------------------------------------------------------
# 辅助 fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def svc_audit_module():
    """确保模块被导入。"""
    import app.services.audit_event_handler  # noqa: F401
    return True
