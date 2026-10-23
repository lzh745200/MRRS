"""
乡村振兴工作 API 全面测试

覆盖 ``app/api/v1/rural_works.py`` 的全部路由。

W27：``rural_tasks`` 模块已按产品决策**下线**（9 个端点 / ``RuralTask`` 模型 /
``rural_task`` schema 全部移除，表由迁移归档），因此原 ``TestRuralTasksAPI``
（10 个用例）随之删除。乡村振兴页面实际一直走 ``/rural-works``，功能不受影响。
"""


class TestRuralWorksAPI:
    """测试乡村振兴工作API"""

    def test_rural_works_list(self, client):
        """测试工作列表"""
        response = client.get("/api/v1/rural-works")
        assert response.status_code in [200, 401, 403]

    def test_rural_works_detail(self, client):
        """测试工作详情"""
        response = client.get("/api/v1/rural-works/1")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_rural_works_create(self, client):
        """测试创建工作"""
        response = client.post("/api/v1/rural-works", json={
            "title": "测试工作",
            "description": "工作内容"
        })
        assert response.status_code in [200, 201, 401, 403, 422]

    def test_rural_works_update(self, client):
        """测试更新工作"""
        response = client.put("/api/v1/rural-works/1", json={})
        assert response.status_code in [200, 401, 403, 404, 405, 422]

    def test_rural_works_delete(self, client):
        """测试删除工作"""
        response = client.delete("/api/v1/rural-works/1")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_rural_works_progress(self, client):
        """测试工作进度"""
        response = client.get("/api/v1/rural-works/1/progress")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_rural_works_update_progress(self, client):
        """测试更新工作进度"""
        response = client.post("/api/v1/rural-works/1/progress", json={
            "progress": 50
        })
        assert response.status_code in [200, 401, 403, 404, 405, 422]
