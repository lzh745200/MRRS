"""回归测试：SensitiveDataFilter 对复合键名（access_token=/refresh_token=）的脱敏（验证后转正）"""
from app.core.logging_config import SensitiveDataFilter


def test_compound_key_redaction():
    f = SensitiveDataFilter()
    # 修复前：\b 边界导致 access_token=/refresh_token= 漏脱敏（真实凭据明文落日志）
    assert "access_token=***" in f._redact("?access_token=abcdef123456")
    assert "refresh_token=***" in f._redact("?refresh_token=abcdef123456")
    assert "abcdef123456" not in f._redact("?token=abcdef123456")
    # 常规键名仍脱敏
    assert "password=***" in f._redact("password=secret1234")
    assert "api_key=***" in f._redact("api_key=secret1234")
    # 非密钥键名不受影响（access_level 不以敏感词结尾）
    assert "access_level=admin" in f._redact("?access_level=admin")
    # 短值（<4 字符）不误伤
    assert "pwd=abc" in f._redact("pwd=abc")
