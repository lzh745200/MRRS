"""补齐 app.services.rural_work_service 覆盖率缺口。

目标行：
- 119：get_rural_works 非管理员 → 按创建人过滤
- 254：update_rural_work data 为普通 dict（无 model_dump）→ dict(data) 分支
- 261：更新字段含 type → _to_work_type 转换
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.rural_work_service import RuralWorkService


def _chain_query():
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    return q


class TestGetRuralWorksDataIsolation:
    def test_non_admin_user_filtered_by_creator(self):
        db = MagicMock()
        q = _chain_query()
        q.count.return_value = 0
        q.all.return_value = []
        db.query.return_value = q

        svc = RuralWorkService(db)
        user = SimpleNamespace(id=42)
        # 服务已改为 is_superuser + data_scope 判定（R28 严格范围），is_admin 不再被导入
        with patch("app.services.rural_work_service.is_superuser", return_value=False):
            items, total = svc.get_rural_works(current_user=user)

        assert (items, total) == ([], 0)
        q.filter.assert_called()  # _apply_work_scope 的“仅本人”过滤生效


class TestUpdateRuralWorkDictData:
    def test_plain_dict_data_and_type_conversion(self):
        db = MagicMock()
        work = MagicMock()
        work.id = 1
        work.name = "工作A"
        db.query.return_value.filter.return_value.first.return_value = work

        svc = RuralWorkService(db)
        result = svc.update_rural_work(1, {"type": "infrastructure", "name": "新名"})

        assert result is not None
        assert work.name == "新名"
