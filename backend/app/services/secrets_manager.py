"""
密钥管理服务

提供密钥的安全存储和管理
"""

from typing import Optional, List, Dict, Any
import os
import secrets
import time


class SecretsManager:
    """
    密钥管理服务

    管理应用程序的密钥和敏感信息
    """

    def __init__(self):
        self._secrets = {}
        self._key_versions = []
        self._init_default_key()

    def _init_default_key(self):
        """初始化默认密钥（持久化到文件，避免重启后数据不可恢复）

        兜底密钥必须是**合法 Fernet key**（44 字符 urlsafe-base64 且解码后 32 字节），
        否则 key_type 声明为 fernet 而实际不可用，调用方 Fernet(key) 会在运行时
        抛 ValueError（深审 #52）。
        """
        default_key = os.getenv("ENCRYPTION_KEY")
        if not default_key:
            key_file = os.path.join(
                os.getenv("LOCALAPPDATA", os.path.expanduser("~")),
                "bumofu-assistance", "data", ".secrets_manager_key",
            )
            try:
                os.makedirs(os.path.dirname(key_file), exist_ok=True)
                if os.path.exists(key_file):
                    with open(key_file, "r", encoding="utf-8") as f:
                        default_key = f.read().strip()
                else:
                    from cryptography.fernet import Fernet
                    default_key = Fernet.generate_key().decode()
                    with open(key_file, "w", encoding="utf-8") as f:
                        f.write(default_key)
            except ImportError:  # pragma: no cover - 可选依赖未安装时的功能降级分支
                default_key = self._generate_fallback_key()
            except Exception:
                # 磁盘不可写/权限不足：仍需给出可用的 Fernet key
                default_key = self._generate_fallback_key()
        self._secrets["default"] = default_key
        self._key_versions.append(
            {"version_id": "v1", "created_at": time.time(), "is_active": True, "key_type": "fernet"}
        )

    @staticmethod
    def _generate_fallback_key() -> str:
        """生成合法 Fernet key；cryptography 不可用时退化为等长 base64 随机串。

        退化分支仅为"极端环境不崩溃"兜底，且会记录 WARNING ——
        与 cryptography 缺失时 rotate_key/create_key 本身就会 ImportError 保持一致，
        不掩盖问题。
        """
        try:
            from cryptography.fernet import Fernet
            return Fernet.generate_key().decode()
        except ImportError:  # pragma: no cover - 可选依赖未安装时的功能降级分支
            import base64
            import logging
            logging.getLogger(__name__).warning(
                "cryptography 不可用，默认密钥退化为非 Fernet 随机串"
            )
            return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """获取密钥"""
        return self._secrets.get(key, default) or os.getenv(key, default)

    def set_secret(self, key: str, value: str):
        """设置密钥"""
        self._secrets[key] = value

    def delete_secret(self, key: str) -> bool:
        """删除密钥"""
        if key in self._secrets:
            del self._secrets[key]
            return True
        return False

    def list_key_versions(self) -> List[Dict[str, Any]]:
        """列出所有密钥版本"""
        return sorted(self._key_versions, key=lambda x: x.get("created_at", 0), reverse=True)

    def rotate_key(self, version_id: Optional[str] = None) -> str:
        """
        轮换密钥

        Args:
            version_id: 要轮换的密钥版本，None表示轮换当前活跃密钥

        Returns:
            新密钥版本ID
        """
        from cryptography.fernet import Fernet

        # 生成新密钥
        new_key = Fernet.generate_key().decode()

        # 创建新版本ID
        new_version_id = f"v{len(self._key_versions) + 1}_{int(time.time())}"

        # 保存新密钥
        self._secrets[new_version_id] = new_key

        # 添加到版本列表
        self._key_versions.append(
            {"version_id": new_version_id, "created_at": time.time(), "is_active": True, "key_type": "fernet"}
        )

        # 停用旧版本
        if version_id:
            for v in self._key_versions:
                if v["version_id"] == version_id:
                    v["is_active"] = False
        else:
            # 停用所有其他版本
            for v in self._key_versions:
                if v["version_id"] != new_version_id:
                    v["is_active"] = False

        return new_version_id

    def create_key(self, key_type: str = "fernet", expires_days: Optional[int] = None) -> str:
        """
        创建新密钥

        Args:
            key_type: 密钥类型 (fernet, aes, etc.)
            expires_days: 过期天数

        Returns:
            新版本ID
        """
        from cryptography.fernet import Fernet

        if key_type == "fernet":
            new_key = Fernet.generate_key().decode()
        else:
            # 其他类型生成随机密钥
            new_key = secrets.token_urlsafe(32)

        version_id = f"v{len(self._key_versions) + 1}_{int(time.time())}"

        self._secrets[version_id] = new_key

        key_info = {"version_id": version_id, "created_at": time.time(), "is_active": True, "key_type": key_type}

        if expires_days:
            key_info["expires_at"] = time.time() + (expires_days * 86400)

        self._key_versions.append(key_info)

        return version_id

    def revoke_key(self, version_id: str) -> bool:
        """
        撤销密钥

        Args:
            version_id: 要撤销的密钥版本ID

        Returns:
            是否成功撤销
        """
        for v in self._key_versions:
            if v["version_id"] == version_id:
                v["is_active"] = False
                v["revoked_at"] = time.time()
                return True
        return False

    def cleanup_expired_keys(self, keep_days: int = 90) -> int:
        """
        清理过期密钥

        Args:
            keep_days: 保留天数

        Returns:
            删除的密钥数量
        """
        cutoff_time = time.time() - (keep_days * 86400)
        deleted_count = 0

        versions_to_remove = []
        for v in self._key_versions:
            # 检查是否过期或已撤销且超过保留期
            if not v.get("is_active"):
                revoked_at = v.get("revoked_at", 0)
                created_at = v.get("created_at", 0)

                if revoked_at < cutoff_time and created_at < cutoff_time:
                    versions_to_remove.append(v["version_id"])

        remove_set = set(versions_to_remove)
        self._key_versions = [v for v in self._key_versions if v["version_id"] not in remove_set]
        for vid in remove_set:
            self._secrets.pop(vid, None)
        deleted_count = len(remove_set)

        return deleted_count


# 全局实例
secrets_manager = SecretsManager()
