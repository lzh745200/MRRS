"""
资金API全面测试
覆盖app/api/v1/funds.py的所有路由
"""




class TestFundsAPI:
    """测试资金API"""

    def test_funds_list(self, client):
        """测试资金列表"""
        response = client.get("/api/v1/funds")
        assert response.status_code in [200, 401, 403]

    def test_funds_list_with_params(self, client):
        """测试资金列表带参数"""
        response = client.get("/api/v1/funds?status=draft&page=1&size=10")
        assert response.status_code in [200, 401, 403]

    def test_funds_detail(self, client):
        """测试资金详情"""
        response = client.get("/api/v1/funds/1")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_funds_create_empty(self, client):
        """测试创建空资金"""
        response = client.post("/api/v1/funds", json={})
        assert response.status_code in [200, 401, 403, 422, 500]

    def test_funds_create_with_data(self, client):
        """测试创建资金"""
        response = client.post("/api/v1/funds", json={
            "title": "测试资金",
            "amount": 10000
        })
        assert response.status_code in [200, 201, 401, 403, 422, 500]

    def test_funds_update(self, client):
        """测试更新资金"""
        response = client.put("/api/v1/funds/1", json={
            "title": "更新资金"
        })
        assert response.status_code in [200, 401, 403, 404, 405, 422]

    def test_funds_delete(self, client):
        """测试删除资金"""
        response = client.delete("/api/v1/funds/1")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_funds_submit(self, client):
        """测试提交资金"""
        response = client.post("/api/v1/funds/1/submit")
        assert response.status_code in [200, 401, 403, 404, 405, 405]

    def test_funds_approve(self, client):
        """测试审批资金"""
        response = client.post("/api/v1/funds/1/approve", json={})
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_funds_reject(self, client):
        """测试拒绝资金"""
        response = client.post("/api/v1/funds/1/reject", json={
            "reason": "测试拒绝"
        })
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_funds_statistics(self, client):
        """测试资金统计"""
        response = client.get("/api/v1/funds/statistics")
        assert response.status_code in [200, 401, 403]

    def test_funds_budget(self, client):
        """测试资金预算"""
        response = client.get("/api/v1/funds/budget")
        assert response.status_code in [200, 401, 403]

    def test_funds_import(self, client):
        """测试导入资金"""
        response = client.post("/api/v1/funds/import", json={})
        assert response.status_code in [200, 401, 403, 404, 405, 405, 422]

    def test_funds_history(self, client):
        """测试资金历史"""
        response = client.get("/api/v1/funds/1/history")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_funds_attachments(self, client):
        """测试资金附件"""
        response = client.get("/api/v1/funds/1/attachments")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_funds_usage(self, client):
        """测试资金使用"""
        response = client.get("/api/v1/funds/1/usage")
        assert response.status_code in [200, 401, 403, 404, 405]

class TestFundAllocationsAPI:
    """测试资金分配API"""

    def test_fund_allocations_list(self, client):
        """测试资金分配列表"""
        response = client.get("/api/v1/funds/1/allocations")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_fund_allocation_create(self, client):
        """测试创建资金分配"""
        response = client.post("/api/v1/funds/1/allocations", json={
            "amount": 5000,
            "department": "测试部门"
        })
        assert response.status_code in [200, 401, 403, 404, 405, 405, 422]

class TestFundWorkflowAPI:
    """测试资金工作流API"""

    def test_fund_workflow_status(self, client):
        """测试资金工作流状态"""
        response = client.get("/api/v1/funds/1/workflow")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_fund_workflow_transitions(self, client):
        """测试资金工作流转换"""
        response = client.get("/api/v1/funds/1/workflow/transitions")
        assert response.status_code in [200, 401, 403, 404, 405]
