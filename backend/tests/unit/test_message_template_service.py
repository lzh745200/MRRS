"""消息模板服务单元测试 (100% coverage)"""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def svc(mock_db):
    from app.services.message_template_service import MessageTemplateService
    return MessageTemplateService(db=mock_db)


class TestInit:
    def test_stores_db(self, svc, mock_db):
        assert svc.db is mock_db
        assert svc._history == []


class TestCreateTemplate:
    def test_success(self, svc, mock_db):
        svc.get_template_by_code = MagicMock(return_value=None)
        mock_template = MagicMock()
        with patch('app.services.message_template_service.MessageTemplate', return_value=mock_template):
            result = svc.create_template(
                code="test_code",
                name="Test Template",
                message_type="system",
                title_template="Title",
                content_template="Content",
                email_subject_template="Subject",
                email_body_template="Body",
                description="Desc",
                is_active=False,
                is_system=True,
                created_by=1,
            )
            assert result is mock_template
            mock_db.add.assert_called_once_with(mock_template)
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once_with(mock_template)

    def test_success_minimal(self, svc, mock_db):
        svc.get_template_by_code = MagicMock(return_value=None)
        mock_template = MagicMock()
        with patch('app.services.message_template_service.MessageTemplate', return_value=mock_template):
            result = svc.create_template(
                code="min", name="Min", message_type="task",
                title_template="T", content_template="C",
            )
            assert result is mock_template

    def test_invalid_message_type(self, svc):
        svc.get_template_by_code = MagicMock(return_value=None)
        with pytest.raises(ValueError, match="无效的消息类型"):
            svc.create_template(code="x", name="x", message_type="invalid",
                                title_template="T", content_template="C")

    def test_duplicate_code(self, svc):
        svc.get_template_by_code = MagicMock(return_value=MagicMock())
        with pytest.raises(ValueError, match="模板编码已存在"):
            svc.create_template(code="dup", name="Dup", message_type="system",
                                title_template="T", content_template="C")


class TestGetTemplate:
    def test_found(self, svc, mock_db):
        mock_template = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_template
        assert svc.get_template(1) is mock_template

    def test_not_found(self, svc, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert svc.get_template(999) is None


class TestGetTemplateByCode:
    def test_found(self, svc, mock_db):
        mock_template = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_template
        assert svc.get_template_by_code("code") is mock_template

    def test_not_found(self, svc, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert svc.get_template_by_code("missing") is None


class TestListTemplates:
    @pytest.fixture
    def mock_query(self, mock_db):
        q = MagicMock()
        mock_db.query.return_value = q
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = [MagicMock()]
        return q

    def test_no_filters(self, svc, mock_db, mock_query):
        result = svc.list_templates()
        assert len(result) == 1
        mock_query.filter.assert_not_called()
        mock_query.order_by.assert_called_once()
        mock_query.offset.assert_called_once_with(0)
        mock_query.limit.assert_called_once_with(100)

    def test_message_type_filter(self, svc, mock_db, mock_query):
        svc.list_templates(message_type="approval")
        assert mock_query.filter.call_count == 1

    def test_is_active_filter_true(self, svc, mock_db, mock_query):
        svc.list_templates(is_active=True)
        assert mock_query.filter.call_count == 1

    def test_is_active_filter_false(self, svc, mock_db, mock_query):
        svc.list_templates(is_active=False)
        assert mock_query.filter.call_count == 1

    def test_is_system_filter_true(self, svc, mock_db, mock_query):
        svc.list_templates(is_system=True)
        assert mock_query.filter.call_count == 1

    def test_is_system_filter_false(self, svc, mock_db, mock_query):
        svc.list_templates(is_system=False)
        assert mock_query.filter.call_count == 1

    def test_skip_limit(self, svc, mock_db, mock_query):
        svc.list_templates(skip=10, limit=5)
        mock_query.offset.assert_called_once_with(10)
        mock_query.limit.assert_called_once_with(5)

    def test_all_filters(self, svc, mock_db, mock_query):
        svc.list_templates(message_type="task", is_active=True, is_system=False,
                           skip=1, limit=2)
        assert mock_query.filter.call_count == 3


class TestUpdateTemplate:
    def test_not_found(self, svc):
        svc.get_template = MagicMock(return_value=None)
        assert svc.update_template(999) is None

    def test_all_fields_changed(self, svc, mock_db):
        template = MagicMock()
        template.name = "Old"
        template.title_template = "Old title"
        template.content_template = "Old content"
        template.email_subject_template = "Old subject"
        template.email_body_template = "Old body"
        template.description = "Old desc"
        template.is_active = False
        svc.get_template = MagicMock(return_value=template)

        svc.update_template(1, name="New", title_template="New title",
                            content_template="New content",
                            email_subject_template="New subject",
                            email_body_template="New body",
                            description="New desc", is_active=True, modified_by=5)
        assert template.name == "New"
        assert template.is_active is True
        assert len(svc._history) == 7
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(template)

    def test_partial_fields(self, svc, mock_db):
        template = MagicMock()
        template.name = "Old"
        template.title_template = "Old title"
        template.content_template = "Old content"
        template.email_subject_template = None
        template.email_body_template = None
        template.description = "Old desc"
        template.is_active = True
        svc.get_template = MagicMock(return_value=template)

        svc.update_template(1, name="New")
        assert template.name == "New"
        assert template.title_template == "Old title"
        assert len(svc._history) == 1

    def test_no_changes_all_none(self, svc, mock_db):
        template = MagicMock()
        svc.get_template = MagicMock(return_value=template)
        result = svc.update_template(1)
        assert result is template
        assert len(svc._history) == 0
        mock_db.commit.assert_called_once()

    def test_same_values_no_history(self, svc, mock_db):
        template = MagicMock()
        template.name = "Same"
        template.title_template = "Same"
        template.content_template = "Same"
        template.email_subject_template = None
        template.email_body_template = None
        template.description = "Same"
        template.is_active = True
        svc.get_template = MagicMock(return_value=template)

        svc.update_template(1, name="Same", title_template="Same",
                            content_template="Same")
        assert len(svc._history) == 0

    def test_modified_by_recorded(self, svc, mock_db):
        template = MagicMock()
        template.name = "Old"
        template.title_template = "T"
        template.content_template = "C"
        template.email_subject_template = None
        template.email_body_template = None
        template.description = None
        template.is_active = True
        svc.get_template = MagicMock(return_value=template)

        svc.update_template(1, name="New", modified_by=42)
        assert svc._history[0].modified_by == 42
        assert svc._history[0].template_id == 1
        assert svc._history[0].field == "name"
        assert svc._history[0].old_value == "Old"
        assert svc._history[0].new_value == "New"


class TestDeleteTemplate:
    def test_not_found(self, svc):
        svc.get_template = MagicMock(return_value=None)
        assert svc.delete_template(999) is False

    def test_is_system_template(self, svc):
        template = MagicMock(is_system=True)
        svc.get_template = MagicMock(return_value=template)
        assert svc.delete_template(1) is False

    def test_success(self, svc, mock_db):
        template = MagicMock(is_system=False)
        svc.get_template = MagicMock(return_value=template)
        assert svc.delete_template(1) is True
        mock_db.delete.assert_called_once_with(template)
        mock_db.commit.assert_called_once()


class TestEnableDisable:
    def test_enable(self, svc):
        svc.update_template = MagicMock()
        result = svc.enable_template(1, modified_by=3)
        svc.update_template.assert_called_once_with(1, is_active=True, modified_by=3)
        assert result is svc.update_template.return_value

    def test_disable(self, svc):
        svc.update_template = MagicMock()
        result = svc.disable_template(1, modified_by=4)
        svc.update_template.assert_called_once_with(1, is_active=False, modified_by=4)
        assert result is svc.update_template.return_value


class TestRenderTemplate:
    def test_not_found(self, svc):
        svc.get_template_by_code = MagicMock(return_value=None)
        assert svc.render_template("missing", {}) is None

    def test_inactive(self, svc):
        template = MagicMock(is_active=False)
        svc.get_template_by_code = MagicMock(return_value=template)
        assert svc.render_template("code", {}) is None

    def test_success(self, svc):
        template = MagicMock()
        template.is_active = True
        template.title_template = "Hello {username}"
        template.content_template = "Welcome {username}"
        template.email_subject_template = "Subject: {title}"
        template.email_body_template = "<p>Body: {title}</p>"
        svc.get_template_by_code = MagicMock(return_value=template)

        result = svc.render_template("code", {"username": "Alice", "title": "Test"}, use_defaults=False)
        assert result["title"] == "Hello Alice"
        assert result["content"] == "Welcome Alice"
        assert result["email_subject"] == "Subject: Test"
        assert result["email_body"] == "<p>Body: Test</p>"

    def test_email_templates_none(self, svc):
        template = MagicMock()
        template.is_active = True
        template.title_template = "{username}"
        template.content_template = "{username}"
        template.email_subject_template = None
        template.email_body_template = None
        svc.get_template_by_code = MagicMock(return_value=template)

        result = svc.render_template("code", {"username": "Bob"}, use_defaults=False)
        assert result["title"] == "Bob"
        assert result["content"] == "Bob"
        assert result["email_subject"] is None
        assert result["email_body"] is None

    def test_with_defaults(self, svc):
        template = MagicMock()
        template.is_active = True
        template.title_template = "{system_name}"
        template.content_template = "Hello"
        template.email_subject_template = None
        template.email_body_template = None
        svc.get_template_by_code = MagicMock(return_value=template)

        result = svc.render_template("code", {}, use_defaults=True)
        assert "{system_name}" not in result["title"]
        assert "管理" in result["title"]


class TestRenderTitle:
    def test_found(self, svc):
        svc.render_template = MagicMock(return_value={"title": "Hi"})
        assert svc.render_title("code", {}) == "Hi"

    def test_not_found(self, svc):
        svc.render_template = MagicMock(return_value=None)
        assert svc.render_title("code", {}) is None


class TestRenderContent:
    def test_found(self, svc):
        svc.render_template = MagicMock(return_value={"content": "Hi"})
        assert svc.render_content("code", {}) == "Hi"

    def test_not_found(self, svc):
        svc.render_template = MagicMock(return_value=None)
        assert svc.render_content("code", {}) is None


class TestRenderString:
    def test_empty_string(self, svc):
        assert svc._render_string("", {}) == ""

    def test_normal_substitution(self, svc):
        assert svc._render_string("Hello {name}", {"name": "World"}) == "Hello World"

    def test_missing_key(self, svc):
        result = svc._render_string("Hello {name}, {date}", {"name": "Alice"})
        assert "Alice" in result
        assert "{date}" in result

    def test_multiple_missing_keys_all_preserved(self, svc):
        """≥2 个缺失占位符：一次 format_map + __missing__ 全部保留原样。

        旧实现只回填首个缺失键，二次 format 仍会 KeyError 中断发送链路；
        新实现走 `_KeepMissingPlaceholders.__missing__`，覆盖其 return 分支。
        """
        result = svc._render_string("你好 {a}，欢迎 {b}，时间 {c}", {})
        assert result == "你好 {a}，欢迎 {b}，时间 {c}"


class TestPrepareVariables:
    def test_with_defaults(self, svc):
        result = svc._prepare_variables({"username": "Alice"}, use_defaults=True)
        assert result["username"] == "Alice"
        assert result["system_name"] == "帮扶管理系统"
        assert "time" in result
        assert "date" in result
        assert "datetime" in result

    def test_without_defaults(self, svc):
        result = svc._prepare_variables({"username": "Alice"}, use_defaults=False)
        assert result == {"username": "Alice"}

    def test_defaults_do_not_override(self, svc):
        result = svc._prepare_variables({"system_name": "Custom"}, use_defaults=True)
        assert result["system_name"] == "Custom"


class TestExtractVariables:
    def test_empty_string(self, svc):
        assert svc.extract_variables("") == []

    def test_finds_variables(self, svc):
        assert svc.extract_variables("Hello {name}, today is {date}") == ["name", "date"]

    def test_no_variables(self, svc):
        assert svc.extract_variables("Hello World") == []


class TestValidateVariables:
    def test_complete(self, svc):
        result = svc.validate_variables("Hello {name}", {"name": "Alice"})
        assert result["is_valid"] is True
        assert result["missing_variables"] == []
        assert result["extra_variables"] == []

    def test_missing(self, svc):
        result = svc.validate_variables("Hello {name} and {date}", {"name": "Alice"})
        assert result["is_valid"] is False
        assert "date" in result["missing_variables"]
        assert "name" in result["required_variables"]

    def test_extra(self, svc):
        result = svc.validate_variables("Hello {name}", {"name": "A", "extra": "B"})
        assert result["is_valid"] is True
        assert "extra" in result["extra_variables"]


class TestHistory:
    def test_record_history(self, svc):
        svc._record_history(1, "name", "old", "new", modified_by=5)
        assert len(svc._history) == 1
        entry = svc._history[0]
        assert entry.template_id == 1
        assert entry.field == "name"
        assert entry.old_value == "old"
        assert entry.new_value == "new"
        assert entry.modified_by == 5
        assert entry.modified_at is not None

    def test_record_history_without_modified_by(self, svc):
        svc._record_history(2, "is_active", False, True)
        entry = svc._history[0]
        assert entry.modified_by is None

    def test_get_template_history_filtered(self, svc):
        svc._record_history(1, "name", "a", "b")
        svc._record_history(1, "is_active", False, True)
        svc._record_history(2, "name", "x", "y")
        entries = svc.get_template_history(1)
        assert len(entries) == 2
        assert svc.get_template_history(2) == [svc._history[2]]
        assert svc.get_template_history(99) == []

    def test_get_all_history(self, svc):
        svc._record_history(1, "name", "a", "b")
        all_h = svc.get_all_history()
        assert len(all_h) == 1
        all_h.append("x")
        assert len(svc._history) == 1  # original unchanged

    def test_clear_history(self, svc):
        svc._record_history(1, "name", "a", "b")
        assert len(svc._history) == 1
        svc.clear_history()
        assert svc._history == []


class TestInitDefaultTemplates:
    def test_creates_all(self, svc):
        svc.get_template_by_code = MagicMock(return_value=None)
        svc.create_template = MagicMock(return_value=MagicMock())
        result = svc.init_default_templates()
        assert len(result) == 14

    def test_skips_existing(self, svc):
        svc.get_template_by_code = MagicMock(
            side_effect=lambda code: MagicMock() if code == "approval_submitted" else None
        )
        svc.create_template = MagicMock(return_value=MagicMock())
        result = svc.init_default_templates()
        assert len(result) == 13

    def test_all_existing(self, svc):
        svc.get_template_by_code = MagicMock(return_value=MagicMock())
        svc.create_template = MagicMock()
        result = svc.init_default_templates()
        assert len(result) == 0
        svc.create_template.assert_not_called()

    def test_with_created_by(self, svc):
        svc.get_template_by_code = MagicMock(return_value=None)
        svc.create_template = MagicMock(return_value=MagicMock())
        svc.init_default_templates(created_by=10)
        for call in svc.create_template.call_args_list:
            assert call.kwargs["created_by"] == 10


class TestGetDefaultTemplates:
    def test_returns_list(self, svc):
        result = svc._get_default_templates()
        assert isinstance(result, list)
        assert len(result) == 14
        for t in result:
            assert "code" in t
            assert "name" in t
            assert "message_type" in t
            assert "title_template" in t
            assert "content_template" in t
