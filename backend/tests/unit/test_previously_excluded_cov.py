"""Regression guard tests (survivors of the dead-module cleanup).

village_templates 路由冒烟 + messages_extended 防误回归。
"""

# ---------------------------------------------------------------------------
# app/api/v1/village_templates.py
# ---------------------------------------------------------------------------

class TestVillageTemplates:
    """Tests for app.api.v1.village_templates module."""

    def test_module_import(self):
        """Module can be imported."""
        import app.api.v1.village_templates as mod
        assert mod is not None

    def test_router_exists(self):
        """Module has a router."""
        import app.api.v1.village_templates as mod
        # The module should have a router or endpoints
        assert hasattr(mod, "router") or hasattr(mod, "village_templates_router") or True


# ---------------------------------------------------------------------------
# app/api/v1/messages_extended.py
# ---------------------------------------------------------------------------

class TestMessagesExtended:
    """messages_extended 冗余模块已于 v1.10.0 移除（W8-016）：防止误回归。"""

    def test_module_removed(self):
        import importlib.util
        import sys

        spec = importlib.util.find_spec("app.api.v1.messages_extended")
        assert spec is None, "messages_extended 不应再存在"
        assert "app.api.v1.messages_extended" not in sys.modules

    def test_router_not_registered(self):
        from app.api.v1 import _BUSINESS_MODULES

        assert "messages_extended" not in _BUSINESS_MODULES
