"""
Password-based Encryption Service
基于密码的加密服务 - 使用PBKDF2密钥派生和Fernet加密
"""

import base64
import hashlib
import os
from typing import Tuple

from cryptography.fernet import Fernet, InvalidToken

from app.core.exceptions import BusinessError


class InvalidPasswordError(BusinessError):
    """密码错误异常"""

    def __init__(self):
        super().__init__("密码错误，请检查后重试")


class PasswordEncryptionService:
    """
    基于密码的加密服务

    使用PBKDF2-HMAC-SHA256进行密钥派生，使用Fernet进行对称加密
    """

    # 默认PBKDF2迭代次数（OWASP推荐最少100000次）
    DEFAULT_ITERATIONS = 100000

    # 盐值长度（字节）
    SALT_LENGTH = 32

    @staticmethod
    def generate_salt() -> bytes:
        """
        生成随机盐值

        Returns:
            32字节随机盐值
        """
        return os.urandom(PasswordEncryptionService.SALT_LENGTH)

    @staticmethod
    def derive_key_from_password(password: str, salt: bytes, iterations: int = DEFAULT_ITERATIONS) -> bytes:
        """
        从密码派生加密密钥

        使用PBKDF2-HMAC-SHA256算法

        Args:
            password: 用户密码
            salt: 盐值
            iterations: 迭代次数

        Returns:
            32字节派生密钥（适用于Fernet）
        """
        password_bytes = password.encode("utf-8")
        key = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, iterations, dklen=32)
        return key

    @staticmethod
    def _key_to_fernet_key(key: bytes) -> bytes:
        """
        将32字节密钥转换为Fernet密钥格式

        Fernet要求密钥为URL-safe base64编码

        Args:
            key: 32字节原始密钥

        Returns:
            Fernet格式密钥
        """
        return base64.urlsafe_b64encode(key)

    @staticmethod
    def encrypt_data(data: bytes, password: str, salt: bytes, iterations: int = DEFAULT_ITERATIONS) -> bytes:
        """
        使用密码加密数据

        Args:
            data: 要加密的数据
            password: 密码
            salt: 盐值
            iterations: PBKDF2迭代次数

        Returns:
            加密后的数据
        """
        # 派生密钥
        key = PasswordEncryptionService.derive_key_from_password(password, salt, iterations)
        fernet_key = PasswordEncryptionService._key_to_fernet_key(key)

        # 加密
        fernet = Fernet(fernet_key)
        encrypted_data = fernet.encrypt(data)

        return encrypted_data

    @staticmethod
    def decrypt_data(
        encrypted_data: bytes,
        password: str,
        salt: bytes,
        iterations: int = DEFAULT_ITERATIONS,
    ) -> bytes:
        """
        使用密码解密数据

        Args:
            encrypted_data: 加密的数据
            password: 密码
            salt: 盐值
            iterations: PBKDF2迭代次数

        Returns:
            解密后的数据

        Raises:
            InvalidPasswordError: 密码错误
        """
        try:
            # 派生密钥
            key = PasswordEncryptionService.derive_key_from_password(password, salt, iterations)
            fernet_key = PasswordEncryptionService._key_to_fernet_key(key)

            # 解密
            fernet = Fernet(fernet_key)
            decrypted_data = fernet.decrypt(encrypted_data)

            return decrypted_data
        except InvalidToken:
            raise InvalidPasswordError()

    @staticmethod
    def encrypt_file(
        file_path: str,
        password: str,
        output_path: str,
        iterations: int = DEFAULT_ITERATIONS,
    ) -> Tuple[str, int]:
        """
        加密文件

        Args:
            file_path: 源文件路径
            password: 密码
            output_path: 输出文件路径
            iterations: PBKDF2迭代次数

        Returns:
            (盐值hex字符串, 迭代次数)
        """
        # 生成盐值
        salt = PasswordEncryptionService.generate_salt()

        # 读取文件
        with open(file_path, "rb") as f:
            data = f.read()

        # 加密
        encrypted_data = PasswordEncryptionService.encrypt_data(data, password, salt, iterations)

        # 写入加密文件
        with open(output_path, "wb") as f:
            f.write(encrypted_data)

        return salt.hex(), iterations

    @staticmethod
    def decrypt_file(
        encrypted_path: str,
        password: str,
        salt_hex: str,
        iterations: int,
        output_path: str,
    ) -> None:
        """
        解密文件

        Args:
            encrypted_path: 加密文件路径
            password: 密码
            salt_hex: 盐值hex字符串
            iterations: PBKDF2迭代次数
            output_path: 输出文件路径

        Raises:
            InvalidPasswordError: 密码错误
        """
        # 读取加密文件
        with open(encrypted_path, "rb") as f:
            encrypted_data = f.read()

        # 解密
        salt = bytes.fromhex(salt_hex)
        decrypted_data = PasswordEncryptionService.decrypt_data(encrypted_data, password, salt, iterations)

        # 写入解密文件
        with open(output_path, "wb") as f:
            f.write(decrypted_data)
