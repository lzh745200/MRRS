"""审批驳回必填原因（问题15）回归测试

后端 /approval/tasks/{id}/reject 必须拒绝空 opinion（400），
防止绕过前端必填校验空原因驳回。
"""
import pytest


class TestRejectOpinionRequired:
    def test_reject_missing_opinion_400(self, auth_client):
        if auth_client is None:
            pytest.skip("client fixture unavailable")
        resp = auth_client.post("/api/v1/approval/tasks/1/reject", json={})
        assert resp.status_code == 400
        assert "驳回必须填写原因" in str(resp.json().get("detail", ""))

    def test_reject_blank_opinion_400(self, auth_client):
        if auth_client is None:
            pytest.skip("client fixture unavailable")
        resp = auth_client.post("/api/v1/approval/tasks/1/reject", json={"opinion": "   "})
        assert resp.status_code == 400

    def test_reject_with_opinion_passes_validation(self, auth_client):
        """填写原因后不再 400（任务不存在时为 403，说明已通过校验进入业务层）"""
        if auth_client is None:
            pytest.skip("client fixture unavailable")
        resp = auth_client.post(
            "/api/v1/approval/tasks/999999/reject", json={"opinion": "不符合要求"}
        )
        assert resp.status_code in (403, 404, 200)
        assert resp.status_code != 400
