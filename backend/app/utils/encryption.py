"""
数据包加密工具
支持AES-256加密
"""

import base64
import hashlib
import os
import threading

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.logging import logger


class DataPackageEncryption:
    """数据包加密工具"""

    def __init__(self, password: str = None, key: bytes = None):
        """
        初始化加密工具

        Args:
            password: 加密密码
            key: 加密密钥（如果提供，则忽略password）
        """
        if key:
            self.key = key
            self.cipher = Fernet(key)
        elif password:
            # 从密码生成密钥
            self.key = self._derive_key_from_password(password)
            self.cipher = Fernet(self.key)
        else:
            # 生成新密钥
            self.key = Fernet.generate_key()
            self.cipher = Fernet(self.key)

    # 从运行时密钥存储中加载部署唯一盐值
    _deployment_salt: bytes | None = None
    # 首次加载可能被多线程并发触发：无锁时各线程会各自拿到不同的随机盐，
    # 同进程内派生出互不兼容的密钥（深审 #85）。
    _salt_lock = threading.Lock()

    @classmethod
    def _load_deployment_salt(cls) -> bytes:
        """加载或生成部署唯一盐值（持久化到运行时密钥文件）。

        Raises:
            RuntimeError: 盐值无法持久化。绝不用进程内随机盐顶替 ——
                本次运行写入的密文在重启后将永久不可解，且只有解密时才暴露
                （深审 #85）。与 pii_crypto 的 require_persisted 口径一致。
        """
        if cls._deployment_salt is not None:
            return cls._deployment_salt

        with cls._salt_lock:
            if cls._deployment_salt is not None:
                return cls._deployment_salt
            from app.utils.runtime_secrets import get_or_create_secret
            try:
                salt_hex = get_or_create_secret(
                    "ENCRYPTION_SALT",
                    generate=lambda: os.urandom(32).hex(),
                    require_persisted=True,
                )
            except Exception as exc:
                logger.error("部署盐值无法持久化，拒绝使用进程内临时盐值: %s", exc)
                raise RuntimeError(
                    "部署盐值初始化失败：无法读写 runtime_secrets.json。"
                    "使用临时盐值会让重启后旧密文永久不可解，故直接失败。"
                ) from exc
            cls._deployment_salt = bytes.fromhex(salt_hex)
        return cls._deployment_salt

    def _derive_key_from_password(self, password: str, salt: bytes = None) -> bytes:
        """
        从密码派生密钥（PBKDF2-SHA256，≥600,000次迭代 — OWASP 2023基线）

        Args:
            password: 密码
            salt: 盐值（不提供则使用部署唯一持久化盐值）

        Returns:
            密钥
        """
        if salt is None:
            salt = self._load_deployment_salt()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,  # OWASP 2023 推荐最低迭代次数
        )

        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def encrypt_data(self, data: bytes) -> bytes:
        """
        加密数据

        Args:
            data: 原始数据

        Returns:
            加密后的数据
        """
        return self.cipher.encrypt(data)

    def decrypt_data(self, encrypted_data: bytes) -> bytes:
        """
        解密数据

        Args:
            encrypted_data: 加密数据

        Returns:
            解密后的数据
        """
        return self.cipher.decrypt(encrypted_data)

    def encrypt_file(self, file_path: str, output_path: str = None) -> str:
        """
        加密文件

        Args:
            file_path: 原始文件路径
            output_path: 输出文件路径（如果不提供，在原文件名后加.enc）

        Returns:
            加密后的文件路径
        """
        if output_path is None:
            output_path = file_path + ".enc"

        # 读取文件
        with open(file_path, "rb") as f:
            data = f.read()

        # 加密
        encrypted_data = self.encrypt_data(data)

        # 写入加密文件
        with open(output_path, "wb") as f:
            f.write(encrypted_data)

        return output_path

    def decrypt_file(self, encrypted_file_path: str, output_path: str) -> str:
        """
        解密文件

        Args:
            encrypted_file_path: 加密文件路径
            output_path: 输出文件路径

        Returns:
            解密后的文件路径
        """
        # 读取加密文件
        with open(encrypted_file_path, "rb") as f:
            encrypted_data = f.read()

        # 解密
        data = self.decrypt_data(encrypted_data)

        # 写入解密文件
        with open(output_path, "wb") as f:
            f.write(data)

        return output_path

    def get_key_string(self) -> str:
        """
        获取密钥字符串（用于保存）

        Returns:
            密钥字符串
        """
        return self.key.decode()

    @staticmethod
    def from_key_string(key_string: str) -> "DataPackageEncryption":
        """
        从密钥字符串创建加密工具

        Args:
            key_string: 密钥字符串

        Returns:
            加密工具实例
        """
        return DataPackageEncryption(key=key_string.encode())


def calculate_file_checksum(file_path: str, algorithm: str = "sha256") -> str:
    """
    计算文件校验和

    Args:
        file_path: 文件路径
        algorithm: 算法（sha256 推荐; sha1 仅用于非安全场景; md5 已弃用，仅保留兼容性）

    Returns:
        校验和字符串

    .. warning::
        MD5 已被证明不安全，请勿用于密码哈希、数字签名等安全场景。
        此处保留 MD5 选项仅为兼容旧数据包校验/缓存键等非安全用途。
        新代码应使用 sha256。
    """
    if algorithm == "md5":
        # nosec B324 -- MD5 仅用于文件校验/缓存键，非安全场景
        logger.warning("MD5 算法已弃用，建议使用 sha256; 当前调用仅用于非安全场景")
        hash_func = hashlib.md5(usedforsecurity=False)  # nosec B324
    elif algorithm == "sha1":
        hash_func = hashlib.sha1(usedforsecurity=False)
    elif algorithm == "sha256":
        hash_func = hashlib.sha256()
    else:
        raise ValueError(f"不支持的算法: {algorithm}")

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)

    return f"{algorithm}:{hash_func.hexdigest()}"


def verify_file_checksum(file_path: str, checksum: str) -> bool:
    """
    验证文件校验和

    Args:
        file_path: 文件路径
        checksum: 校验和字符串（格式：algorithm:hash）

    Returns:
        是否验证通过
    """
    try:
        algorithm, expected_hash = checksum.split(":")
        actual_checksum = calculate_file_checksum(file_path, algorithm)
        return actual_checksum == checksum
    except ValueError as e:
        # 校验和格式错误
        logger.warning(f"Invalid checksum format: {checksum}, error: {e}")
        return False
    except (IOError, OSError) as e:
        # 文件读取错误
        logger.error(f"File I/O error during checksum verification: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during checksum verification: {e}", exc_info=True)
        return False


def generate_encryption_key() -> str:
    """
    生成加密密钥

    Returns:
        密钥字符串
    """
    key = Fernet.generate_key()
    return key.decode()
