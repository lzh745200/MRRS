"""组织层级级联维护与防环的回归用例（2026-10-14 修复配套）。

背景（修复前）：
- `POST /organizations/{id}/move` 只改 parent_id，**不刷新 path/level**；
- `PUT /organizations/{id}` 同样不刷新，且**没有防环**（只拦"自身"）。

于是组织被移动后："树视图（parent_id）"与"权限视图（path 前缀）"长期背离 ——
移动后的组织看不到自己的下级数据、或仍能看到原父级的兄弟数据（组织级数据权限
`Organization.path.like(f"{org.path}%")` 完全依赖 path）。

这组用例锁定修复后的行为：移动/改父必须级联重算自身与全部子孙的 path/level，
且把组织挂到自身子孙之下必须被拒绝。
"""
from types import SimpleNamespace

from app.services.organization_service import OrganizationService


# ---------------------------------------------------------------------------
# 轻量会话替身：只支持服务里用到的两种查询形态
#   query(Organization).filter(Organization.id == X).first()
#   query(Organization).filter(Organization.parent_id == X).all()
# ---------------------------------------------------------------------------
class _Query:
    def __init__(self, orgs):
        self._orgs = orgs
        self._expr = None

    def filter(self, expr):
        self._expr = expr
        return self

    def _column(self):
        left = self._expr.left
        return getattr(left, "key", None)

    def _value(self):
        return self._expr.right.value

    def first(self):
        col, val = self._column(), self._value()
        for org in self._orgs:
            if getattr(org, col, None) == val:
                return org
        return None

    def all(self):
        col, val = self._column(), self._value()
        return [org for org in self._orgs if getattr(org, col, None) == val]


class _Session:
    def __init__(self, orgs):
        self._orgs = orgs

    def query(self, _model):
        return _Query(self._orgs)


def _floor():
    """构造两棵树：

        root(1)                      other(4)
        └─ a(2)                      （另一棵根）
           └─ a1(3)

    path 形态与生产一致：根 `/{id}/`，子 `{父 path}{id}/`；level 为 path 段数。
    """
    root = SimpleNamespace(id=1, parent_id=None, path="/1/", level=1)
    a = SimpleNamespace(id=2, parent_id=1, path="/1/2/", level=2)
    a1 = SimpleNamespace(id=3, parent_id=2, path="/1/2/3/", level=3)
    other = SimpleNamespace(id=4, parent_id=None, path="/4/", level=1)
    return [root, a, a1, other], root, a, a1, other


def test_move_cascades_path_and_level_to_descendants():
    """把 a(2) 连同其子孙挂到 other(4) 下：三者 path/level 必须整体刷新。"""
    orgs, _root, a, a1, other = _floor()
    svc = OrganizationService(db=_Session(orgs))

    a.parent_id = other.id
    changed = svc.recompute_subtree_paths(a)

    assert changed == 2, "a 与 a1 都应被重算"
    assert a.path == "/4/2/" and a.level == 2
    assert a1.path == "/4/2/3/" and a1.level == 3


def test_move_to_top_level_resets_path():
    """置为顶级（parent_id=None）后 path 应收敛为 /{id}/、level 回到 1。"""
    orgs, root, a, a1, _other = _floor()
    svc = OrganizationService(db=_Session(orgs))

    a.parent_id = None
    svc.recompute_subtree_paths(a)

    assert a.path == "/2/" and a.level == 1
    assert a1.path == "/2/3/" and a1.level == 2


def test_recompute_is_idempotent():
    """已经正确的子树再次重算不应产生任何改动（幂等）。"""
    orgs, _root, a, _a1, _other = _floor()
    svc = OrganizationService(db=_Session(orgs))

    assert svc.recompute_subtree_paths(a) == 0


def test_recompute_tolerates_existing_cycle():
    """库中若已存在环，重算不得死循环（只跳过重复节点）。"""
    root = SimpleNamespace(id=1, parent_id=2, path="/1/", level=1)
    a = SimpleNamespace(id=2, parent_id=1, path="/2/", level=1)
    svc = OrganizationService(db=_Session([root, a]))

    changed = svc.recompute_subtree_paths(root)
    assert changed >= 1  # 环上节点的 path 必然需要重写，但必须在有限步内结束


def test_would_create_cycle_detects_descendant():
    """把 a(2) 挂到其子孙 a1(3) 之下必须判为成环。"""
    orgs, _root, a, _a1, other = _floor()
    svc = OrganizationService(db=_Session(orgs))

    assert svc.would_create_cycle(2, 3) is True       # 目标是自身子孙
    assert svc.would_create_cycle(2, 2) is True       # 目标是自身
    assert svc.would_create_cycle(2, 1) is False      # 挂到原父级 → 合法
    assert svc.would_create_cycle(2, 4) is False      # 挂到另一棵树 → 合法
    assert svc.would_create_cycle(2, None) is False   # 置为顶级 → 合法


def test_validate_parent_child_relationship_keeps_contract():
    """对外语义保持不变：自身/不存在的子级一律 False，合法关系 True。"""
    orgs, _root, _a, _a1, other = _floor()
    svc = OrganizationService(db=_Session(orgs))

    assert svc.validate_parent_child_relationship(1, 1) is False      # 自身
    assert svc.validate_parent_child_relationship(1, 999) is False    # 子级不存在
    assert svc.validate_parent_child_relationship(1, 2) is True       # 合法
    assert svc.validate_parent_child_relationship(3, 2) is False      # 父级是自身子孙 → 成环
    assert svc.validate_parent_child_relationship(other.id, 2) is True
