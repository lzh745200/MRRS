"""覆盖率攻坚: app/services/project/__init__.py 缺口行 17-19（包初始化导入与 __all__）."""


class TestProjectPackageInit:
    def test_package_imports_effectiveness_service(self):
        """导入 app.services.project 执行包初始化（第 17-19 行）.

        W1 不变量 8: 不使用 importlib.reload——import 本身即执行包 __init__,
        reload 会就地重建命名空间, 有类对象分裂风险且对覆盖无增益。
        """
        import app.services.project as project_pkg

        assert project_pkg.EffectivenessService is not None
        assert "EffectivenessService" in project_pkg.__all__
