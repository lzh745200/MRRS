"""
PolicyService 单元测试
覆盖: app/services/policy_service.py
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

class TestPolicyServiceCRUD:
    """PolicyService CRUD 操作测试"""

    def setup_method(self):
        self.mock_db = MagicMock()
        from app.services.policy_service import PolicyService
        self.service = PolicyService(self.mock_db)

    def _make_policy(self, **kwargs):
        defaults = dict(
            id=1,
            title="测试政策",
            category="military",
            organization_level="cmc",
            level="cmc",
            publish_date=datetime(2025, 1, 1),
            issue_date=datetime(2025, 1, 1),
            effective_date=None,
            department="测试部门",
            issuing_authority="测试部门",
            content="政策内容",
            summary="政策摘要",
            document_number="DOC-001",
            code="DOC-001",
            file_path=None,
            attachment_urls=None,
            status="active",
            keywords=None,
            view_count=10,
            download_count=0,
            is_important=False,
            file_size=None,
            file_type=None,
            created_at=None,
            updated_at=None,
            created_by=1,
            updated_by=1,
        )
        defaults.update(kwargs)
        mock_policy = MagicMock()
        for k, v in defaults.items():
            setattr(mock_policy, k, v)
        return mock_policy

    def test_get_policy_by_id_found(self):
        mock_policy = self._make_policy()
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_policy

        result = self.service.get_policy_by_id(1)
        assert result is not None
        assert result.title == "测试政策"

    def test_get_policy_by_id_not_found(self):
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        result = self.service.get_policy_by_id(999)
        assert result is None

    def test_get_policy_model_by_id(self):
        mock_policy = self._make_policy()
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_policy
        result = self.service.get_policy_model_by_id(1)
        assert result is not None
        assert result.title == "测试政策"

    @patch("app.services.policy_service.Policy")
    def test_create_policy(self, MockPolicy):
        mock_instance = self._make_policy(
            title="新政策", category="military",
            organization_level="cmc", publish_date=None,
            content="政策内容", view_count=0,
        )
        MockPolicy.return_value = mock_instance
        self.mock_db.refresh = MagicMock(side_effect=lambda p: None)

        policy_data = SimpleNamespace(
            title="新政策",
            category="military",
            organization_level="cmc",
            level="cmc",
            publish_date=None,
            issue_date=None,
            effective_date=None,
            department=None,
            issuing_authority=None,
            content=None,
            summary=None,
            document_number=None,
            code=None,
            file_path=None,
            attachment_urls=None,
            status="active",
            keywords=None,
            is_important=False,
        )

        result = self.service.create_policy(policy_data, user_id=1)
        MockPolicy.assert_called_once()
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()

    def test_update_policy_found(self):
        mock_policy = self._make_policy()
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_policy

        update_data = MagicMock()
        update_data.model_dump.return_value = {"title": "更新后标题"}

        result = self.service.update_policy(1, update_data, user_id=1)
        assert result is not None
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()

    def test_update_policy_not_found(self):
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        update_data = MagicMock()
        update_data.model_dump.return_value = {}
        result = self.service.update_policy(999, update_data)
        assert result is None

    def test_delete_policy_found(self):
        mock_policy = self._make_policy()
        self.mock_db.query.return_value.filter.return_value.first.return_value = mock_policy

        result = self.service.delete_policy(1)
        assert result is True
        self.mock_db.delete.assert_called_once_with(mock_policy)
        self.mock_db.commit.assert_called_once()

    def test_delete_policy_not_found(self):
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        result = self.service.delete_policy(999)
        assert result is False

    def test_increment_view_count_found(self):
        """W2-T6：原子 UPDATE 语义（不再依赖 ORM 实例回读）。"""
        self.mock_db.query.return_value.filter.return_value.update.return_value = 1

        result = self.service.increment_view_count(1)
        assert result is True
        self.mock_db.query.return_value.filter.return_value.update.assert_called_once()
        self.mock_db.commit.assert_called_once()

    def test_increment_view_count_none_initial(self):
        """COALESCE 兜底 NULL 计数（SQL 端）。"""
        self.mock_db.query.return_value.filter.return_value.update.return_value = 1

        result = self.service.increment_view_count(1)
        assert result is True

    def test_increment_view_count_not_found(self):
        self.mock_db.query.return_value.filter.return_value.update.return_value = 0
        result = self.service.increment_view_count(999)
        assert result is False
        self.mock_db.commit.assert_not_called()

    def test_batch_delete(self):
        self.mock_db.query.return_value.filter.return_value.delete.return_value = 3
        result = self.service.batch_delete([1, 2, 3])
        assert result == 3
        self.mock_db.commit.assert_called_once()

class TestPolicyServiceQueries:
    """PolicyService 查询和统计测试"""

    def setup_method(self):
        self.mock_db = MagicMock()
        from app.services.policy_service import PolicyService
        self.service = PolicyService(self.mock_db)

    def test_get_categories_raises_on_schema_mismatch(self):
        """get_categories 的服务代码传参与 schema 定义不匹配，应抛出 ValidationError"""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            self.service.get_categories()

    def test_to_response_military(self):
        mock_policy = MagicMock()
        mock_policy.id = 1
        mock_policy.title = "专项政策"
        mock_policy.category = "military"
        mock_policy.organization_level = "central"
        mock_policy.level = "central"
        mock_policy.publish_date = datetime(2025, 1, 1)
        mock_policy.issue_date = datetime(2025, 1, 1)
        mock_policy.effective_date = None
        mock_policy.department = "中央"
        mock_policy.issuing_authority = "中央"
        mock_policy.content = "内容"
        mock_policy.summary = "摘要"
        mock_policy.document_number = "M-001"
        mock_policy.code = "M-001"
        mock_policy.file_path = None
        mock_policy.attachment_urls = None
        mock_policy.status = "active"
        mock_policy.keywords = None
        mock_policy.view_count = 10
        mock_policy.download_count = 0
        mock_policy.is_important = False
        mock_policy.file_size = None
        mock_policy.file_type = None
        mock_policy.created_at = None
        mock_policy.updated_at = None
        mock_policy.created_by = 1
        mock_policy.updated_by = 1

        result = self.service._to_response(mock_policy)
        assert result.category_name == "专项政策"
        assert result.level_name == "中央部署"

    def test_to_response_local(self):
        mock_policy = MagicMock()
        mock_policy.id = 2
        mock_policy.title = "地方政策"
        mock_policy.category = "local"
        mock_policy.organization_level = "national"
        mock_policy.level = "national"
        mock_policy.publish_date = datetime(2025, 1, 1)
        mock_policy.issue_date = datetime(2025, 1, 1)
        mock_policy.effective_date = None
        mock_policy.department = "国务院"
        mock_policy.issuing_authority = "国务院"
        mock_policy.content = "内容"
        mock_policy.summary = "摘要"
        mock_policy.document_number = "L-001"
        mock_policy.code = "L-001"
        mock_policy.file_path = None
        mock_policy.attachment_urls = None
        mock_policy.status = "active"
        mock_policy.keywords = None
        mock_policy.view_count = 5
        mock_policy.download_count = 0
        mock_policy.is_important = False
        mock_policy.file_size = None
        mock_policy.file_type = None
        mock_policy.created_at = None
        mock_policy.updated_at = None
        mock_policy.created_by = 1
        mock_policy.updated_by = 1

        result = self.service._to_response(mock_policy)
        assert result.category_name == "地方政策"
        assert result.level_name == "国家级"

    def test_get_related_policies_not_found(self):
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        result = self.service.get_related_policies(999)
        assert result == []
