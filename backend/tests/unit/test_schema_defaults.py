"""Pydantic v2 可变默认值隔离性。

W27：原用例同时校验 ``RuralTaskStatistics``，随 ``rural_tasks`` 模块下线一并移除；
保留 ``CategoriesResponse``（政策分类）部分，验证口径不变。
"""
from app.schemas.policy import CategoriesResponse


def test_mutable_defaults_isolated():
    """Pydantic v2 应深拷贝默认值：实例间修改互不影响。"""
    c = CategoriesResponse()
    d = CategoriesResponse()
    c.categories.append({"value": "x", "label": "y"})
    assert d.categories == [], "CategoriesResponse.categories 默认值被共享！"
