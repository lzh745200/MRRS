"""CascadePurgeService._delete_chain 根行锚定回归测试（真实 SQLite）。

背景（深审 #1 复审 / 系统全面排查报告 2026-10-14 H1）：
- `_descendant_chains` 产出的链是「由深到浅」，旧 `_delete_chain` 的
  - 最深跳生成 ``parent.id = :rid``（把根行主键拿去比对中间表主键 → 深层删不掉）；
  - 中间层生成 ``col NOT IN (SELECT parent_pk FROM parent)``（**不带根行限定** →
    会误删其它根行的悬挂关联数据）。
- 本文件用真实内存 SQLite（未开外键约束）构造「两条互不相干的完整子树 + 一条悬挂行」，
  证明删除 A 之后 B 的数据与悬挂行都**原样保留**，且 A 的每一层都被删除。

链式关系：supported_villages ← projects(village_id) ← funds(project_id) ← fund_transactions(fund_id)
（FundTransaction.village_id 也可直接引用根，构成"同表多路径"，一并覆盖。）
"""

import pytest
from datetime import date

from app.models.fund import Fund
from app.models.fund_budget import FundTransaction
from app.models.project import Project
from app.models.supported_village import SupportedVillage
from app.services.cascade_purge_service import CascadePurgeService

NON_EXISTENT_VILLAGE_ID = 987654321


@pytest.fixture
def svc(real_db_session):
    return CascadePurgeService(real_db_session)


def _mk_subtree(db, village_name: str) -> dict:
    """造一棵完整三层子树：村 → 项目 → 经费 → 明细，返回各层 id。"""
    v = SupportedVillage(village_name=village_name, is_active=False)
    db.add(v)
    db.flush()
    p = Project(name=f"{village_name}-项目", village_id=v.id, is_active=False)
    db.add(p)
    db.flush()
    f = Fund(name=f"{village_name}-经费", project_id=p.id, village_id=v.id, is_active=False)
    db.add(f)
    db.flush()
    t = FundTransaction(
        fund_id=f.id, project_id=p.id, village_id=v.id,
        amount=1, purpose=f"{village_name}-支出", transaction_date=date(2026, 1, 1),
    )
    db.add(t)
    db.flush()
    db.commit()
    return {"village": v.id, "project": p.id, "fund": f.id, "transaction": t.id}


class TestPurgeOnlyDeletesOwnSubtree:
    """核心不变量：删除 A 绝不能影响 B 的任何一行（旧实现会误删 B 的悬挂关联）。"""

    def test_purge_a_keeps_b_subtree_intact(self, svc, real_db_session):
        a = _mk_subtree(real_db_session, "甲村")
        b = _mk_subtree(real_db_session, "乙村")

        stats = svc.purge("supported_villages", a["village"])

        assert stats["success"] is True
        # A 的每一层都被删除（含最深一层明细）
        assert real_db_session.get(SupportedVillage, a["village"]) is None
        assert real_db_session.get(Project, a["project"]) is None
        assert real_db_session.get(Fund, a["fund"]) is None
        assert real_db_session.get(FundTransaction, a["transaction"]) is None
        # 统计里应体现三个关联层
        assert stats["deleted_records"] >= 4
        # B 的整棵子树原样保留（旧实现的 NOT IN 分支会把它删掉）
        assert real_db_session.get(SupportedVillage, b["village"]) is not None
        assert real_db_session.get(Project, b["project"]) is not None
        assert real_db_session.get(Fund, b["fund"]) is not None
        assert real_db_session.get(FundTransaction, b["transaction"]) is not None

    def test_purge_does_not_touch_dangling_rows(self, svc, real_db_session):
        """悬挂行（village_id 指向不存在的村）不属于任何根行，绝不能被顺带清理。"""
        a = _mk_subtree(real_db_session, "丙村")
        b = _mk_subtree(real_db_session, "丁村")
        dangling = Project(name="悬挂项目", village_id=NON_EXISTENT_VILLAGE_ID, is_active=False)
        real_db_session.add(dangling)
        real_db_session.commit()

        stats = svc.purge("supported_villages", a["village"])

        assert stats["success"] is True
        assert real_db_session.get(Project, dangling.id) is not None
        assert real_db_session.get(Project, b["project"]) is not None
        assert real_db_session.get(Fund, b["fund"]) is not None

    def test_purge_ignores_same_table_other_path(self, svc, real_db_session):
        """funds/fund_transactions 同时直接引用根表（village_id），
        多路径链不得重复删除或漏删。"""
        a = _mk_subtree(real_db_session, "戊村")
        b = _mk_subtree(real_db_session, "己村")

        stats = svc.purge("supported_villages", a["village"])

        assert stats["success"] is True
        assert real_db_session.get(Fund, a["fund"]) is None
        assert real_db_session.get(FundTransaction, a["transaction"]) is None
        assert real_db_session.get(Fund, b["fund"]) is not None
        assert real_db_session.get(FundTransaction, b["transaction"]) is not None


class TestDeleteChainContract:
    def test_empty_chain_is_noop(self, svc):
        assert svc._delete_chain([], 1) == 0

    def test_single_hop_anchors_root_row(self, svc, real_db_session):
        """单跳链：只删根行自己的直接子行。"""
        a = _mk_subtree(real_db_session, "庚村")
        b = _mk_subtree(real_db_session, "辛村")
        n = svc._delete_chain([("projects", "village_id", "supported_villages", "id")], a["village"])
        assert n == 1
        assert real_db_session.get(Project, a["project"]) is None
        assert real_db_session.get(Project, b["project"]) is not None

    def test_two_hop_deletes_deepest_first(self, svc, real_db_session):
        """两跳链：深层（经费）与浅层（项目）都要删，且都锚定根行。"""
        a = _mk_subtree(real_db_session, "壬村")
        b = _mk_subtree(real_db_session, "癸村")
        chain = [
            ("funds", "project_id", "projects", "id"),
            ("projects", "village_id", "supported_villages", "id"),
        ]
        n = svc._delete_chain(chain, a["village"])
        assert n == 2
        assert real_db_session.get(Fund, a["fund"]) is None
        assert real_db_session.get(Project, a["project"]) is None
        assert real_db_session.get(Fund, b["fund"]) is not None
        assert real_db_session.get(Project, b["project"]) is not None

    def test_three_hop_reaches_deepest_level(self, svc, real_db_session):
        """三跳链：旧实现在第 3 层会因锚定错层而删不到（残留孤儿行）。"""
        a = _mk_subtree(real_db_session, "子村")
        b = _mk_subtree(real_db_session, "丑村")
        chain = [
            ("fund_transactions", "fund_id", "funds", "id"),
            ("funds", "project_id", "projects", "id"),
            ("projects", "village_id", "supported_villages", "id"),
        ]
        n = svc._delete_chain(chain, a["village"])
        assert n == 3
        assert real_db_session.get(FundTransaction, a["transaction"]) is None
        assert real_db_session.get(Fund, a["fund"]) is None
        assert real_db_session.get(Project, a["project"]) is None
        assert real_db_session.get(FundTransaction, b["transaction"]) is not None
        assert real_db_session.get(Fund, b["fund"]) is not None
