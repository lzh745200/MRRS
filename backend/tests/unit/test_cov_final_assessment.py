"""app.api.v1.assessment 覆盖补全 — village-comparison 组装循环的村庄缺失兜底 (line 377)."""
from unittest.mock import MagicMock, patch

from app.api.v1.assessment import compare_villages


class _FlipIdVillage:
    """两次访问 .id 返回不同值，模拟 villages_dict 键与 allowed_ids 不一致的防御场景"""

    def __init__(self):
        self._calls = 0

    @property
    def id(self):
        self._calls += 1
        return 1 if self._calls == 1 else 2


class TestVillageComparison:
    async def test_village_missing_from_dict_is_skipped(self):
        """allowed_ids 中的 id 在 villages_dict 查不到 → continue 跳过 (line 377)"""
        village = _FlipIdVillage()
        db = MagicMock(name="db")
        q = MagicMock(name="query")
        q.filter.return_value = q
        q.group_by.return_value = q
        q.join.return_value = q
        # .all() 依次对应: villages / latest_incomes / project_stats / fund_stats
        q.all.side_effect = [[village], [], [], []]
        db.query.return_value = q

        user = MagicMock(name="user")
        user.role = "admin"
        user.is_superuser = True

        with patch("app.api.v1.assessment.scoped_filter", return_value=q):
            resp = await compare_villages(village_ids="1", current_user=user, db=db)

        # 村庄被跳过 → 结果为空列表信封
        assert resp["data"]["total"] == 0
        assert resp["data"]["items"] == []
