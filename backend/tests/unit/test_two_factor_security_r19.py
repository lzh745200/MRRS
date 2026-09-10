"""R19 深探修复的回归锁定（2FA 链路两处真实缺陷）。

缺陷 1（认证绕过，高危）：`/auth/login` 在 2FA 挑战分支下发的 `temp_token` 由
`create_token_pair(..., extra_claims={"two_factor_pending": True})` 生成，其 `type`
仍是 `"access"`；`get_current_user` 只校验黑名单与 token 类型，因此该"中间态令牌"
可以直接当普通 Bearer 令牌调用全部业务端点（读写数据、甚至
`POST /two-factor/disable` 永久关闭二次验证）。实测：仅凭密码拿到 temp_token 后
`GET /auth/me`、`GET /users`、`GET /funds` 全部 200，`POST /two-factor/disable` 也 200。

缺陷 2（恢复码可无限复用，高危）：`two_factor_auth.backup_codes` 是裸 `Column(JSON)`，
`TwoFactorService.verify_login` 用 `list.remove(token)` 就地修改——SQLAlchemy 对裸 JSON
列的就地修改不产生 attribute 事件，不生成 UPDATE，提交静默丢失。实测：同一备用码
连续两次登录均 200，DB 中码数恒为 10，与界面承诺的"每个恢复码只能使用一次"相悖。
"""

from types import SimpleNamespace
from unittest.mock import MagicMock
import inspect

import pytest
from fastapi import HTTPException

import app.core.security as sec
from app.services.two_factor_service import TwoFactorService


def _call_kwargs(db, token: str) -> dict:
    """构造调用 `get_current_user` 的关键字参数。

    `get_current_user` 有两种签名并存（并发会话正把它改成
    `db: Session = Depends(get_db)` 复用请求级 Session）：老版在函数内
    `SessionLocal()` 自建会话，新版由 FastAPI 注入。这里按实际签名决定是否传
    `db`，使本文件在两种形态下都成立 —— 不传 `db` 时新版会把 `Depends(...)`
    对象当成 Session 用（`'Depends' object has no attribute 'query'`）。
    """
    kwargs = {"credentials": SimpleNamespace(credentials=token)}
    if "db" in inspect.signature(sec.get_current_user).parameters:
        kwargs["db"] = db
    return kwargs


class TestTwoFactorPendingTokenCannotBeUsedAsAccessToken:
    """缺陷 1：2FA 中间态令牌必须被认证出口拒绝。"""

    async def test_pending_token_rejected(self, monkeypatch):
        monkeypatch.setattr(
            sec,
            "decode_token",
            MagicMock(return_value={"sub": "admin", "type": "access", "two_factor_pending": True}),
        )
        db = MagicMock()
        session_local = MagicMock(return_value=db)
        monkeypatch.setattr("app.core.database.SessionLocal", session_local)

        with pytest.raises(HTTPException) as exc:
            await sec.get_current_user(**_call_kwargs(db, "temp"))

        assert exc.value.status_code == 401
        assert "二次验证未完成" in exc.value.detail
        # 拒绝必须发生在建库会话之前：既不泄露"用户是否存在"，也不做无用查询
        db.query.assert_not_called()
        session_local.assert_not_called()

    async def test_pending_token_cannot_reach_two_factor_disable(self, monkeypatch):
        """显式锁定攻击路径：中间态令牌不得用于关闭二次验证。"""
        monkeypatch.setattr(
            sec,
            "decode_token",
            MagicMock(return_value={"sub": "admin", "type": "access", "two_factor_pending": True}),
        )
        db = MagicMock()
        monkeypatch.setattr("app.core.database.SessionLocal", MagicMock(return_value=db))

        with pytest.raises(HTTPException) as exc:
            await sec.get_current_user(**_call_kwargs(db, "temp"))

        assert exc.value.status_code == 401

    async def test_explicit_false_claim_is_allowed(self, monkeypatch):
        """`two_factor_pending: False` 是正常令牌形态，不得误伤。"""
        user = SimpleNamespace(id=7, username="admin", token_version_safe=0)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        monkeypatch.setattr("app.core.database.SessionLocal", MagicMock(return_value=db))
        monkeypatch.setattr(
            sec,
            "decode_token",
            MagicMock(return_value={"sub": "admin", "type": "access", "two_factor_pending": False}),
        )

        result = await sec.get_current_user(**_call_kwargs(db, "real"))

        assert result is user

    async def test_absent_claim_is_allowed(self, monkeypatch):
        """无该声明的历史令牌继续放行（兼容）。"""
        user = SimpleNamespace(id=8, username="admin", token_version_safe=0)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        monkeypatch.setattr("app.core.database.SessionLocal", MagicMock(return_value=db))
        monkeypatch.setattr(
            sec, "decode_token", MagicMock(return_value={"sub": "admin", "type": "access"})
        )

        result = await sec.get_current_user(**_call_kwargs(db, "real"))

        assert result is user


class TestBackupCodeSingleUseIsPersisted:
    """缺陷 2：备用码消费必须真正落库（裸 JSON 列就地修改不产生 UPDATE）。"""

    @pytest.fixture
    def file_engine(self, tmp_path):
        """文件型 SQLite：只有真正落盘才能在新会话里读回，内存库会掩盖该缺陷。"""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.models import Base

        engine = create_engine(f"sqlite:///{tmp_path / 'two_factor.db'}")
        Base.metadata.create_all(bind=engine)
        yield engine, sessionmaker(bind=engine)
        engine.dispose()

    def test_consumed_backup_code_disappears_from_db(self, file_engine):
        from app.models.two_factor_auth import TwoFactorAuth
        from app.services.encryption_service import encrypt_field

        engine, Session = file_engine
        secret = TwoFactorService.generate_secret()

        s1 = Session()
        s1.add(
            TwoFactorAuth(
                user_id=1,
                secret_key=encrypt_field(secret),
                backup_codes=["11111111", "22222222"],
                enabled=True,
            )
        )
        s1.commit()
        s1.close()

        s2 = Session()
        user = SimpleNamespace(id=1, username="u1")
        assert TwoFactorService.verify_login(s2, user, "11111111") is True
        s2.close()

        s3 = Session()
        row = s3.query(TwoFactorAuth).first()
        assert row.backup_codes == ["22222222"], "被消费的备用码必须从库中移除"
        s3.close()

    def test_second_use_of_same_code_is_rejected(self, file_engine):
        from app.models.two_factor_auth import TwoFactorAuth
        from app.services.encryption_service import encrypt_field

        engine, Session = file_engine
        secret = TwoFactorService.generate_secret()

        s1 = Session()
        s1.add(
            TwoFactorAuth(
                user_id=2,
                secret_key=encrypt_field(secret),
                backup_codes=["33333333"],
                enabled=True,
            )
        )
        s1.commit()
        s1.close()

        user = SimpleNamespace(id=2, username="u2")
        s2 = Session()
        assert TwoFactorService.verify_login(s2, user, "33333333") is True
        s2.close()

        s3 = Session()
        assert TwoFactorService.verify_login(s3, user, "33333333") is False
        s3.close()

    def test_all_codes_exhausted_leaves_empty_list(self, file_engine):
        from app.models.two_factor_auth import TwoFactorAuth
        from app.services.encryption_service import encrypt_field

        engine, Session = file_engine
        secret = TwoFactorService.generate_secret()

        s1 = Session()
        s1.add(
            TwoFactorAuth(
                user_id=3,
                secret_key=encrypt_field(secret),
                backup_codes=["44444444"],
                enabled=True,
            )
        )
        s1.commit()
        s1.close()

        user = SimpleNamespace(id=3, username="u3")
        s2 = Session()
        assert TwoFactorService.verify_login(s2, user, "44444444") is True
        s2.close()

        s3 = Session()
        row = s3.query(TwoFactorAuth).first()
        assert row.backup_codes == []
        s3.close()


class TestBackupCodesColumnIsMutationTracked:
    """模型层锁定：就地 remove 必须被 ORM 追踪为"脏"，否则恢复码消费从不落库。"""

    def test_in_place_remove_marks_attribute_dirty(self, tmp_path):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.models import Base
        from app.models.two_factor_auth import TwoFactorAuth
        from app.services.encryption_service import encrypt_field

        engine = create_engine(f"sqlite:///{tmp_path / 'dirty.db'}")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)

        s = Session()
        s.add(
            TwoFactorAuth(
                user_id=9,
                secret_key=encrypt_field(TwoFactorService.generate_secret()),
                backup_codes=["55555555"],
                enabled=True,
            )
        )
        s.commit()

        row = s.query(TwoFactorAuth).first()
        assert s.is_modified(row, include_collections=True) is False

        row.backup_codes.remove("55555555")

        assert s.is_modified(row, include_collections=True) is True, (
            "backup_codes 必须是 MutableList.as_mutable(JSON)："
            "裸 JSON 列的就地 remove/append 不产生 attribute 事件、不生成 UPDATE，"
            "备用恢复码可被无限复用"
        )
        s.close()
        engine.dispose()
