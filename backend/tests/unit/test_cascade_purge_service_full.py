"""app.services.cascade_purge_service.CascadePurgeService 覆盖补充测试（真实 SQLite）。

覆盖 _load_graph / _count / _delete / _count_deep / _delete_deep /
preview（直接 + 二级依赖 + 零引用）/ purge（成功级联 + 记录不存在回滚）。

链式关系：supported_villages ← projects(village_id) ← funds(project_id)。
"""
import pytest
from unittest.mock import MagicMock

from app.models.fund import Fund
from app.models.project import Project
from app.models.supported_village import SupportedVillage
from app.services.cascade_purge_service import CascadePurgeService


@pytest.fixture
def svc(real_db_session):
    return CascadePurgeService(real_db_session)


def _mkchain(db, with_children=True):
    v = SupportedVillage(village_name="级联村", is_active=False)
    db.add(v)
    db.commit()
    db.refresh(v)
    if with_children:
        p = Project(name="级联项目", village_id=v.id)
        db.add(p)
        db.commit()
        db.refresh(p)
        f = Fund(name="级联经费", project_id=p.id)  # village_id 留空 → 仅二级依赖
        db.add(f)
        db.commit()
    return v


class TestLoadGraph:
    def test_finds_direct_refs(self, svc):
        refs = svc._load_graph("supported_villages")
        tables = {t for t, _ in refs}
        assert "projects" in tables

    def test_root_table_excluded(self, svc):
        refs = svc._load_graph("supported_villages")
        assert all(t != "supported_villages" for t, _ in refs)


class TestPreview:
    def test_direct_and_deep_counts(self, svc, real_db_session):
        v = _mkchain(real_db_session)
        out = svc.preview("supported_villages", v.id)
        assert out["root_table"] == "supported_villages"
        assert out["row_id"] == v.id
        assert "projects" in out["details"]
        assert any("via projects" in k for k in out["details"])
        assert out["total_references"] >= 2

    def test_no_children_zero(self, svc, real_db_session):
        v = _mkchain(real_db_session, with_children=False)
        out = svc.preview("supported_villages", v.id)
        assert out["total_references"] == 0
        assert out["details"] == {}


class TestPurge:
    def test_purge_deletes_chain(self, svc, real_db_session):
        v = _mkchain(real_db_session)
        vid = v.id
        stats = svc.purge("supported_villages", vid)
        assert stats["success"] is True
        assert stats["deleted_records"] >= 3
        assert real_db_session.get(SupportedVillage, vid) is None

    def test_purge_missing_rolls_back(self, svc, real_db_session):
        out = svc.purge("supported_villages", 999999)
        assert out["success"] is False
        assert out["message"] == "记录不存在"

    def test_purge_leaf_only(self, svc, real_db_session):
        v = _mkchain(real_db_session, with_children=False)
        stats = svc.purge("supported_villages", v.id)
        assert stats["success"] is True
        assert stats["deleted_records"] == 1


class TestCycleGuard:
    """合成 root↔child 环：验证 deep 图中出现 root_table 时被 continue 跳过。

    当前 schema 无互相外键对（已核验），故用合成图直接驱动
    `if t2 == root_table: continue` 防护分支。
    """

    def test_preview_skips_root_in_deep_graph(self, svc):
        svc._load_graph = MagicMock(side_effect=[
            [("child_tbl", "child_id")],        # root 的直接子表
            [("supported_villages", "sv_id")],  # child 的子图含 root → continue
        ])
        svc._count = MagicMock(return_value=1)
        out = svc.preview("supported_villages", 1)
        assert "child_tbl" in out["details"]
        assert "supported_villages" not in out["details"]

    def test_purge_skips_root_in_deep_graph(self, svc):
        svc._load_graph = MagicMock(side_effect=[
            [("child_tbl", "child_id")],        # deep 循环的 root 子表
            [("supported_villages", "sv_id")],  # 含 root → continue
            [("child_tbl", "child_id")],        # 直接删除循环的 root 子表
        ])
        svc._delete_deep = MagicMock(return_value=1)
        svc._delete = MagicMock(return_value=1)
        # 主行不存在 → rowcount 0 → 回滚；deep continue 分支已在之前执行
        out = svc.purge("supported_villages", 999999)
        assert out["success"] is False
        svc._delete_deep.assert_not_called()  # root 被 continue，未进入孙表删除
