"""临时验证：Pydantic 可变默认值隔离性（验证后删除）"""
from app.schemas.policy import CategoriesResponse
from app.schemas.rural_task import RuralTaskStatistics


def test_mutable_defaults_isolated():
    """Pydantic v2 应深拷贝默认值：实例间修改互不影响"""
    c = CategoriesResponse()
    d = CategoriesResponse()
    c.categories.append({"value": "x", "label": "y"})
    assert d.categories == [], "CategoriesResponse.categories 默认值被共享！"

    e = RuralTaskStatistics()
    f = RuralTaskStatistics()
    e.by_category["k"] = 1
    assert f.by_category == {}, "RuralTaskStatistics.by_category 默认值被共享！"
