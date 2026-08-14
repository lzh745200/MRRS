"""
审批工作流服务单元测试 (100% coverage target)
覆盖: app/services/approval_workflow_service.py
"""
import pytest
from unittest.mock import MagicMock, patch

# 预加载所有模型以避免懒加载导致的 mapper 解析错误
import app.models
for _name in app.models.__all__:
    try:
        getattr(app.models, _name)
    except Exception:
        pass

from app.models.approval import ApprovalAction, ApprovalStatus


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def svc(mock_db):
    from app.services.approval_workflow_service import ApprovalWorkflowService
    return ApprovalWorkflowService(db=mock_db)


def make_mock_query(mock_db, return_value=None):
    """Helper: configure mock_db.query chain to return desired value from .first() or .all()"""
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.options.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = return_value or []
    mock_query.first.return_value = return_value[0] if return_value else None
    return mock_query


# ══════════════════════════════════════════════════════════════
# Init
# ══════════════════════════════════════════════════════════════


class TestInit:
    def test_init_stores_db(self, mock_db):
        from app.services.approval_workflow_service import ApprovalWorkflowService
        svc = ApprovalWorkflowService(db=mock_db)
        assert svc.db is mock_db


# ══════════════════════════════════════════════════════════════
# Workflow CRUD
# ══════════════════════════════════════════════════════════════


class TestCreateWorkflow:
    def test_too_many_nodes_raises(self, svc):
        with pytest.raises(ValueError, match="最多支持5级审批"):
            svc.create_workflow("test", "fund", [{"name": f"n{i}"} for i in range(6)])

    def test_zero_nodes_raises(self, svc):
        with pytest.raises(ValueError, match="至少需要1个审批节点"):
            svc.create_workflow("test", "fund", [])

    def test_creates_workflow_with_nodes(self, svc, mock_db):
        mock_db.add = MagicMock()
        mock_db.flush = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        nodes_data = [
            {"name": "初审", "approver_type": "user", "approver_id": 1, "timeout_hours": 24},
            {"name": "复审", "approver_type": "role", "approver_id": 2},
        ]
        result = svc.create_workflow("test_wf", "fund", nodes_data, description="desc", created_by=10)

        assert result is not None
        assert result.name == "test_wf"
        assert result.entity_type == "fund"
        assert result.description == "desc"
        assert result.created_by == 10
        assert result.is_active is True
        # 1 workflow + 2 nodes added
        assert mock_db.add.call_count == 3
        mock_db.flush.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(result)

    def test_creates_with_defaults(self, svc, mock_db):
        mock_db.add = MagicMock()
        mock_db.flush = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = svc.create_workflow("test", "fund", [{}])

        assert result is not None
        # node gets default name/approver_type/timeout_hours
        mock_db.add.assert_called()
        mock_db.commit.assert_called_once()


class TestGetWorkflow:
    def test_found(self, svc, mock_db):
        mock_wf = MagicMock()
        make_mock_query(mock_db, [mock_wf])
        result = svc.get_workflow(1)
        assert result is mock_wf

    def test_not_found(self, svc, mock_db):
        make_mock_query(mock_db, [])
        result = svc.get_workflow(999)
        assert result is None


class TestListWorkflows:
    def test_no_filters(self, svc, mock_db):
        items = [MagicMock(), MagicMock()]
        make_mock_query(mock_db, items)
        result = svc.list_workflows()
        assert result == items

    def test_filter_by_entity_type(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        mock_query.filter.return_value = mock_query
        result = svc.list_workflows(entity_type="fund")
        assert result == items
        mock_query.filter.assert_called_once()

    def test_filter_by_is_active(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        result = svc.list_workflows(is_active=True)
        assert result == items

    def test_filter_by_both(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        # force filter to return self for chaining
        mock_query.filter.return_value = mock_query
        result = svc.list_workflows(entity_type="fund", is_active=True)
        assert result == items
        # filter called twice
        assert mock_query.filter.call_count == 2

    def test_is_active_false(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        mock_query.filter.return_value = mock_query
        result = svc.list_workflows(is_active=False)
        assert result == items
        mock_query.filter.assert_called()


class TestUpdateWorkflow:
    def test_not_found(self, svc, mock_db):
        with patch.object(svc, "get_workflow", return_value=None):
            result = svc.update_workflow(999, name="new")
            assert result is None

    def test_update_all_fields(self, svc, mock_db):
        mock_wf = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()
        with patch.object(svc, "get_workflow", return_value=mock_wf):
            result = svc.update_workflow(1, name="new_name", description="new_desc", is_active=False)
            assert result is mock_wf
            assert mock_wf.name == "new_name"
            assert mock_wf.description == "new_desc"
            assert mock_wf.is_active is False
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once_with(mock_wf)

    def test_update_only_name(self, svc, mock_db):
        mock_wf = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()
        with patch.object(svc, "get_workflow", return_value=mock_wf):
            result = svc.update_workflow(1, name="only_name")
            assert result is mock_wf
            assert mock_wf.name == "only_name"
            mock_db.commit.assert_called_once()


class TestDeleteWorkflow:
    def test_not_found(self, svc, mock_db):
        with patch.object(svc, "get_workflow", return_value=None):
            assert svc.delete_workflow(999) is False

    def test_success(self, svc, mock_db):
        mock_wf = MagicMock()
        mock_db.delete = MagicMock()
        mock_db.commit = MagicMock()
        with patch.object(svc, "get_workflow", return_value=mock_wf):
            assert svc.delete_workflow(1) is True
            mock_db.delete.assert_called_once_with(mock_wf)
            mock_db.commit.assert_called_once()


class TestEnsureDefaultWorkflow:
    def test_existing_returned(self, svc, mock_db):
        existing = MagicMock()
        mock_query = make_mock_query(mock_db, [existing])
        result = svc.ensure_default_workflow("fund")
        assert result is existing

    def test_creates_new(self, svc, mock_db):
        make_mock_query(mock_db, [])
        mock_db.add = MagicMock()
        mock_db.flush = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = svc.ensure_default_workflow("fund", user_id=42)

        assert result is not None
        assert result.name == "fund默认审批流程"
        assert result.entity_type == "fund"
        mock_db.commit.assert_called()


# ══════════════════════════════════════════════════════════════
# Task Operations
# ══════════════════════════════════════════════════════════════


class TestSubmitApproval:
    def test_no_workflow_returns_none(self, svc, mock_db):
        mock_query = make_mock_query(mock_db, [])
        mock_query.options.return_value.filter.return_value.first.return_value = None
        result = svc.submit_approval("fund", 1, 100)
        assert result is None

    def test_workflow_no_nodes_returns_none(self, svc, mock_db):
        mock_wf = MagicMock()
        mock_wf.nodes = []
        mock_query = make_mock_query(mock_db, [])
        mock_query.options.return_value.filter.return_value.first.return_value = mock_wf
        result = svc.submit_approval("fund", 1, 100)
        assert result is None

    def test_success(self, svc, mock_db):
        first_node = MagicMock()
        first_node.approver_id = 200
        mock_wf = MagicMock()
        mock_wf.id = 10
        mock_wf.nodes = [first_node]
        mock_query = make_mock_query(mock_db, [])
        mock_query.options.return_value.filter.return_value.first.return_value = mock_wf
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = svc.submit_approval(
            "fund", 1, 100,
            change_data={"name": "new"}, original_data={"name": "old"},
            title="审批测试",
        )

        assert result is not None
        assert result.workflow_id == 10
        assert result.entity_type == "fund"
        assert result.entity_id == 1
        assert result.submitter_id == 100
        assert result.current_level == 1
        assert result.current_approver_id == 200
        assert result.status == ApprovalStatus.PENDING.value
        assert result.change_data == {"name": "new"}
        assert result.original_data == {"name": "old"}
        assert result.title == "审批测试"
        # submit_approval creates ApprovalTask + Message notification = 2 add/commit calls
        assert mock_db.add.call_count == 2
        assert mock_db.commit.call_count == 2
        mock_db.refresh.assert_called_once()


class TestGetTask:
    def test_found(self, svc, mock_db):
        mock_task = MagicMock()
        mock_query = make_mock_query(mock_db, [mock_task])
        mock_query.options.return_value.filter.return_value.first.return_value = mock_task
        assert svc.get_task(1) is mock_task

    def test_not_found(self, svc, mock_db):
        mock_query = make_mock_query(mock_db, [])
        mock_query.options.return_value.filter.return_value.first.return_value = None
        assert svc.get_task(999) is None


class TestGetPendingTasks:
    def test_returns_list(self, svc, mock_db):
        items = [MagicMock(), MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        result = svc.get_pending_tasks(approver_id=50)
        assert result == items


class TestGetAllTasksWithCount:
    def test_no_filters(self, svc, mock_db):
        items = [MagicMock(), MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        mock_query.count.return_value = 2

        result = svc.get_all_tasks_with_count()
        assert result == {"items": items, "total": 2}

    def test_with_filters(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1

        result = svc.get_all_tasks_with_count(
            entity_type="fund", status="pending", submitter_id=100
        )
        assert result == {"items": items, "total": 1}
        # filter called 3 times (entity_type, status, submitter_id)
        assert mock_query.filter.call_count == 3

    def test_filter_by_entity_type_only(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        result = svc.get_all_tasks_with_count(entity_type="fund")
        assert result["total"] == 1

    def test_filter_by_status_only(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        result = svc.get_all_tasks_with_count(status="approved")
        assert result["total"] == 1

    def test_filter_by_submitter_only(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        result = svc.get_all_tasks_with_count(submitter_id=50)
        assert result["total"] == 1


class TestApproveTask:
    def test_task_not_found(self, svc, mock_db):
        with patch.object(svc, "get_task", return_value=None):
            result = svc.approve_task(1, 10)
            assert result is None

    def test_task_not_pending(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.APPROVED.value
        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.approve_task(1, 10)
            assert result is None

    def test_wrong_approver(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_approver_id = 20
        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.approve_task(1, 10)  # 10 != 20
            assert result is None

    def test_standalone_skips_approver_check(self, svc, mock_db):
        mock_node = MagicMock()
        mock_node.level = 2
        mock_node.approver_id = 30

        mock_wf = MagicMock()
        mock_wf.nodes = [MagicMock(level=1), mock_node]

        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_level = 1
        mock_task.current_approver_id = 20
        mock_task.workflow = mock_wf
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.approve_task(1, 10, standalone=True)
            assert result is not None
            assert result.current_level == 2
            assert result.current_approver_id == 30
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_approve_final_level(self, svc, mock_db):
        mock_node = MagicMock()
        mock_node.level = 1
        mock_node.approver_id = 20

        mock_wf = MagicMock()
        mock_wf.nodes = [mock_node]

        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_level = 1
        mock_task.current_approver_id = 20
        mock_task.workflow = mock_wf
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.approve_task(1, 20)
            assert result is not None
            assert result.status == ApprovalStatus.APPROVED.value
            assert result.completed_at is not None
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_approve_middle_level(self, svc, mock_db):
        nodes = [
            MagicMock(level=1, approver_id=20),
            MagicMock(level=2, approver_id=30),
            MagicMock(level=3, approver_id=40),
        ]
        mock_wf = MagicMock()
        mock_wf.nodes = nodes

        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_level = 2
        mock_task.current_approver_id = 30
        mock_task.workflow = mock_wf
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.approve_task(1, 30)
            assert result is not None
            assert result.current_level == 3
            assert result.current_approver_id == 40
            assert result.status == ApprovalStatus.PENDING.value  # not final yet


class TestRejectTask:
    def test_task_not_found(self, svc, mock_db):
        with patch.object(svc, "get_task", return_value=None):
            result = svc.reject_task(1, 10)
            assert result is None

    def test_task_not_pending(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.APPROVED.value
        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.reject_task(1, 10)
            assert result is None

    def test_wrong_approver(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_approver_id = 20
        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.reject_task(1, 10)
            assert result is None

    def test_standalone_skips_approver_check(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_level = 1
        mock_task.current_approver_id = 20
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.reject_task(1, 10, standalone=True)
            assert result is not None
            assert result.status == ApprovalStatus.REJECTED.value
            assert result.completed_at is not None
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_success_with_opinion(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_level = 2
        mock_task.current_approver_id = 30
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.reject_task(1, 30, opinion="不同意")
            assert result is not None
            assert result.status == ApprovalStatus.REJECTED.value


class TestWithdrawTask:
    def test_not_found(self, svc, mock_db):
        with patch.object(svc, "get_task", return_value=None):
            result = svc.withdraw_task(1, 10)
            assert result is None

    def test_not_pending(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.APPROVED.value
        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.withdraw_task(1, 10)
            assert result is None

    def test_wrong_submitter(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.submitter_id = 100
        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.withdraw_task(1, 999)
            assert result is None

    def test_success(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.submitter_id = 100
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.withdraw_task(1, 100)
            assert result is not None
            assert result.status == ApprovalStatus.WITHDRAWN.value
            assert result.completed_at is not None
            mock_db.commit.assert_called_once()


class TestResubmitApproval:
    def test_not_found(self, svc, mock_db):
        with patch.object(svc, "get_task", return_value=None):
            result = svc.resubmit_approval(1, 10)
            assert result is None

    def test_wrong_status(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.PENDING.value
        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.resubmit_approval(1, 10)
            assert result is None

    def test_wrong_submitter(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.REJECTED.value
        mock_task.submitter_id = 100
        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.resubmit_approval(1, 999)
            assert result is None

    def test_success_with_change_data(self, svc, mock_db):
        nodes = [MagicMock(level=1, approver_id=50)]
        mock_wf = MagicMock()
        mock_wf.nodes = nodes

        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.REJECTED.value
        mock_task.submitter_id = 100
        mock_task.workflow = mock_wf
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.resubmit_approval(1, 100, change_data={"new": "data"})
            assert result is not None
            assert result.status == ApprovalStatus.PENDING.value
            assert result.current_level == 1
            assert result.completed_at is None
            assert result.change_data == {"new": "data"}
            assert result.current_approver_id == 50
            mock_db.commit.assert_called_once()

    def test_success_without_change_data(self, svc, mock_db):
        mock_wf = MagicMock()
        mock_wf.nodes = []

        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.WITHDRAWN.value
        mock_task.submitter_id = 100
        mock_task.workflow = mock_wf
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.resubmit_approval(1, 100)
            assert result is not None
            assert result.status == ApprovalStatus.PENDING.value
            assert result.current_level == 1
            # No nodes, so current_approver_id stays as is (not overwritten)
            mock_db.commit.assert_called_once()

    def test_withdrawn_status_allowed(self, svc, mock_db):
        mock_wf = MagicMock()
        mock_wf.nodes = [MagicMock(level=1, approver_id=50)]

        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.WITHDRAWN.value
        mock_task.submitter_id = 100
        mock_task.workflow = mock_wf
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.resubmit_approval(1, 100)
            assert result is not None


class TestSubmitAndAutoApprove:
    def test_submit_fails_then_auto_create_and_approve(self, svc, mock_db):
        """submit_approval returns None -> ensure_default_workflow -> submit again -> auto approve"""
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = ApprovalStatus.APPROVED.value
        mock_task.workflow = MagicMock()
        mock_task.workflow.nodes = [
            MagicMock(level=1, approver_id=100),
            MagicMock(level=2, approver_id=100),
        ]

        # First submit returns None, second returns task
        with patch.object(svc, "submit_approval", side_effect=[None, mock_task]):
            with patch.object(svc, "ensure_default_workflow") as mock_ensure:
                with patch.object(svc, "approve_task", return_value=mock_task):
                    result = svc.submit_and_auto_approve("fund", 1, 100)
                    assert result is not None
                    mock_ensure.assert_called_once_with("fund", user_id=100)

    def test_submit_succeeds_first_try(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = ApprovalStatus.APPROVED.value
        mock_task.workflow = MagicMock()
        mock_task.workflow.nodes = [MagicMock(level=1, approver_id=100)]

        with patch.object(svc, "submit_approval", return_value=mock_task):
            with patch.object(svc, "approve_task", return_value=mock_task):
                result = svc.submit_and_auto_approve("fund", 1, 100)
                assert result is not None

    def test_approve_breaks_on_rejected(self, svc, mock_db):
        """approve_task returns task with status REJECTED -> loop breaks"""
        rejected_task = MagicMock()
        rejected_task.id = 1
        rejected_task.status = ApprovalStatus.REJECTED.value
        rejected_task.workflow = MagicMock()
        rejected_task.workflow.nodes = [
            MagicMock(level=1, approver_id=100),
            MagicMock(level=2, approver_id=100),
        ]

        with patch.object(svc, "submit_approval", return_value=rejected_task):
            with patch.object(svc, "approve_task", return_value=rejected_task):
                result = svc.submit_and_auto_approve("fund", 1, 100)
                assert result is not None
                assert result.status == ApprovalStatus.REJECTED.value

    def test_approve_breaks_on_none(self, svc, mock_db):
        """approve_task returns None -> loop breaks"""
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.workflow = MagicMock()
        mock_task.workflow.nodes = [
            MagicMock(level=1, approver_id=100),
            MagicMock(level=2, approver_id=100),
        ]

        with patch.object(svc, "submit_approval", return_value=mock_task):
            with patch.object(svc, "approve_task", return_value=None):
                result = svc.submit_and_auto_approve("fund", 1, 100)
                assert result is None

    def test_both_submits_fail(self, svc, mock_db):
        """Both submit attempts return None -> return None"""
        with patch.object(svc, "submit_approval", return_value=None):
            with patch.object(svc, "ensure_default_workflow"):
                result = svc.submit_and_auto_approve("fund", 1, 100)
                assert result is None


class TestTransferTask:
    def test_not_found(self, svc, mock_db):
        with patch.object(svc, "get_task", return_value=None):
            result = svc.transfer_task(1, 10, 20)
            assert result is None

    def test_not_pending(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.APPROVED.value
        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.transfer_task(1, 10, 20)
            assert result is None

    def test_wrong_approver(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_approver_id = 30
        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.transfer_task(1, 10, 20)
            assert result is None

    def test_success(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_level = 2
        mock_task.current_approver_id = 10
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.transfer_task(1, 10, 20, reason="忙不过来")
            assert result is not None
            assert result.current_approver_id == 20
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            # verify transfer record attributes
            record = mock_db.add.call_args[0][0]
            assert record.action == ApprovalAction.TRANSFER.value
            assert record.transfer_to_id == 20
            assert record.transfer_reason == "忙不过来"


class TestBatchApprove:
    def test_all_succeed(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.id = 1
        with patch.object(svc, "approve_task", return_value=mock_task):
            result = svc.batch_approve([1, 2, 3], 10)
            assert result == {"success": [1, 2, 3], "failed": []}

    def test_some_fail(self, svc, mock_db):
        with patch.object(svc, "approve_task", side_effect=[
            MagicMock(id=1),
            None,
            MagicMock(id=3),
        ]):
            result = svc.batch_approve([1, 2, 3], 10)
            assert result["success"] == [1, 3]
            assert len(result["failed"]) == 1
            assert result["failed"][0]["id"] == 2

    def test_exception_handling(self, svc, mock_db):
        with patch.object(svc, "approve_task", side_effect=[
            MagicMock(id=1),
            ValueError("DB error"),
            MagicMock(id=3),
        ]):
            result = svc.batch_approve([1, 2, 3], 10)
            assert result["success"] == [1, 3]
            assert len(result["failed"]) == 1
            assert result["failed"][0]["id"] == 2
            assert "DB error" in result["failed"][0]["reason"]


class TestAutoApproveAllPending:
    def test_no_pending(self, svc, mock_db):
        mock_query = make_mock_query(mock_db, [])
        mock_query.all.return_value = []
        result = svc.auto_approve_all_pending(1)
        assert result == {"total_pending": 0, "approved": 0, "failed": 0}

    def test_some_approved(self, svc, mock_db):
        tasks = [MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)]
        mock_query = make_mock_query(mock_db, tasks)
        mock_query.all.return_value = tasks

        approved_task = MagicMock()
        approved_task.status = ApprovalStatus.APPROVED.value

        pending_task = MagicMock()
        pending_task.status = ApprovalStatus.PENDING.value

        with patch.object(svc, "approve_task", side_effect=[
            approved_task,  # task 1 -> approved
            pending_task,   # task 2 -> still pending
            approved_task,  # task 3 -> approved
        ]):
            result = svc.auto_approve_all_pending(1)
            assert result == {"total_pending": 3, "approved": 2, "failed": 1}


# ══════════════════════════════════════════════════════════════
# History & Diff
# ══════════════════════════════════════════════════════════════


class TestGetApprovalHistory:
    def test_no_filters(self, svc, mock_db):
        items = [MagicMock(), MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        result = svc.get_approval_history()
        assert result == items

    def test_with_entity_filter(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        # joinedload returns same mock; join returns same mock
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        result = svc.get_approval_history(entity_type="fund", entity_id=1)
        assert result == items

    def test_with_submitter_filter(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        result = svc.get_approval_history(submitter_id=100)
        assert result == items

    def test_with_status_filter(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        result = svc.get_approval_history(status="pending")
        assert result == items

    def test_with_all_filters(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        result = svc.get_approval_history(
            entity_type="fund", entity_id=1, submitter_id=100, status="pending"
        )
        assert result == items
        # join called once
        mock_query.join.assert_called_once()

    def test_no_join_without_filters(self, svc, mock_db):
        items = [MagicMock()]
        mock_query = make_mock_query(mock_db, items)
        # no join should be called
        result = svc.get_approval_history()
        assert result == items
        mock_query.join.assert_not_called()


class TestGetTaskDiff:
    def test_not_found(self, svc, mock_db):
        with patch.object(svc, "get_task", return_value=None):
            result = svc.get_task_diff(999)
            assert result is None

    def test_with_data(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.id = 5
        mock_task.entity_type = "fund"
        mock_task.entity_id = 10
        mock_task.change_data = {"name": "new"}
        mock_task.original_data = {"name": "old"}

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.get_task_diff(5)
            # 新契约：change_data/original_data/diff_fields（前端使用）
            assert result["change_data"] == {"name": "new"}
            assert result["original_data"] == {"name": "old"}
            assert result["diff_fields"] == ["name"]
            # 旧契约：changed/original 保留向后兼容
            assert result["changed"] == {"name": "new"}
            assert result["original"] == {"name": "old"}
            assert result["task_id"] == 5
            assert result["entity_type"] == "fund"
            assert result["entity_id"] == 10

    def test_with_none_data(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.id = 5
        mock_task.entity_type = "fund"
        mock_task.entity_id = 10
        mock_task.change_data = None
        mock_task.original_data = None

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.get_task_diff(5)
            assert result["changed"] == {}
            assert result["original"] == {}
            assert result["change_data"] == {}
            assert result["original_data"] == {}
            assert result["diff_fields"] == []
            assert result["task_id"] == 5
            assert result["entity_type"] == "fund"
            assert result["entity_id"] == 10


# ══════════════════════════════════════════════════════════════
# 单机模式：未分配审批人任务处理（2026-08-14 修复）
# ══════════════════════════════════════════════════════════════


class TestUnassignedTaskActions:
    def test_approve_unassigned_allowed(self, svc, mock_db):
        mock_node = MagicMock()
        mock_node.level = 1
        mock_node.approver_id = None
        mock_wf = MagicMock()
        mock_wf.nodes = [mock_node]

        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_level = 1
        mock_task.current_approver_id = None
        mock_task.workflow = mock_wf
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.approve_task(1, 10)  # 非审批人、非 standalone
            assert result is not None
            assert result.status == ApprovalStatus.APPROVED.value

    def test_reject_unassigned_allowed(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_level = 1
        mock_task.current_approver_id = None
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.reject_task(1, 10, opinion="驳回")
            assert result is not None
            assert result.status == ApprovalStatus.REJECTED.value

    def test_transfer_unassigned_allowed(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_level = 1
        mock_task.current_approver_id = None
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.transfer_task(1, 10, 20, reason="代转")
            assert result is not None
            assert result.current_approver_id == 20

    def test_transfer_standalone_admin_override(self, svc, mock_db):
        mock_task = MagicMock()
        mock_task.id = 1
        mock_task.status = ApprovalStatus.PENDING.value
        mock_task.current_level = 1
        mock_task.current_approver_id = 99
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.transfer_task(1, 10, 20, reason="管理员代转", standalone=True)
            assert result is not None
            assert result.current_approver_id == 20


class TestResubmitRecord:
    def test_resubmit_adds_resubmit_record(self, svc, mock_db):
        nodes = [MagicMock(level=1, approver_id=50)]
        mock_wf = MagicMock()
        mock_wf.nodes = nodes

        mock_task = MagicMock()
        mock_task.id = 3
        mock_task.status = ApprovalStatus.REJECTED.value
        mock_task.submitter_id = 100
        mock_task.workflow = mock_wf
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        with patch.object(svc, "get_task", return_value=mock_task):
            result = svc.resubmit_approval(3, 100)
            assert result is not None
            # 记录「重新提交」动作，使审批意见不再显示旧驳回原因
            records = [call.args[0] for call in mock_db.add.call_args_list]
            assert len(records) == 1
            assert records[0].action == "resubmit"
            assert records[0].opinion is None


class TestDefaultWorkflowUnassigned:
    def test_default_workflow_node_has_no_approver(self, svc, mock_db):
        make_mock_query(mock_db, [])
        mock_db.add = MagicMock()
        mock_db.flush = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

        result = svc.ensure_default_workflow("fund", user_id=42)

        assert result is not None
        # 默认节点不指定审批人：单机模式下任何登录用户均可审批
        nodes = [call.args[0] for call in mock_db.add.call_args_list]
        node = [n for n in nodes if hasattr(n, "approver_id") and n.approver_type == "user"]
        assert len(node) == 1
        assert node[0].approver_id is None


class TestResolveRoleApprover:
    def test_admin_role_resolves_to_admin_user(self, svc):
        from app.services.approval_workflow_service import ApprovalWorkflowService

        user = MagicMock()
        user.id = 7
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = user
        session.close = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=session):
            result = ApprovalWorkflowService._resolve_role_approver_id("admin")
        assert result == 7

    def test_no_admin_user_returns_none(self, svc):
        from app.services.approval_workflow_service import ApprovalWorkflowService

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        session.close = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=session):
            assert ApprovalWorkflowService._resolve_role_approver_id("admin") is None

    def test_non_admin_role_returns_none(self, svc):
        from app.services.approval_workflow_service import ApprovalWorkflowService

        session = MagicMock()
        session.close = MagicMock()
        with patch("app.core.database.SessionLocal", return_value=session):
            assert ApprovalWorkflowService._resolve_role_approver_id("user") is None

    def test_session_error_returns_none(self, svc):
        from app.services.approval_workflow_service import ApprovalWorkflowService

        with patch("app.core.database.SessionLocal", side_effect=RuntimeError("boom")):
            assert ApprovalWorkflowService._resolve_role_approver_id("admin") is None
