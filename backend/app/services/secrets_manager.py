"""
密钥管理服务

提供密钥的安全存储和管理

M23（2026-10-14 系统排查）：密钥版本**必须持久化**。
旧实现把 rotate_key / create_key 生成的密钥只存内存（self._secrets），
重启后 _key_versions 清空、历史版本密钥丢失 —— 用旧版本密钥加密的数据
将永远无法解密（数据不可逆级缺陷）。现落“受保护文件”
（LOCALAPPDATA/bumofu-assistance/data/.secrets_manager_keys.json，0600，
原子替换），启动时加载，重启后历史版本仍可解密。
"""

import json
import logging
import os
import secrets
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 受保护密钥库文件名（与历史单密钥文件 .secrets_manager_key 同目录）
KEYS_FILE_NAME = ".secrets_manager_keys.json"

# 版本记录中属于“元数据”的键（密钥本体单独存于同文件的 key 字段）
_VERSION_META_KEYS = ("version_id", "created_at", "is_active", "key_type")


class SecretsManager:
    """
    密钥管理服务

    管理应用程序的密钥和敏感信息
    """

    def __init__(self):
        self._secrets = {}
        self._key_versions = []
        self._init_default_key()

    # ------------------------------------------------------------------
    # 持久化（M23）
    # ------------------------------------------------------------------

    def _keys_file_path(self) -> str:
        """受保护密钥库路径（与默认密钥文件同目录）。"""
        return os.path.join(
            os.getenv("LOCALAPPDATA", os.path.expanduser("~")),
            "bumofu-assistance", "data", KEYS_FILE_NAME,
        )

    def _load_key_store(self) -> Optional[Dict[str, Any]]:
        """从受保护文件加载密钥库；不存在/损坏时返回 None（退回内存态）。"""
        path = self._keys_file_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        versions = data.get("versions")
        default_key = data.get("default_key")
        if not isinstance(versions, list) or not isinstance(default_key, str) or not default_key:
            return None
        return {"default_key": default_key, "versions": versions}

    def _persist_key_store(self) -> None:
        """把当前密钥库原子写入受保护文件（失败仅告警，保持内存态不中断业务）。"""
        versions = []
        for v in self._key_versions:
            entry = {k: v[k] for k in _VERSION_META_KEYS if k in v}
            for extra in ("expires_at", "revoked_at"):
                if extra in v:
                    entry[extra] = v[extra]
            entry["key"] = self._secrets.get(v["version_id"])
            versions.append(entry)
        data = {"default_key": self._secrets.get("default"), "versions": versions}

        path = self._keys_file_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            try:
                os.chmod(tmp_path, 0o600)  # 仅属主可读写
            except OSError:  # pragma: no cover - Windows 上 chmod 语义有限
                pass
            os.replace(tmp_path, path)  # 原子替换，避免半截文件
        except OSError:
            logger.warning("密钥库持久化失败（%s），本次仅在内存中生效", path, exc_info=True)

    def _init_default_key(self):
        """初始化默认密钥（持久化到文件，避免重启后数据不可恢复）

        兜底密钥必须是**合法 Fernet key**（44 字符 urlsafe-base64 且解码后 32 字节），
        否则 key_type 声明为 fernet 而实际不可用，调用方 Fernet(key) 会在运行时
        抛 ValueError（深审 #52）。

        M23：本方法同时从受保护密钥库加载历史版本（rotate_key 落盘的版本），
        使重启后 _key_versions 不清空、历史版本密钥仍可用于解密。
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
            except Exception as exc:  # noqa: BLE001 - 兜底但必须留痕
                logger.warning('_init_default_key 兜底失败（已降级）: %s', exc, exc_info=True)
                # 磁盘不可写/权限不足：仍需给出可用的 Fernet key
                default_key = self._generate_fallback_key()
        self._secrets["default"] = default_key

        # M23：加载持久化的密钥库（ENCRYPTION_KEY 显式指定时操作者意图优先，
        # 仍加载历史版本 —— 否则轮换过的版本在重启后照样丢失）。
        store = self._load_key_store()
        if store is not None:
            if not os.getenv("ENCRYPTION_KEY"):
                # 环境变量未指定默认密钥时，以持久化的 default 为准
                # （可能与旧版单密钥文件不同：库里的 default 是最新持久态）
                self._secrets["default"] = store["default_key"]
            loaded = 0
            for v in store["versions"]:
                if not isinstance(v, dict):
                    continue
                version_id = v.get("version_id")
                key_material = v.get("key")
                if not version_id or not key_material:
                    continue
                self._secrets[version_id] = key_material
                entry = {k: v[k] for k in _VERSION_META_KEYS if k in v}
                for extra in ("expires_at", "revoked_at"):
                    if extra in v:
                        entry[extra] = v[extra]
                self._key_versions.append(entry)
                loaded += 1
            if loaded:
                logger.info("已从密钥库加载 %d 个历史密钥版本", loaded)
                return

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

        # M23：落受保护文件，重启后新版本仍可解密
        self._persist_key_store()
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

        # M23：落受保护文件，重启后新版本仍可解密
        self._persist_key_store()
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
                # M23：撤销状态同样持久化，避免重启后“已撤销”被复活
                self._persist_key_store()
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

        # M23：清理结果持久化，避免重启后已清理密钥复活
        if deleted_count:
            self._persist_key_store()

        return deleted_count


# 全局实例
secrets_manager = SecretsManager()
