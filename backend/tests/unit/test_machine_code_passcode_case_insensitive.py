"""通行码验证大小写归一化回归测试（真实 SQLite 语义）。

背景：通行码为小写十六进制（自动生成）或纯数字（手动 4 位）。用户以
大写输入（图片 OCR / 手动录入习惯）时属同一通行码，此前因 SQLite
``=`` 二进制比较区分大小写而被误拒，注册页提示「通行码无效」。

修复：verify_pass_code 入参先 ``.strip().lower()``，_verify_pass_code_impl
对库内 pass_code 列统一 ``func.lower`` 后比较（normalize 路径同时去连字符）。

本文件用真实 sqlite（:memory: + StaticPool）验证 SQL 语义，Mock 链无法
证明 func.lower 的比较行为。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.machine_code import MachineCode
from app.services.machine_code_service import MachineCodeService


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()


class TestPassCodeCaseInsensitive:
    def test_uppercase_exact_matches_lowercase_stored(self):
        db = _session()
        try:
            db.add(MachineCode(
                machine_code="MC-ALPHA", pass_code="abcd-ef12-3456-7890",
                status="pending",
            ))
            db.commit()
            svc = MachineCodeService(db)
            record = svc.verify_pass_code("ABCD-EF12-3456-7890", "MC-ALPHA")
            assert record is not None
            assert record.machine_code == "MC-ALPHA"
        finally:
            db.close()

    def test_uppercase_without_hyphen_matches(self):
        """大写 + 全省略连字符：走去连字符归一化路径且大小写不敏感。"""
        db = _session()
        try:
            db.add(MachineCode(
                machine_code="MC-BETA", pass_code="abcd-ef12-3456-7890",
                status="pending",
            ))
            db.commit()
            svc = MachineCodeService(db)
            record = svc.verify_pass_code("ABCDEF1234567890", "MC-BETA")
            assert record is not None
            assert record.machine_code == "MC-BETA"
        finally:
            db.close()

    def test_uppercase_drift_fallback_rebind(self):
        """大写输入 + 机器码漂移：第三级回退（仅凭通行码）同样大小写不敏感。"""
        db = _session()
        try:
            db.add(MachineCode(
                machine_code="MC-OLD", pass_code="dead-beef-cafe-babe",
                status="pending",
            ))
            db.commit()
            svc = MachineCodeService(db)
            record = svc.verify_pass_code("DEAD-BEEF-CAFE-BABE", "MC-NEW-DRIFTED")
            assert record is not None
            assert record.machine_code == "MC-NEW-DRIFTED"
        finally:
            db.close()

    def test_numeric_passcode_unaffected(self):
        """手动 4 位数字通行码不受 lower() 影响。"""
        db = _session()
        try:
            db.add(MachineCode(
                machine_code="MC-NUM", pass_code="4821", status="pending",
            ))
            db.commit()
            svc = MachineCodeService(db)
            assert svc.verify_pass_code("4821", "MC-NUM") is not None
            assert svc.verify_pass_code(" 4821 ", "MC-NUM") is not None
            assert svc.verify_pass_code("4820", "MC-NUM") is None
        finally:
            db.close()

    def test_mixed_case_org_passcode_matches(self):
        """组织通行码（不绑定机器码）同样接受大写输入。"""
        db = _session()
        try:
            db.add(MachineCode(
                machine_code="ORG-1-xyz", pass_code="cafe-0000-1111-2222",
                status="pending", organization_id=None,
            ))
            db.commit()
            svc = MachineCodeService(db)
            record = svc.verify_pass_code("CAFE-0000-1111-2222", "ANY-MACHINE")
            assert record is not None
        finally:
            db.close()
