"""刷新令牌长期会话一致性（v1.18.58）。

默认值曾在三处漂移：config=7 / security=30 / token_manager=7。
本用例锁定唯一业务口径：30 天长期会话，且三处代码与 .env.example 一致。
"""

from datetime import datetime, timezone

import jwt

from app.core import security
from app.core.config import settings
from app.core.token_manager import create_token_pair


def _ttl_days(token: str) -> float:
    payload = jwt.decode(token, options={"verify_signature": False})
    expires = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    return (expires - datetime.now(timezone.utc)).total_seconds() / 86400


def test_config_and_security_defaults_are_30_days():
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 30
    assert security.REFRESH_TOKEN_EXPIRE_DAYS == 30


def test_token_manager_pair_refresh_ttl_is_30_days():
    pair = create_token_pair("alice", access_ttl_minutes=1)
    assert 29.9 <= _ttl_days(pair["refresh_token"]) <= 30.1


def test_legacy_security_refresh_token_uses_same_30_days():
    assert 29.9 <= _ttl_days(security.create_refresh_token({"sub": "alice"})) <= 30.1
