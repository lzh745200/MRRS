"""Bug B 回归：通行码 UNIQUE 冲突不再冒泡为未处理 500。

历史缺陷（真机复现）：
- B3 level-3 回退改绑机器码时，若目标 machine_code 已被另一条记录占用
  （machine_code UNIQUE），safe_commit 抛 IntegrityError 未捕获 → 注册接口 500。
- B4 管理员手动指定的短通行码与现有记录 pass_code 冲突（pass_code UNIQUE）
  → create_machine_code_record 的 safe_commit 抛 IntegrityError 未捕获 → 录入接口 500。

修复后：B3 回滚并返回 None（验证失败 → 干净的 400）；B4 抛业务 ValueError
（API 层已映射为 400）。两条路径都不再崩溃。

注：用 MagicMock 会话（与 test_passcode_hmac_failclosed.py 同风格），
db.commit.side_effect 触发 safe_commit 内部的 IntegrityError 重抛路径。
"""

import pytest
from sqlalchemy.exc import IntegrityError
from unittest.mock import MagicMock

from app.services import machine_code_service as mcs


def _integrity_error() -> IntegrityError:
    return IntegrityError(
        "STMT", {}, Exception("UNIQUE constraint failed: machine_codes.machine_code")
    )


class TestLevel3RebindCollision:
    def test_rebind_machine_code_collision_returns_none(self):
        """B3：改绑目标机器码已被占用 → 回滚 + 返回 None（而非未捕获 500）。"""
        record = MagicMock()
        record.machine_code = "OLDMC123"
        record.status = "pending"
        record.organization_id = None

        db = MagicMock()
        q = MagicMock()
        # impl(normalize=False): level1 None, level2 None, level3 record → 改绑冲突返回 None
        # impl(normalize=True):  level1/2/3 全 None → 返回 None
        q.filter.return_value.first.side_effect = [None, None, record, None, None, None]
        db.query.return_value = q
        db.commit.side_effect = _integrity_error()

        svc = mcs.MachineCodeService(db)
        result = svc.verify_pass_code("SOMEPASSCODE", "NEWMC456")

        assert result is None
        # safe_commit 与 B3 处理各回滚一次；至少必须回滚，不能把脏会话留给调用方
        assert db.rollback.called

    def test_rebind_success_still_writes_audit(self):
        """无冲突时改绑照常成功并写审计（守护 B3 修复未误伤正常路径）。"""
        record = MagicMock()
        record.machine_code = "OLDMC123"
        record.status = "pending"
        record.organization_id = None

        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.side_effect = [None, None, record]
        db.query.return_value = q
        # commit 不抛异常 → 改绑成功

        svc = mcs.MachineCodeService(db)
        with pytest.MonkeyPatch.context() as mp:
            called = {"n": 0}

            def _fake_wwl(*args, **kwargs):
                called["n"] += 1

            mp.setattr("app.services.work_log_service.write_work_log", _fake_wwl)
            result = svc.verify_pass_code("SOMEPASSCODE", "NEWMC456")

        assert result is record
        assert record.machine_code == "NEWMC456"
        assert called["n"] == 1


class TestCreateRecordPassCodeCollision:
    def test_new_record_collision_raises_valueerror(self):
        """B4：新建记录时手动通行码冲突 → 抛业务 ValueError（API 转 400）。"""
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.return_value = None  # existing=None → 新建分支
        db.query.return_value = q
        db.commit.side_effect = _integrity_error()

        svc = mcs.MachineCodeService(db)
        with pytest.raises(ValueError, match="通行码已被其他机器码记录占用"):
            svc.create_machine_code_record("MC-NEW", created_by=1, pass_code="1234")

    def test_reset_existing_collision_raises_valueerror(self):
        """B4：复用已有记录重置通行码时冲突 → 抛业务 ValueError。"""
        existing = MagicMock()
        existing.status = "active"
        existing.user_id = 5

        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.first.return_value = existing  # 命中已有 → 重置分支
        db.query.return_value = q
        db.commit.side_effect = _integrity_error()

        svc = mcs.MachineCodeService(db)
        with pytest.raises(ValueError, match="通行码已被其他机器码记录占用"):
            svc.create_machine_code_record("MC-EXISTING", created_by=1, pass_code="1234")
