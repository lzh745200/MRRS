"""临时调试：sync_version 事件是否注册（验证后删除）"""
from sqlalchemy import event


def test_event_registered():
    from app.models.supported_village import SupportedVillage
    from app.models.base import TimestampMixin, _bump_sync_version_on_update

    # 检查事件监听是否注册到 SupportedVillage mapper
    from sqlalchemy.orm import Mapper
    m: Mapper = SupportedVillage.__mapper__
    listeners = m.dispatch.before_update
    names = [getattr(l, "__name__", repr(l)) for l in listeners]
    print("before_update listeners:", names)
    assert any("bump_sync_version" in n or n == "_bump_sync_version_on_update" for n in names), names
