"""OCR 深审第二轮：2FA 备用恢复码必须哈希存储（app/services/two_factor_service.py）。

修复前：enable_two_factor 把 8 位明文恢复码写入 two_factor_auth.backup_codes，
verify_login 用 token in backup_codes 明文比对 —— DB/备份泄露即可绕过二次验证。
修复后：只存 PBKDF2-HMAC-SHA256 摘要（每码独立盐），明文仅在 enable 响应中出现一次；
校验时先比摘要，未命中再兼容历史明文（常量时间）并把剩余明文整体升级为摘要。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from types import SimpleNamespace

from app.models import Base
from app.models.two_factor_auth import TwoFactorAuth
from app.services import two_factor_service as tfs
from app.services.two_factor_service import TwoFactorService

# 测试用迭代数：真实 100_000 次 PBKDF2 会让本文件每例多花数百毫秒；
# 存储格式与校验路径完全一致，仅代价参数不同（生产常量见 BACKUP_CODE_ITERATIONS）。
_FAST_ITERATIONS = 1_000


@pytest.fixture(autouse=True)
def _fast_iterations(monkeypatch):
    monkeypatch.setattr(tfs, "BACKUP_CODE_ITERATIONS", _FAST_ITERATIONS)


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tfa.db'}")
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def _seed(session_factory, user_id: int, backup_codes, enabled=True):
    from app.services.encryption_service import encrypt_field
    s = session_factory()
    s.add(
        TwoFactorAuth(
            user_id=user_id,
            secret_key=encrypt_field(TwoFactorService.generate_secret()),
            backup_codes=backup_codes,
            enabled=enabled,
        )
    )
    s.commit()
    s.close()


class TestBackupCodeHashingAtRest:
    def test_enable_two_factor_stores_only_hashes(self, session_factory):
        user = SimpleNamespace(id=101, username="u101", email="u101@example.com")
        s = session_factory()
        result = TwoFactorService.enable_two_factor(s, user)
        s.close()

        plaintext = result["backup_codes"]
        assert len(plaintext) == 10
        assert all(len(code) == 8 and code.isdigit() for code in plaintext)

        s2 = session_factory()
        row = s2.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == 101).first()
        stored = list(row.backup_codes or [])
        s2.close()

        assert len(stored) == 10
        assert all(TwoFactorService.is_hashed_backup_code(item) for item in stored)
        for code in plaintext:
            assert code not in stored, "明文恢复码不得落库"
            assert any(TwoFactorService._verify_backup_code(code, item) for item in stored)

    def test_same_code_hashed_twice_uses_distinct_salts(self):
        first = TwoFactorService._hash_backup_code("12345678")
        second = TwoFactorService._hash_backup_code("12345678")
        assert first != second, "每码必须独立随机盐，禁止可枚举的固定摘要"

    def test_verify_login_accepts_hashed_code_and_consumes_it_once(self, session_factory):
        code = "12345678"
        _seed(session_factory, 102, [TwoFactorService._hash_backup_code(code)])
        user = SimpleNamespace(id=102, username="u102")

        s1 = session_factory()
        assert TwoFactorService.verify_login(s1, user, code) is True
        s1.close()

        s2 = session_factory()
        assert TwoFactorService.verify_login(s2, user, code) is False, "恢复码必须一次性"
        s2.close()


class TestLegacyPlaintextMigration:
    def test_legacy_plaintext_code_matches_then_upgrades_remaining(self, session_factory):
        _seed(session_factory, 103, ["11111111", "22222222"])
        user = SimpleNamespace(id=103, username="u103")

        s1 = session_factory()
        assert TwoFactorService.verify_login(s1, user, "22222222") is True
        s1.close()

        s2 = session_factory()
        row = s2.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == 103).first()
        remaining = list(row.backup_codes or [])
        s2.close()

        assert len(remaining) == 1
        assert remaining[0] != "11111111", "历史明文码必须在命中后就地升级为摘要"
        assert TwoFactorService.is_hashed_backup_code(remaining[0])
        assert TwoFactorService._verify_backup_code("11111111", remaining[0]) is True

    def test_wrong_code_does_not_upgrade_or_consume(self, session_factory):
        _seed(session_factory, 104, ["11111111", "22222222"])
        user = SimpleNamespace(id=104, username="u104")

        s1 = session_factory()
        assert TwoFactorService.verify_login(s1, user, "99999999") is False
        s1.close()

        s2 = session_factory()
        row = s2.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == 104).first()
        assert list(row.backup_codes) == ["11111111", "22222222"], "未命中不得改动库中数据"
        s2.close()


class TestBackupCodeVerificationFailClosed:
    def test_malformed_stored_hash_is_rejected(self):
        malformed = tfs.BACKUP_CODE_PREFIX + "$" + str(_FAST_ITERATIONS) + "$nothex$nothex"
        assert TwoFactorService._verify_backup_code("12345678", malformed) is False

    def test_non_string_and_empty_inputs_are_rejected(self):
        assert TwoFactorService._verify_backup_code("", "12345678") is False
        assert TwoFactorService._verify_backup_code(12345678, "12345678") is False
        assert TwoFactorService._verify_backup_code("12345678", 12345678) is False
        assert TwoFactorService._verify_backup_code("12345678", None) is False

    def test_is_hashed_backup_code_shape_check(self):
        assert TwoFactorService.is_hashed_backup_code(None) is False
        assert TwoFactorService.is_hashed_backup_code("12345678") is False
        assert TwoFactorService.is_hashed_backup_code("sha256$1$aa$bb") is False
        assert TwoFactorService.is_hashed_backup_code(tfs.BACKUP_CODE_PREFIX + "$abc$aa$bb") is False
        assert TwoFactorService.is_hashed_backup_code(tfs.BACKUP_CODE_PREFIX + "$1000$aa$bb") is True
