"""应用启动钩子包（架构评估 B3 · 2026-09-12）。

历史问题：app/main.py 987 行"什么都懂一点"——lifespan 编排 + 14 个启动/
停止钩子 + 数据库初始化 + 路由全部堆在入口模块，任一钩子异常都可能影响
启动韧性，入口文件成为上帝模块。

本包按职责拆分启动钩子，每个函数自带 try/except 兜底与日志（与原实现
逐字一致，仅挪动位置）：

- :mod:`app.startup.recovery`     —— token 黑名单恢复 / 中断导出任务恢复
- :mod:`app.startup.seed`         —— 默认管理员种子 / 锁定账户解锁
- :mod:`app.startup.environment`  —— 依赖包检查 / 版本变更记录 / 文件完整性
- :mod:`app.startup.monitors`     —— 资源/数据库健康监控 + 各类后台调度器

app/main.py 只保留 **编排清单**（lifespan）与数据库初始化集群
（``_init_database_tables`` / Alembic / 自动补列——与测试、``/health`` 的
``_migration_status`` 强耦合，见 tests/unit/test_main_app.py）。
main 顶部以同名别名 re-export，保证既有 ``from app.main import _xxx`` 与
``patch("app.main._xxx")`` 用法完全兼容。
"""
