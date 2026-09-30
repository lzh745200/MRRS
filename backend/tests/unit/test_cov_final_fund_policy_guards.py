"""覆盖补全：fund_budgets 备注列附件兼容读取 / funds 状态机红线 / policy 附件下载守卫。"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.fund_budgets import (
    _BUDGET_ATTACHMENT_KEY,
    _decode_remarks,
    _filter_attachment_entries,
)
from app.api.v1.funds import FundUpdate, update_fund
from app.api.v1.policy import download_policy_file


# ---------------------------------------------------------------------------
# 公共 mock
# ---------------------------------------------------------------------------

def _chained_db():
    """query/filter/order_by/... 全部返回自身的链式 MagicMock 会话。"""
    db = MagicMock(name="db")
    for name in ("query", "filter", "order_by", "offset", "limit", "options", "join"):
        getattr(db, name).return_value = db
    return db


def _operator_user():
    return SimpleNamespace(
        id=1, username="admin", full_name="管理员", role="admin",
        is_superuser=True, is_active=True, organization_id=1,
    )


# ===========================================================================
# app/api/v1/fund_budgets.py:531
# ===========================================================================

class TestFilterAttachmentEntriesNonList:
    """_filter_attachment_entries 对非列表入参 fail-closed 返回空列表（line 531）。

    该函数读取的是用户可编辑的 remarks 列：历史脏数据 / 手工改库 / 旧版本
    "整段 JSON 覆盖备注" 都可能留下非列表形态，直接迭代会抛 TypeError（500）。
    """

    @pytest.mark.parametrize(
        "dirty",
        [None, "", "url=http://evil/x", 123, 4.5, True, {"url": "http://x"}, ("http://x",)],
    )
    def test_non_list_value_returns_empty(self, dirty):
        assert _filter_attachment_entries(dirty) == []

    def test_list_still_filters_dict_entries_with_url(self):
        """对照组：合法列表只保留形如 {"url": ...} 的字典条目。"""
        rows = [
            {"url": "http://ok/1", "file_name": "a.pdf"},
            {"file_name": "no-url.pdf"},
            "http://bare-string",
            None,
            123,
        ]
        assert _filter_attachment_entries(rows) == [{"url": "http://ok/1", "file_name": "a.pdf"}]

    def test_envelope_with_non_list_payload_decodes_to_no_attachments(self):
        """保留键信封里塞了字符串（被篡改/脏数据）→ 附件为空，备注文本仍可读。"""
        raw = json.dumps({_BUDGET_ATTACHMENT_KEY: "not-a-list", "text": "正常备注"})
        decoded = _decode_remarks(raw)
        assert decoded["attachments"] == []
        assert decoded["text"] == "正常备注"


# ===========================================================================
# app/api/v1/funds.py:618-620
# ===========================================================================

class TestUpdateFundStatusGuard:
    """经费状态机红线：status 不得经通用更新接口写入（lines 618-620）。

    若放任 PUT /funds/{id} 写 status，创建人可绕过审批/附件/里程碑校验
    直接把经费推到 approved / allocated。
    """

    def test_changed_status_is_rejected_with_400(self):
        db = _chained_db()
        fund = SimpleNamespace(id=1, status="pending")
        with patch("app.api.v1.funds._get_fund_or_404", return_value=fund):
            with pytest.raises(HTTPException) as excinfo:
                update_fund(1, FundUpdate(status="approved"), _operator_user(), db)

        assert excinfo.value.status_code == 400
        assert "经费状态不能直接修改" in excinfo.value.detail
        # 必须在落库前拒绝：原记录状态不得被改写，也不得留下变更留痕
        assert fund.status == "pending"
        db.add.assert_not_called()
        db.commit.assert_not_called()

    def test_status_echoed_unchanged_is_ignored(self):
        """前端整表单回传原状态（status 等于当前值）不该报错，也不产生变更。"""
        db = _chained_db()
        fund = SimpleNamespace(id=1, status="pending")
        with patch("app.api.v1.funds._get_fund_or_404", return_value=fund):
            resp = update_fund(1, FundUpdate(status="pending"), _operator_user(), db)

        assert resp["code"] == 200
        assert resp["message"] == "更新成功"
        db.add.assert_not_called()

    def test_explicit_null_status_is_ignored(self):
        """显式传 null（清空语义）同样不得把 status 写成 NULL。"""
        db = _chained_db()
        fund = SimpleNamespace(id=1, status="planned")
        with patch("app.api.v1.funds._get_fund_or_404", return_value=fund):
            resp = update_fund(1, FundUpdate(status=None), _operator_user(), db)

        assert resp["code"] == 200
        assert fund.status == "planned"


# ===========================================================================
# app/api/v1/policy.py:1048
# ===========================================================================

class TestDownloadPolicyWithoutAttachment:
    """政策无附件（file_path 为空）→ 404，绝不进入 FileResponse（line 1048）。"""

    @pytest.mark.parametrize("empty_path", [None, ""])
    async def test_empty_file_path_returns_404(self, empty_path):
        db = _chained_db()
        db.first.return_value = SimpleNamespace(id=1, file_path=empty_path)

        with patch("app.api.v1.policy._resolve_safe_upload_path") as resolver:
            with pytest.raises(HTTPException) as excinfo:
                await download_policy_file(policy_id=1, current_user=_operator_user(), db=db)

        assert excinfo.value.status_code == 404
        assert excinfo.value.detail == "附件文件不存在"
        # 空路径不得进入路径解析（否则可能解析成上传根目录）
        resolver.assert_not_called()
        db.commit.assert_not_called()

    async def test_missing_policy_returns_404_first(self):
        """对照组：政策本身不存在时先撞 404（政策不存在），不会走到附件守卫。"""
        db = _chained_db()
        db.first.return_value = None

        with pytest.raises(HTTPException) as excinfo:
            await download_policy_file(policy_id=999, current_user=_operator_user(), db=db)

        assert excinfo.value.status_code == 404
        assert excinfo.value.detail == "政策不存在"
