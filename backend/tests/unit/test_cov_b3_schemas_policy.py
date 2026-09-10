"""b3 攻坚：覆盖 app.schemas.policy 的 PolicyResponse 兼容属性"""
from datetime import datetime

from app.schemas.policy import PolicyResponse


class TestPolicyResponseCompatProperties:
    def _make(self):
        return PolicyResponse(
            id=1,
            title="政策标题",
            content="政策内容",
            level="central",
            issuing_authority="中央军委",
            code="军发〔2024〕1号",
            issue_date=datetime(2024, 1, 15),
            file_path="/files/policy1.pdf",
        )

    def test_organization_level(self):
        assert self._make().organization_level == "central"

    def test_department(self):
        assert self._make().department == "中央军委"

    def test_document_number(self):
        assert self._make().document_number == "军发〔2024〕1号"

    def test_publish_date(self):
        assert self._make().publish_date == datetime(2024, 1, 15)

    def test_defaults_none(self):
        resp = PolicyResponse(id=2, title="t", content="c")
        assert resp.organization_level is None
        assert resp.department is None
        assert resp.document_number is None
        assert resp.publish_date is None
