"""R29 回归锁定：Alembic 迁移图必须**只有一个 head**。

安装包验收实测的启动级故障：新增迁移时把 `down_revision` 接到了
`contract_attachments_001`，而该版本已不是 head（`policy_attachments_001` 接在它后面），
于是迁移图分叉成两个 head →

    alembic upgrade head → CommandError: Multiple head revisions are present
    （crash.log: MultipleHeads: data_report_type_001, policy_attachments_001）
    ERROR: Application startup failed. Exiting.

`main.py` 启动时先跑 `alembic upgrade head`，失败即**启动失败**（打包实例直接起不来），
自动补列兜底救不回来 —— 这是发布级阻断，必须有门禁。

新增迁移前请先 `alembic heads` 确认唯一 head，并把它作为 `down_revision`。
"""

from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
VERSIONS = BACKEND / "alembic" / "versions"


def _heads() -> list:
    """用 Alembic 官方 API 取 heads（与 main.py 的 `alembic upgrade head` 同源）。

    不要自己正则解析迁移文件 —— 本仓存在 `down_revision` 为多行/变量的写法，
    手写解析会把非 head 的版本误判成 head（首版即踩到：手写解析报 4 个 head，
    而 `alembic heads` 实际只有 1 个）。
    """
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory

    ini = BACKEND.parent / "alembic.ini"
    if not ini.exists():
        ini = BACKEND / "alembic.ini"
    cfg = AlembicConfig(str(ini))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return sorted(ScriptDirectory.from_config(cfg).get_heads())


class TestAlembicSingleHead:
    def test_exactly_one_head(self):
        heads = _heads()
        assert len(heads) == 1, (
            f"迁移图有 {len(heads)} 个 head：{heads} —— `alembic upgrade head` 会抛 "
            "MultipleHeads 导致应用启动失败。请把新迁移的 down_revision 指向当前唯一 head。"
        )

    def test_data_report_type_chains_after_policy_attachments(self):
        """data_report_type_001 必须接在 policy_attachments_001 之后（线性链）。"""
        import re

        text = (VERSIONS / "data_report_type_001.py").read_text(encoding="utf-8")
        m = re.search(r"^down_revision\s*=\s*['\"]([^'\"]+)['\"]", text, re.M)
        assert m and m.group(1) == "policy_attachments_001"

    def test_guard_detects_forked_graph(self, tmp_path, monkeypatch):
        """守卫自身有效性：人为造一个分叉图，必须判出多 head。"""
        import shutil

        fake = tmp_path / "alembic"
        shutil.copytree(VERSIONS.parent, fake)
        (fake / "versions" / "zz_fork_test_001.py").write_text(
            "revision = 'zz_fork_test_001'\n"
            "down_revision = 'subscription_last_sent_001'\n"
            "def upgrade():\n    pass\n"
            "def downgrade():\n    pass\n",
            encoding="utf-8",
        )

        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory

        ini = BACKEND.parent / "alembic.ini"
        cfg = AlembicConfig(str(ini if ini.exists() else BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(fake))
        heads = ScriptDirectory.from_config(cfg).get_heads()
        assert len(heads) > 1, "分叉图必被判出多 head（否则守卫失效）"
