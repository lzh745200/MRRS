"""
Tests for help.py — static help articles API (no auth required, no DB needed).
"""



BASE = "/api/v1/system/help"


class TestGetCategories:
    def test_returns_categories(self, auth_client):
        resp = auth_client.get(f"{BASE}/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        cats = data["data"]["categories"]
        assert len(cats) >= 5
        keys = {c["key"] for c in cats}
        assert "quick_start" in keys
        assert "faq" in keys
        for c in cats:
            assert c["count"] >= 1


class TestGetArticles:
    def test_all(self, auth_client):
        resp = auth_client.get(f"{BASE}/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["total"] >= 6
        assert len(data["data"]["items"]) <= 30

    def test_filter_by_category(self, auth_client):
        resp = auth_client.get(f"{BASE}/articles?category=faq")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert all(a["category"] == "faq" for a in items)

    def test_search_by_keyword(self, auth_client):
        resp = auth_client.get(f"{BASE}/articles?keyword=资金")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 1

    def test_pagination(self, auth_client):
        resp = auth_client.get(f"{BASE}/articles?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) == 2
        assert data["total"] >= 6


class TestGetArticleDetail:
    def test_found(self, auth_client):
        resp = auth_client.get(f"{BASE}/articles/1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == 1
        assert data["title"] == "系统快速入门指南"

    def test_not_found(self, auth_client):
        resp = auth_client.get(f"{BASE}/articles/999")
        assert resp.status_code == 404


class TestSearch:
    def test_empty_query_returns_empty(self, auth_client):
        resp = auth_client.get(f"{BASE}/search?q=")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 0
        assert data["items"] == []

    def test_search_by_title(self, auth_client):
        resp = auth_client.get(f"{BASE}/search?q=资金管理")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 1
        assert items[0]["relevance_score"] >= 5

    def test_search_by_content(self, auth_client):
        resp = auth_client.get(f"{BASE}/search?q=离线地图")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 1

    def test_search_by_tag(self, auth_client):
        resp = auth_client.get(f"{BASE}/search?q=架构")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 1

    def test_limit(self, auth_client):
        resp = auth_client.get(f"{BASE}/search?q=管理&limit=1")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 1

    def test_no_match(self, auth_client):
        resp = auth_client.get(f"{BASE}/search?q=zzzznonexistent")
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] == 0


class TestHelpContentConsistency:
    def test_no_registration_guidance_in_help_articles(self):
        """系统已不提供注册功能，帮助中心不得再出现注册流程/入口文案。"""
        from app.api.v1.system.help import _HELP_ARTICLES

        for article in _HELP_ARTICLES:
            text = " ".join([
                article.get("title", ""),
                article.get("content", ""),
                " ".join(article.get("tags", [])),
            ])
            assert "注册" not in text, f"帮助文章仍含注册说明: {article['id']} {article['title']}"


class TestSystemInfo:
    def test_returns_info(self, auth_client):
        resp = auth_client.get(f"{BASE}/system-info")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["short_name"] == "帮扶振兴"
        assert len(data["features"]) >= 5
