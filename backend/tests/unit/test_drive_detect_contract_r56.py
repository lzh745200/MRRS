# -*- coding: utf-8 -*-
"""drive_detect 的返回契约（2026-10-31 类型修复配套）。

原返回类型标注 `List[Dict[str, str]]`，但每项的 available 实际是 bool，
且前端就按 bool 消费。注解与实现不一致，下游若按 str 处理（字符串拼接/排序）会崩。
本用例锁定「path/type 是 str、available 是 bool、键集合固定」这一契约。
"""
from app.utils.drive_detect import list_backup_dirs


def test_list_backup_dirs_contract():
    dirs = list_backup_dirs()
    assert isinstance(dirs, list)
    for d in dirs:
        assert set(d.keys()) == {"path", "type", "available"}, d
        assert isinstance(d["path"], str), d
        assert isinstance(d["type"], str), d
        # 关键：available 必须是 bool（原注解声称 str）
        assert isinstance(d["available"], bool), d


def test_available_is_not_string():
    """防止有人改回字符串（"true"/"1"）导致前端 falsy 判断失效。"""
    for d in list_backup_dirs():
        assert not isinstance(d["available"], str), d
