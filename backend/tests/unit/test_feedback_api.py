"""
意见反馈 API 全面测试
覆盖 backend/app/api/v1/feedback.py 的所有路由和分支

- GET  /api/v1/feedback  (list_feedback)
- POST /api/v1/feedback  (submit_feedback)
- async _get_user_from_token() 内部辅助函数

使用 FastAPI TestClient + dependency_overrides + MagicMock DB。
目标：100% 行/分支覆盖。
"""

import pytest
from unittest.mock import MagicMock, Mock, patch, AsyncMock
from datetime import datetime, timezone

from fastapi.testclient import TestClient


# ══════════════════════════════════════════════════════════════════════
# 测试辅助函数
# ══════════════════════════════════════════════════════════════════════

def _make_mock_fb(**kwargs):
    """构造一个模拟的 Feedback ORM 对象"""
    fb = MagicMock()
    fb.id = kwargs.get("id", 1)
    fb.category = kwargs.get("category", "bug")
    fb.content = kwargs.get("content", "测试反馈内容")
    fb.priority = kwargs.get("priority", "medium")
    fb.status = kwargs.get("status", "open")
    fb.user_name = kwargs.get("user_name", "testuser")
    fb.user_email = kwargs.get("user_email", "test@example.com")
    fb.created_at = kwargs.get("created_at",
        datetime(2026, 6, 15, 10, 30, 0, tzinfo=timezone.utc))
    fb.updated_at = kwargs.get("updated_at",
        datetime(2026, 6, 15, 10, 30, 0, tzinfo=timezone.utc))
    return fb


def _make_mock_db(items=None, total=None):
    """构造模拟的 DB Session。

    模拟 SQLAlchemy query 链式调用:
      db.query(Model).filter(...).order_by(...).offset(n).limit(m).all()
    以及 query 上的 count()
    """
    db = Mock()
    items = items or []
    total = total if total is not None else len(items)

    # 构建 query 链
    mock_all = Mock()
    mock_all.all.return_value = items

    mock_limit = Mock()
    mock_limit.all.return_value = items

    mock_offset = Mock()
    mock_offset.limit.return_value = mock_limit

    mock_order_by = Mock()
    mock_order_by.offset.return_value = mock_offset

    mock_filter = Mock()
    mock_filter.count.return_value = total
    mock_filter.order_by.return_value = mock_order_by
    mock_filter.offset.return_value = mock_offset
    mock_filter.limit.return_value = mock_limit
    mock_filter.all.return_value = items

    mock_query = Mock()
    mock_query.count.return_value = total
    mock_query.filter.return_value = mock_filter
    mock_query.order_by.return_value = mock_order_by
    mock_query.offset.return_value = mock_offset
    mock_query.limit.return_value = mock_limit
    mock_query.all.return_value = items

    db.query.return_value = mock_query
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.rollback = Mock()
    return db


def _setup_admin_override(app):
    """覆盖 get_current_user 为管理员用户"""
    from app.core.security import get_current_user

    admin = Mock()
    admin.id = 1
    admin.username = "admin"
    admin.role = "admin"
    admin.is_superuser = True
    admin.is_active = True

    async def _fake():
        return admin

    app.dependency_overrides[get_current_user] = _fake
    return admin


def _setup_db_override(app, mock_db):
    """覆盖 get_db 为 mock session"""
    from app.core.database import get_db

    def _gen():
        yield mock_db

    app.dependency_overrides[get_db] = _gen


def _clear_overrides(app):
    """清理所有依赖覆盖"""
    from app.core.database import get_db
    from app.core.security import get_current_user
    for dep in [get_db, get_current_user]:
        app.dependency_overrides.pop(dep, None)


# ══════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def app():
    """获取未修改的 FastAPI app 实例"""
    from app.main import app
    return app


@pytest.fixture
def c(app):
    """TestClient — 每次测试后自动清理 dependency_overrides"""
    tc = TestClient(app, raise_server_exceptions=False)
    yield tc
    _clear_overrides(app)


# ══════════════════════════════════════════════════════════════════════
# GET /api/v1/feedback — 获取反馈列表
# ══════════════════════════════════════════════════════════════════════

class TestListFeedback:
    """list_feedback 端点测试"""

    # ── 基础功能 ──

    def test_default_pagination(self, app, c):
        """默认分页参数：page=1, page_size=20, 无 type 过滤"""
        items = [_make_mock_fb(id=1)]
        mock_db = _make_mock_db(items=items, total=1)
        _setup_db_override(app, mock_db)
        _setup_admin_override(app)

        resp = c.get("/api/v1/feedback")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["total"] == 1
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 20
        assert len(data["data"]["items"]) == 1

    def test_response_item_fields(self, app, c):
        """验证响应中每个 item 的字段映射"""
        fb = _make_mock_fb(id=42, category="suggestion", content="内容ABC",
                           user_email="admin@org.mil", user_name="admin",
                           status="open")
        mock_db = _make_mock_db(items=[fb], total=1)
        _setup_db_override(app, mock_db)
        _setup_admin_override(app)

        resp = c.get("/api/v1/feedback")
        item = resp.json()["data"]["items"][0]
        assert item["id"] == 42
        assert item["type"] == "suggestion"        # category → type
        assert item["content"] == "内容ABC"
        assert item["contact"] == "admin@org.mil"  # user_email → contact
        assert item["username"] == "admin"          # user_name → username
        assert item["status"] == "open"
        assert item["created_at"] is not None

    def test_custom_pagination_page2(self, app, c):
        """page=2, page_size=5"""
        all_items = [_make_mock_fb(id=i) for i in range(1, 11)]
        mock_db = _make_mock_db(items=all_items[5:], total=10)
        _setup_db_override(app, mock_db)
        _setup_admin_override(app)

        resp = c.get("/api/v1/feedback?page=2&page_size=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["page"] == 2
        assert data["data"]["page_size"] == 5
        assert data["data"]["total"] == 10

    def test_page_zero(self, app, c):
        """page=0 — offset 为负，FastAPI 不拦截，SQLAlchemy 处理"""
        mock_db = _make_mock_db(items=[], total=0)
        _setup_db_override(app, mock_db)
        _setup_admin_override(app)

        resp = c.get("/api/v1/feedback?page=0&page_size=20")
        assert resp.status_code == 200

    # ── type 过滤 ──

    def test_filter_by_type_bug(self, app, c):
        """type=bug 过滤"""
        items = [_make_mock_fb(id=1, category="bug")]
        mock_db = _make_mock_db(items=items, total=1)
        _setup_db_override(app, mock_db)
        _setup_admin_override(app)

        resp = c.get("/api/v1/feedback?type=bug")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"][0]["type"] == "bug"

    def test_filter_by_type_suggestion(self, app, c):
        """type=suggestion 过滤"""
        items = [_make_mock_fb(id=2, category="suggestion")]
        mock_db = _make_mock_db(items=items, total=1)
        _setup_db_override(app, mock_db)
        _setup_admin_override(app)

        resp = c.get("/api/v1/feedback?type=suggestion")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"][0]["type"] == "suggestion"

    def test_filter_by_type_other(self, app, c):
        """type=other 过滤"""
        items = [_make_mock_fb(id=3, category="other")]
        mock_db = _make_mock_db(items=items, total=1)
        _setup_db_override(app, mock_db)
        _setup_admin_override(app)

        resp = c.get("/api/v1/feedback?type=other")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"][0]["type"] == "other"

    def test_type_all_skips_filter(self, app, c):
        """type=all 时不应用 filter（查询全部）"""
        items = [_make_mock_fb(id=1, category="bug"),
                 _make_mock_fb(id=2, category="suggestion")]
        mock_db = _make_mock_db(items=items, total=2)
        _setup_db_override(app, mock_db)
        _setup_admin_override(app)

        resp = c.get("/api/v1/feedback?type=all")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 2

    def test_type_not_provided(self, app, c):
        """不传 type 参数 — type=None → 不应用 filter"""
        items = [_make_mock_fb(id=1)]
        mock_db = _make_mock_db(items=items, total=1)
        _setup_db_override(app, mock_db)
        _setup_admin_override(app)

        resp = c.get("/api/v1/feedback")
        assert resp.status_code == 200

    def test_type_empty_string(self, app, c):
        """type='' — falsy → 跳过过滤"""
        items = [_make_mock_fb(id=1)]
        mock_db = _make_mock_db(items=items, total=1)
        _setup_db_override(app, mock_db)
        _setup_admin_override(app)

        resp = c.get("/api/v1/feedback?type=")
        assert resp.status_code == 200

    # ── 空列表 ──

    def test_empty_list(self, app, c):
        """无反馈记录时返回空列表"""
        mock_db = _make_mock_db(items=[], total=0)
        _setup_db_override(app, mock_db)
        _setup_admin_override(app)

        resp = c.get("/api/v1/feedback")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 0
        assert data["data"]["items"] == []

    def test_null_created_at(self, app, c):
        """created_at 为 None 时不崩溃（isoformat 调用被跳过）"""
        fb = _make_mock_fb(id=1, created_at=None)
        mock_db = _make_mock_db(items=[fb], total=1)
        _setup_db_override(app, mock_db)
        _setup_admin_override(app)

        resp = c.get("/api/v1/feedback")
        assert resp.status_code == 200
        assert resp.json()["data"]["items"][0]["created_at"] is None

    # ── 认证 ──

    def test_without_auth_returns_401(self, app, c):
        """未认证访问 — get_current_user 未被覆盖 → 触发真实 JWT 检查 → 401"""
        mock_db = _make_mock_db(items=[], total=0)
        _setup_db_override(app, mock_db)

        resp = c.get("/api/v1/feedback")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════════════
# POST /api/v1/feedback — 提交反馈
# ══════════════════════════════════════════════════════════════════════

class TestSubmitFeedback:
    """submit_feedback 端点测试"""

    # ── 成功提交 ──

    def test_full_fields_bug(self, app, c):
        """提交完整字段：type=bug + content + contact"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={
            "type": "bug",
            "content": "页面加载缓慢",
            "contact": "user@example.com",
        })
        assert resp.status_code == 200
        # 端点返回 success_response 信封，断言关键字段而非精确相等
        body = resp.json()
        assert body["success"] is True
        assert body["message"] == "感谢您的反馈"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_full_fields_suggestion(self, app, c):
        """提交 type=suggestion"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={
            "type": "suggestion",
            "content": "建议新增导出功能",
            "contact": "dev@org.mil",
        })
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.category == "suggestion"

    def test_full_fields_other(self, app, c):
        """提交 type=other"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={
            "type": "other",
            "content": "其他方面的意见",
        })
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.category == "other"

    def test_minimal_feedback(self, app, c):
        """仅提交 content — 其余使用默认值"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={
            "content": "一个简单的建议",
        })
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.category == "other"
        assert created.content == "一个简单的建议"
        assert created.priority == "medium"
        assert created.status == "open"
        assert created.source == "web"
        assert created.user_name is None
        assert created.user_email is None

    # ── 创建的 Feedback 对象字段验证 ──

    def test_created_feedback_field_by_field(self, app, c):
        """逐字段验证创建的 Feedback 对象"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={
            "type": "bug",
            "content": "精确验证",
            "contact": "tester@mil.cn",
        })
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.category == "bug"
        assert created.content == "精确验证"
        assert created.priority == "medium"
        assert created.status == "open"
        assert created.source == "web"
        assert created.user_email == "tester@mil.cn"

    # ── type 规范化 ──

    def test_type_uppercase_normalized(self, app, c):
        """大写 BUG → lower() → 'bug' → 匹配 VALID_TYPES"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={
            "type": "BUG",
            "content": "大写类型",
        })
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.category == "bug"

    def test_type_mixed_case_normalized(self, app, c):
        """Suggestion → lower() → 'suggestion'"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={
            "type": "Suggestion",
            "content": "混合大小写",
        })
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.category == "suggestion"

    def test_invalid_type_falls_back_to_other(self, app, c):
        """非法 type 值 → 回退为 'other'"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        for bad_type in ["invalid", "feature_request", "complaint", "123"]:
            mock_db.reset_mock()
            resp = c.post("/api/v1/feedback", json={
                "type": bad_type,
                "content": "测试非法类型",
            })
            assert resp.status_code == 200
            created = mock_db.add.call_args[0][0]
            assert created.category == "other", f"type={bad_type!r} 应回退为 other"

    def test_type_none_defaults_other(self, app, c):
        """不传 type 字段 — Pydantic 默认 'other'"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={"content": "无类型"})
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.category == "other"

    def test_type_null_json(self, app, c):
        """JSON 中 type 显式为 null — Pydantic schema type:str 不允许 None → 422"""
        resp = c.post("/api/v1/feedback", json={
            "type": None,
            "content": "null type",
        })
        assert resp.status_code == 422

    # ── content 内容校验 ──

    def test_empty_content_400(self, app, c):
        """content='' → 400"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={"content": ""})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "反馈内容不能为空"
        mock_db.add.assert_not_called()

    def test_whitespace_content_400(self, app, c):
        """content 仅空白 → 400"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        for ws in ["   ", "\t\n", " \t \n   "]:
            mock_db.reset_mock()
            resp = c.post("/api/v1/feedback", json={"content": ws})
            assert resp.status_code == 400, f"content={ws!r} 应返回 400"
            mock_db.add.assert_not_called()

    def test_blank_content_combined(self, app, c):
        """多类型空白组合 → 400"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={
            "content": "  \t\n\r  ",
        })
        assert resp.status_code == 400

    def test_missing_content_422(self, app, c):
        """JSON 中缺少 content 字段 → Pydantic 校验 → 422"""
        resp = c.post("/api/v1/feedback", json={})
        assert resp.status_code == 422

    def test_strips_content_whitespace(self, app, c):
        """content 前后空白被 strip"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={
            "content": "  前后都有空格  ",
        })
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.content == "前后都有空格"

    def test_content_with_newlines(self, app, c):
        """content 含换行符（多行文本）"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        multiline = "第一行\n第二行\n第三行"
        resp = c.post("/api/v1/feedback", json={"content": multiline})
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.content == multiline

    # ── contact 处理 ──

    def test_contact_empty_string_None(self, app, c):
        """contact='' → ('' or '').strip()='' → or None → None"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={
            "content": "测试",
            "contact": "",
        })
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.user_email is None

    def test_contact_whitespace_None(self, app, c):
        """contact 仅空白 → strip()='' → None"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={
            "content": "测试",
            "contact": "   ",
        })
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.user_email is None

    def test_contact_no_field(self, app, c):
        """不传 contact → Pydantic 默认 None → user_email is None"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={"content": "测试"})
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.user_email is None

    def test_contact_null_json(self, app, c):
        """contact 为 null → (None or '').strip()='' → None"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={
            "content": "测试",
            "contact": None,
        })
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.user_email is None

    # ── DB 异常 ──

    def test_db_add_fails_500(self, app, c):
        """db.add() 抛异常 → rollback + 500"""
        mock_db = _make_mock_db()
        mock_db.add.side_effect = RuntimeError("无法写入")
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={"content": "触发 DB 写入错误"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "保存反馈失败"
        mock_db.rollback.assert_called_once()

    def test_db_commit_fails_500(self, app, c):
        """db.commit() 抛异常 → rollback + 500"""
        mock_db = _make_mock_db()
        mock_db.commit.side_effect = RuntimeError("无法提交")
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={"content": "触发 DB 提交错误"})
        assert resp.status_code == 500
        # safe_commit（app/core/transaction.py）在 commit 失败时先自行 rollback
        # 并重新抛异常；端点 except 块（app/api/v1/feedback.py）再 rollback 一次
        # （对已回滚的 session 是无害 no-op），因此共调用 2 次。
        assert mock_db.rollback.call_count == 2

    def test_db_refresh_fails_500(self, app, c):
        """db.refresh() 抛异常 → rollback + 500"""
        mock_db = _make_mock_db()
        mock_db.refresh.side_effect = RuntimeError("无法刷新")
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={"content": "测试"})
        assert resp.status_code == 500
        mock_db.rollback.assert_called_once()

    # ── Authorization header 解析 ──

    def test_no_authorization_header(self, app, c):
        """不携带 Authorization header → user_name=None"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={"content": "匿名反馈"})
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.user_name is None

    def test_empty_authorization_header(self, app, c):
        """Authorization: '' → falsy → user_name=None"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback",
            json={"content": "空头反馈"},
            headers={"Authorization": ""},
        )
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.user_name is None

    def test_non_bearer_authorization(self, app, c):
        """Authorization: Basic ... → 非 Bearer → user_name=None"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback",
            json={"content": "Basic 认证"},
            headers={"Authorization": "Basic YWRtaW46cGFzcw=="},
        )
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.user_name is None

    def test_with_bearer_token_username(self, app, c):
        """Bearer token → _get_user_from_token 返回 username"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        with patch("app.api.v1.feedback._get_user_from_token",
                   new_callable=AsyncMock) as mock_gu:
            mock_gu.return_value = "token_user"

            resp = c.post("/api/v1/feedback",
                json={"content": "带用户token"},
                headers={"Authorization": "Bearer valid.jwt.token"},
            )
            assert resp.status_code == 200
            created = mock_db.add.call_args[0][0]
            assert created.user_name == "token_user"

    def test_with_bearer_token_none(self, app, c):
        """Bearer token → _get_user_from_token 返回 None → user_name=None"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        with patch("app.api.v1.feedback._get_user_from_token",
                   new_callable=AsyncMock) as mock_gu:
            mock_gu.return_value = None

            resp = c.post("/api/v1/feedback",
                json={"content": "token 无效"},
                headers={"Authorization": "Bearer invalid.token"},
            )
            assert resp.status_code == 200
            created = mock_db.add.call_args[0][0]
            assert created.user_name is None

    # ── 边界条件 ──

    def test_very_long_content(self, app, c):
        """R28 §3：content 上限 5000 字，超限拒绝（匿名可写端点的存储放大面）"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={"content": "长" * 10000})
        assert resp.status_code == 422
        mock_db.add.assert_not_called()

    def test_content_at_max_length_boundary(self, app, c):
        """恰好 5000 字（上限）应被接受"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        resp = c.post("/api/v1/feedback", json={"content": "长" * 5000})
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert len(created.content) == 5000

    def test_special_characters_content(self, app, c):
        """content 含中文标点、emoji、HTML 等特殊字符"""
        mock_db = _make_mock_db()
        _setup_db_override(app, mock_db)

        special = "测试 <script>alert('xss')</script> & ♥"
        resp = c.post("/api/v1/feedback", json={"content": special})
        assert resp.status_code == 200
        created = mock_db.add.call_args[0][0]
        assert created.content == special

    def test_invalid_json_body(self, app, c):
        """请求体不是有效 JSON → FastAPI Pydantic 解析失败 → 422"""
        resp = c.post("/api/v1/feedback",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════
# _get_user_from_token 内部辅助函数测试
# ══════════════════════════════════════════════════════════════════════

class TestGetUserFromToken:
    """_get_user_from_token 函数测试"""

    # ── 快捷返回 None 的分支 ──

    @pytest.mark.anyio
    async def test_auth_none(self):
        """authorization=None → 立即返回 None"""
        from app.api.v1.feedback import _get_user_from_token
        result = await _get_user_from_token(None)
        assert result is None

    @pytest.mark.anyio
    async def test_auth_empty_string(self):
        """authorization='' → falsy → 返回 None"""
        from app.api.v1.feedback import _get_user_from_token
        result = await _get_user_from_token("")
        assert result is None

    @pytest.mark.anyio
    async def test_auth_non_bearer(self):
        """authorization='Basic xyz' → 非 Bearer 前缀 → 返回 None"""
        from app.api.v1.feedback import _get_user_from_token
        result = await _get_user_from_token("Basic YWJjZA==")
        assert result is None

    @pytest.mark.anyio
    async def test_auth_bearer_prefix_only(self):
        """authorization='Bearer ' → token 为空字符串 → verify_token('',...) 被调用"""
        from app.api.v1.feedback import _get_user_from_token

        with patch("app.api.v1.auth.verify_token", new_callable=AsyncMock, create=True) as mock_vt:
            mock_vt.return_value = None
            result = await _get_user_from_token("Bearer ")
            assert result is None
            mock_vt.assert_called_once_with("", "access_token")

    # ── verify_token 返回有效信息 ──

    @pytest.mark.anyio
    async def test_returns_username(self):
        """verify_token 返回 dict 含 username → 返回 username"""
        from app.api.v1.feedback import _get_user_from_token

        with patch("app.api.v1.auth.verify_token", new_callable=AsyncMock, create=True) as mock_vt:
            mock_vt.return_value = {"username": "admin", "id": "42"}
            result = await _get_user_from_token("Bearer valid.token.here")
            assert result == "admin"
            mock_vt.assert_called_once_with("valid.token.here", "access_token")

    @pytest.mark.anyio
    async def test_returns_id_fallback(self):
        """verify_token 返回 dict 无 username → 回退返回 id"""
        from app.api.v1.feedback import _get_user_from_token

        with patch("app.api.v1.auth.verify_token", new_callable=AsyncMock, create=True) as mock_vt:
            mock_vt.return_value = {"id": "99"}
            result = await _get_user_from_token("Bearer only.id.token")
            assert result == "99"

    @pytest.mark.anyio
    async def test_returns_username_over_id(self):
        """username 优先于 id（两者都存在时返回 username）"""
        from app.api.v1.feedback import _get_user_from_token

        with patch("app.api.v1.auth.verify_token", new_callable=AsyncMock, create=True) as mock_vt:
            mock_vt.return_value = {"username": "张三", "id": "100"}
            result = await _get_user_from_token("Bearer both.token")
            assert result == "张三"

    @pytest.mark.anyio
    async def test_token_info_none(self):
        """verify_token 返回 None → 返回 None"""
        from app.api.v1.feedback import _get_user_from_token

        with patch("app.api.v1.auth.verify_token", new_callable=AsyncMock, create=True) as mock_vt:
            mock_vt.return_value = None
            result = await _get_user_from_token("Bearer expired.token")
            assert result is None

    @pytest.mark.anyio
    async def test_token_info_empty_dict(self):
        """verify_token 返回 {} — 空字典 falsy → if info: 不进入 → 返回 None"""
        from app.api.v1.feedback import _get_user_from_token

        with patch("app.api.v1.auth.verify_token", new_callable=AsyncMock, create=True) as mock_vt:
            mock_vt.return_value = {}
            result = await _get_user_from_token("Bearer weird.token")
            assert result is None

    @pytest.mark.anyio
    async def test_token_info_surprising_dict(self):
        """verify_token 返回不含 username/id 的 dict → 返回 ''（id fallback 的 default）"""
        from app.api.v1.feedback import _get_user_from_token

        with patch("app.api.v1.auth.verify_token", new_callable=AsyncMock, create=True) as mock_vt:
            mock_vt.return_value = {"role": "admin"}
            result = await _get_user_from_token("Bearer strange.token")
            assert result == ""

    # ── verify_token 抛异常 ──

    @pytest.mark.anyio
    async def test_verify_token_raises(self):
        """verify_token 抛异常 → try/except 捕获 → 返回 None（不崩溃）"""
        from app.api.v1.feedback import _get_user_from_token

        with patch("app.api.v1.auth.verify_token", new_callable=AsyncMock, create=True) as mock_vt:
            mock_vt.side_effect = RuntimeError("JWT 解码失败")
            result = await _get_user_from_token("Bearer malformed.token")
            assert result is None
            mock_vt.assert_called_once()

    @pytest.mark.anyio
    async def test_verify_token_raises_import_error(self):
        """模拟从 app.api.v1.auth 导入 verify_token 失败 → try/except → None"""
        # 构造一个场景：verify_token 在 auth 模块中不存在
        # _get_user_from_token 内部有 try/except Exception，会捕获 ImportError
        import app.api.v1.auth as auth_pkg

        stored = None
        if hasattr(auth_pkg, "verify_token"):
            stored = auth_pkg.verify_token
            del auth_pkg.verify_token

        try:
            from app.api.v1.feedback import _get_user_from_token
            result = await _get_user_from_token("Bearer some-token")
            # import verify_token 失败 → except 捕获 → 返回 None
            assert result is None
        finally:
            if stored is not None:
                auth_pkg.verify_token = stored
