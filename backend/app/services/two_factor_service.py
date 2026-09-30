"""
双因素认证服务
"""

import hashlib
import hmac
import logging
import secrets
from base64 import b64encode
from datetime import timezone, datetime
from io import BytesIO
from typing import List

import pyotp
from sqlalchemy.orm import Session

from app.models.two_factor_auth import TwoFactorAuth
from app.models.user import User
from app.services.encryption_service import decrypt_field, encrypt_field
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

# 备用恢复码存储格式（2026-09-30 深审修复）：
# 历史实现把 8 位恢复码**明文**写入 two_factor_auth.backup_codes（JSON 列）并在
# verify_login 里明文比对 —— 数据库文件或备份泄露即等于二次验证被绕过。
# 现改为只存单向 PBKDF2-HMAC-SHA256 摘要（每码独立随机盐），明文仅出现在
# enable_two_factor 的当次响应里。校验时先按摘要比对；为兼容升级前已落库的
# 历史明文数据，摘要未命中时再与明文比对（常量时间），命中即把该用户剩余的
# 明文恢复码整体升级为摘要后落库。
BACKUP_CODE_PREFIX = "pbkdf2_sha256"
BACKUP_CODE_ITERATIONS = 100_000
_BACKUP_CODE_SALT_BYTES = 16


class TwoFactorService:
    """双因素认证服务"""

    @staticmethod
    def generate_secret() -> str:
        """生成TOTP密钥"""
        return pyotp.random_base32()

    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """
        生成备用恢复码

        Args:
            count: 生成数量

        Returns:
            恢复码列表
        """
        codes = []
        for _ in range(count):
            # 生成8位数字恢复码
            code = "".join([str(secrets.randbelow(10)) for _ in range(8)])
            codes.append(code)
        return codes

    @staticmethod
    def _hash_backup_code(code: str) -> str:
        """把恢复码转换为带随机盐的单向摘要（存储格式见 BACKUP_CODE_PREFIX）"""
        salt = secrets.token_bytes(_BACKUP_CODE_SALT_BYTES)
        digest = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, BACKUP_CODE_ITERATIONS)
        return "$".join(
            (BACKUP_CODE_PREFIX, str(BACKUP_CODE_ITERATIONS), salt.hex(), digest.hex())
        )

    @staticmethod
    def is_hashed_backup_code(stored: object) -> bool:
        """判断存储项是否已是摘要格式（否则视为历史明文数据）"""
        if not isinstance(stored, str):
            return False
        parts = stored.split("$")
        return len(parts) == 4 and parts[0] == BACKUP_CODE_PREFIX and parts[1].isdigit()

    @staticmethod
    def _verify_backup_code(code: str, stored: object) -> bool:
        """校验恢复码：摘要优先，未命中再兼容历史明文（常量时间比较）"""
        if not isinstance(code, str) or not code:
            return False
        if TwoFactorService.is_hashed_backup_code(stored):
            parts = str(stored).split("$")
            try:
                salt = bytes.fromhex(parts[2])
                expected = bytes.fromhex(parts[3])
                iterations = int(parts[1])
            except ValueError:
                # 存储项畸形（如手工改库）时 fail-closed：视为不匹配
                return False
            digest = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(digest, expected)
        if isinstance(stored, str):
            # 历史明文数据：常量时间比较，避免按字符提前返回泄露前缀
            return hmac.compare_digest(code, stored)
        return False

    @staticmethod
    def generate_qr_code(secret: str, user_email: str, issuer: str = "帮扶管理信息系统") -> str:
        """
        生成TOTP二维码

        Args:
            secret: TOTP密钥
            user_email: 用户邮箱
            issuer: 发行者名称

        Returns:
            Base64编码的二维码图片
        """
        # 生成TOTP URI
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=user_email, issuer_name=issuer)

        # 生成二维码（qrcode 懒加载：该包导入代价高——实测 AV 环境下
        # 首次 import 可达 100s+，移入方法内避免拖慢模块导入与测试收集）
        import qrcode

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # 转换为Base64
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"

    @staticmethod
    def verify_totp(secret: str, token: str) -> bool:
        """
        验证TOTP令牌

        Args:
            secret: TOTP密钥
            token: 用户输入的6位数字令牌

        Returns:
            是否验证成功
        """
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(token, valid_window=1)  # 允许前后30秒的时间窗口
        except Exception as e:
            logger.error(f"TOTP验证失败: {e}")
            return False

    @staticmethod
    def enable_two_factor(db: Session, user: User) -> dict:
        """
        为用户启用双因素认证

        Args:
            db: 数据库会话
            user: 用户对象

        Returns:
            包含密钥和二维码的字典
        """
        # 检查是否已启用
        existing = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user.id).first()
        if existing and existing.enabled:
            raise ValueError("双因素认证已启用")

        # 生成密钥和备用码
        secret = TwoFactorService.generate_secret()
        backup_codes = TwoFactorService.generate_backup_codes()

        # 加密存储密钥
        encrypted_secret = encrypt_field(secret)

        # 落库的只有摘要；明文恢复码仅随本次响应返回给用户
        hashed_backup_codes = [TwoFactorService._hash_backup_code(code) for code in backup_codes]

        # 创建或更新记录
        if existing:
            existing.secret_key = encrypted_secret
            existing.backup_codes = hashed_backup_codes
            existing.enabled = False  # 需要验证后才启用
            existing.verified_at = None
            two_factor = existing
        else:
            two_factor = TwoFactorAuth(
                user_id=user.id,
                secret_key=encrypted_secret,
                backup_codes=hashed_backup_codes,
                enabled=False,
            )
            db.add(two_factor)

        safe_commit(db)
        db.refresh(two_factor)

        # 生成二维码
        qr_code = TwoFactorService.generate_qr_code(secret, user.email)

        return {"secret": secret, "qr_code": qr_code, "backup_codes": backup_codes}

    @staticmethod
    def verify_and_enable(db: Session, user: User, token: str) -> bool:
        """
        验证TOTP令牌并启用双因素认证

        Args:
            db: 数据库会话
            user: 用户对象
            token: TOTP令牌

        Returns:
            是否验证成功
        """
        two_factor = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user.id).first()
        if not two_factor:
            raise ValueError("未找到双因素认证配置")

        # 解密密钥
        secret = decrypt_field(two_factor.secret_key)

        # 验证令牌
        if TwoFactorService.verify_totp(secret, token):
            two_factor.enabled = True
            two_factor.verified_at = datetime.now(timezone.utc)
            safe_commit(db)
            return True

        return False

    @staticmethod
    def verify_login(db: Session, user: User, token: str) -> bool:
        """
        验证登录时的TOTP令牌

        Args:
            db: 数据库会话
            user: 用户对象
            token: TOTP令牌或备用码

        Returns:
            是否验证成功
        """
        two_factor = (
            db.query(TwoFactorAuth).filter(
                TwoFactorAuth.user_id == user.id,
                TwoFactorAuth.enabled == True,  # noqa: E712
            ).first()
        )

        if not two_factor:
            return False

        # 先尝试TOTP验证
        secret = decrypt_field(two_factor.secret_key)
        if TwoFactorService.verify_totp(secret, token):
            return True

        # 尝试备用码验证（使用后移除；顺带把历史明文码升级为摘要存储）
        stored_codes = list(two_factor.backup_codes or [])
        matched_index = None
        for index, stored in enumerate(stored_codes):
            if TwoFactorService._verify_backup_code(token, stored):
                matched_index = index
                break

        if matched_index is None:
            return False

        remaining = [code for i, code in enumerate(stored_codes) if i != matched_index]
        has_legacy_plaintext = any(not TwoFactorService.is_hashed_backup_code(code) for code in remaining)
        migrated = [
            code if TwoFactorService.is_hashed_backup_code(code) else TwoFactorService._hash_backup_code(code)
            for code in remaining
        ]
        if has_legacy_plaintext:
            logger.info("用户 %s 的历史明文备用码已升级为摘要存储", user.username)
        two_factor.backup_codes = migrated
        safe_commit(db)
        logger.info(f"用户 {user.username} 使用备用码登录")
        return True

    @staticmethod
    def disable_two_factor(db: Session, user: User):
        """
        禁用双因素认证

        Args:
            db: 数据库会话
            user: 用户对象
        """
        two_factor = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user.id).first()
        if two_factor:
            db.delete(two_factor)
            safe_commit(db)
            logger.info(f"用户 {user.username} 已禁用双因素认证")

    @staticmethod
    def is_enabled(db: Session, user: User) -> bool:
        """
        检查用户是否启用了双因素认证

        Args:
            db: 数据库会话
            user: 用户对象

        Returns:
            是否启用
        """
        two_factor = (
            db.query(TwoFactorAuth).filter(
                TwoFactorAuth.user_id == user.id,
                TwoFactorAuth.enabled == True,  # noqa: E712
            ).first()
        )
        return two_factor is not None
