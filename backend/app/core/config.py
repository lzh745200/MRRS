"""
应用配置管理
从环境变量读取配置
完全离线单机版 - 无外部服务依赖
"""

import json as _json
import sys
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_default_data_dir() -> str:
    """获取默认数据目录（解决 Windows 安装版权限问题）"""
    # 使用统一的路径工具模块
    from app.utils.paths import get_app_data_dir

    data_dir = get_app_data_dir() / "data"
    return str(data_dir).replace("\\", "/")


def _get_default_database_url() -> str:
    """获取默认数据库 URL"""
    from app.utils.paths import get_database_path

    db_path = get_database_path()
    # 转换为绝对路径字符串，确保使用正斜杠
    abs_path = str(db_path.absolute()).replace("\\", "/")
    return f"sqlite:///{abs_path}"


def _get_default_cache_dir() -> str:
    """获取默认缓存目录"""
    from app.utils.paths import get_cache_path

    cache_dir = get_cache_path()
    return str(cache_dir).replace("\\", "/")


def _get_default_uploads_dir() -> str:
    from app.utils.paths import get_uploads_path

    return str(get_uploads_path()).replace("\\", "/")


def _get_default_exports_dir() -> str:
    from app.utils.paths import get_app_data_dir

    return str(get_app_data_dir() / "exports").replace("\\", "/")


class Settings(BaseSettings):
    """应用设置 - 离线单机版"""

    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 基础配置
    PROJECT_NAME: str = "帮扶管理信息系统"
    # 优先从环境变量 PROJECT_VERSION 读取（Electron 从 package.json 注入），
    # 未设置时使用硬编码默认值
    PROJECT_VERSION: str = "1.11.3"
    API_PREFIX: str = "/api/v1"
    SECRET_KEY: str = ""  # 自动生成并持久化到 runtime_secrets.json（无需手动配置）
    ALGORITHM: str = "HS256"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # 加密密钥配置
    USE_ENCRYPTED_SECRETS: bool = False
    SECRETS_FILE_PATH: str = "./backend/secrets/encrypted_config.json"
    MASTER_KEY_PATH: str = "./backend/secrets/master.key"

    # 数据库配置 - 仅使用SQLite本地数据库
    # 动态计算默认路径以支持 Windows 安装版（使用 %APPDATA%）
    DATABASE_URL: str = ""  # 空字符串表示使用动态默认值，见 model_post_init

    # 数据库加密配置
    DB_ENCRYPTION_ENABLED: bool = False  # 默认关闭，需配合 sqlcipher3 使用
    DB_ENCRYPTION_KEY_PATH: str = "./config/db.key"

    # 字段加密密钥（用于 encrypt_field/decrypt_field）
    ENCRYPTION_KEY: str = ""  # 空字符串表示使用默认测试密钥
    # 加密后端: "aes256" (AES-256-GCM, 高安全推荐) | "fernet" (Fernet/AES-128-CBC, 兼容旧版)
    ENCRYPTION_BACKEND: str = "aes256"
    # 密钥派生方式: "pbkdf2" (PBKDF2-SHA256, 200000迭代, 推荐) | "raw" (直接使用密钥)
    ENCRYPTION_KEY_DERIVATION: str = "pbkdf2"

    # 数据库连接池配置
    # SQLite 走 QueuePool（见 core/database.py），WAL 模式支持多读者并发；
    # 压测表明 30 连接（20+10）在 50+ 并发时排队耗尽，扩大至 60 以留余量。
    DB_POOL_SIZE: int = 40
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True
    DB_ECHO: bool = False
    SLOW_QUERY_THRESHOLD_MS: float = 200.0  # 降低到 200ms

    # 服务器配置（默认仅监听本机回环地址，Electron 生产模式会强制注入 HOST=127.0.0.1）
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    # 是否信任 X-Forwarded-For / X-Real-IP 代理头。
    # 默认 False：桌面直连场景下这些头可被客户端任意伪造（限流键可被轮换绕过）；
    # 仅在部署于可信反向代理（如 Kylin 单机版 nginx）之后时置 true。
    TRUST_PROXY_HEADERS: bool = False

    # 本地缓存配置（替代Redis）
    CACHE_DIR: str = "./data/cache"
    CACHE_SIZE_LIMIT: int = 100  # MB

    # Redis配置（可选）
    REDIS_ENABLED: bool = False
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_MAX_CONNECTIONS: int = 50

    # 安全配置
    # 单机版 token 有效期收窄至 8 小时（安全基线要求 ≤8h）。
    # 结合 token_version 强制下线可进一步缓解会话泄露风险。
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8小时
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30天，单机版延长
    BCRYPT_ROUNDS: int = 12  # OWASP 建议 12 轮以上
    PASSWORD_EXPIRE_DAYS: int = 90  # 密码有效期（天）
    MAX_FAILED_LOGIN_ATTEMPTS: int = 5  # 最大登录失败次数
    ACCOUNT_LOCKOUT_MINUTES: int = 30  # 账户锁定时长（分钟）

    # CORS配置
    # 生产环境仅允许本机回环地址
    # 开发环境额外允许 Vite dev server (5173)
    CORS_ORIGINS: str = (
        "http://127.0.0.1:8000,http://localhost:8000,"
        "http://127.0.0.1:5173,http://localhost:5173"
    )

    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "GET,POST,PUT,DELETE,OPTIONS,PATCH"
    CORS_ALLOW_HEADERS: str = "Content-Type,Authorization,X-Requested-With,X-CSRF-Token"

    # CSRF配置
    # 启用后，所有状态变更请求（POST/PUT/DELETE/PATCH）需要携带有效的 CSRF token
    # 前端需先调用 /api/v1/auth/csrf-token 获取 token，并在请求头 X-CSRF-Token 中携带
    # 安全基线要求：即使单机部署也应启用 CSRF 保护，防止同源跨站请求攻击
    # 默认开启；如需临时关闭（如调试），可设置环境变量 CSRF_ENABLED=false
    CSRF_ENABLED: bool = True  # 安全基线：默认开启 CSRF 保护
    CSRF_SECRET_KEY: str = ""  # 留空时自动生成（与 SECRET_KEY 类似持久化到 runtime_secrets.json）

    # 速率限制配置
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"
    LOG_FORMAT: str = "json"
    LOG_ROTATION: str = "10 days"
    LOG_RETENTION: str = "30 days"
    LOG_MAX_SIZE_MB: int = 50  # 单个日志文件最大大小（MB）
    LOG_BACKUP_COUNT: int = 5  # 保留的日志备份文件数量

    # 文件上传配置
    UPLOAD_DIR: str = "./uploads"
    EXPORT_DIR: str = "./exports"  # 导出文件目录（cleanup.py 等模块使用）
    LOG_DIR: str = "./logs"  # 日志目录（cleanup.py 使用；与 LOG_FILE 同级目录）
    MAX_FILE_SIZE: int = 52428800  # 50MB
    ALLOWED_FILE_TYPES: str = "xlsx,xls,csv,pdf,jpg,jpeg,png,doc,docx,pptx"

    # 应用名称别名（email.py 等模块使用）
    APP_NAME: str = "帮扶管理信息系统"

    # 缓存配置
    CACHE_ENABLED: bool = True
    CACHE_DEFAULT_TTL: int = 3600
    CACHE_MAX_SIZE: int = 10000

    # 监控配置
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    HEALTH_CHECK_ENABLED: bool = True

    # 告警配置
    ALERT_EMAIL_RECIPIENTS: Optional[List[str]] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    ALERT_WEBHOOK_URL: Optional[str] = None
    ALERT_WEBHOOK_TYPE: str = "generic"  # generic, dingtalk, wecom

    # 启动时自动迁移（ALTER TABLE ADD COLUMN）
    # 设为 False 可禁用运行时自动 DDL，改用 Alembic 迁移管理
    # 注意：必须保持 True。部署环境的 SQLite 数据库可能缺少 is_active 等较新的列
    # （如 supported_villages.is_active / projects.is_active / funds.is_active），
    # 自动迁移会在启动时检测并 ALTER TABLE ADD COLUMN 补齐，避免运行时
    # OperationalError: no such column: xxx.is_active
    ENABLE_AUTO_MIGRATION: bool = True

    @property
    def CORS_ALLOWED_ORIGINS(self) -> List[str]:
        """获取CORS允许的源列表"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def cors_origins_list(self) -> List[str]:
        """获取CORS允许的源列表 (别名)"""
        return self.CORS_ALLOWED_ORIGINS

    @property
    def CORS_ALLOWED_METHODS(self) -> List[str]:
        """获取CORS允许的方法列表"""
        return [method.strip().upper() for method in self.CORS_ALLOW_METHODS.split(",")]

    @property
    def cors_allow_methods_list(self) -> List[str]:
        """获取CORS允许的方法列表 (别名)"""
        return self.CORS_ALLOWED_METHODS

    @property
    def CORS_ALLOWED_HEADERS(self) -> List[str]:
        """获取CORS允许的头部列表"""
        return [header.strip() for header in self.CORS_ALLOW_HEADERS.split(",")]

    @property
    def cors_allow_headers_list(self) -> List[str]:
        """获取CORS允许的头部列表 (别名)"""
        return self.CORS_ALLOWED_HEADERS

    @property
    def allowed_file_types_list(self) -> List[str]:
        """获取允许的文件类型列表"""
        return [ftype.strip().lower() for ftype in self.ALLOWED_FILE_TYPES.split(",")]

    def _load_encrypted_secrets(self) -> None:
        """从加密文件加载密钥"""
        try:
            secrets_file = Path(self.SECRETS_FILE_PATH)
            master_key_file = Path(self.MASTER_KEY_PATH)

            if not secrets_file.exists() or not master_key_file.exists():
                import logging

                logging.getLogger(__name__).warning(
                    f"加密密钥文件不存在: {secrets_file} 或 {master_key_file}，回退到环境变量"
                )
                return

            # 读取主密钥
            with open(master_key_file, "r") as f:
                master_key = f.read().strip()

            # 读取加密配置
            with open(secrets_file, "r") as f:
                encrypted_config = _json.load(f)

            # 解密配置
            from app.utils.encryption import DataPackageEncryption

            encryptor = DataPackageEncryption.from_key_string(master_key)

            for key, encrypted_value in encrypted_config.items():
                try:
                    decrypted_value = encryptor.decrypt_data(encrypted_value.encode())
                    decrypted_str = decrypted_value.decode("utf-8")

                    # 覆盖配置值
                    if key == "SECRET_KEY":
                        self.SECRET_KEY = decrypted_str
                    elif key == "CSRF_SECRET_KEY":
                        self.CSRF_SECRET_KEY = decrypted_str
                    elif key == "SMTP_PASSWORD":
                        # 如果有 SMTP 配置，解密后设置
                        setattr(self, key, decrypted_str)
                    elif key == "DB_ENCRYPTION_KEY":
                        setattr(self, key, decrypted_str)

                except Exception as e:
                    import logging

                    logging.getLogger(__name__).error(f"解密密钥 {key} 失败: {e}")

        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"加载加密密钥失败: {e}，回退到环境变量")

    def model_post_init(self, __context) -> None:
        """模型初始化后的钩子"""
        if self.USE_ENCRYPTED_SECRETS:
            self._load_encrypted_secrets()

        # 安全基线：生产环境强制关闭 SQL echo，避免敏感数据（身份证/手机号/资金）
        # 落入日志。即使 .env 误配 DB_ECHO=true，生产环境也强制降级为 False。
        if self.ENVIRONMENT == "production" and self.DB_ECHO:
            import logging

            logging.getLogger(__name__).warning(
                "DB_ECHO 在生产环境被强制关闭（防止敏感信息泄露到日志）"
            )
            self.DB_ECHO = False

        # 安全基线：生产环境检查字段加密密钥是否为空（使用默认测试密钥是安全风险）
        if self.ENVIRONMENT == "production" and not self.ENCRYPTION_KEY:
            # 自动从运行时密钥存储加载或生成持久化密钥（每台机器独立随机生成，
            # 跨重启保持，位于用户数据目录），避免使用任何硬编码默认密钥。
            try:
                from app.utils.runtime_secrets import get_or_create_secret

                self.ENCRYPTION_KEY = get_or_create_secret(
                    "ENCRYPTION_FERNET_KEY",
                    generate=lambda: _generate_fernet_key(),
                )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "ENCRYPTION_KEY 未配置且自动生成失败（%s），字段加密将使用进程内随机密钥——"
                    "重启后历史密文可能无法解密，请尽快通过环境变量或 .env 配置 ENCRYPTION_KEY",
                    exc,
                )

        # 动态设置数据目录路径（解决 Windows 安装版权限问题）
        # 首先获取默认数据目录，供后续使用
        data_dir = _get_default_data_dir()

        # 如果 DATABASE_URL 为空或相对路径，使用动态计算的数据目录
        if not self.DATABASE_URL:
            self.DATABASE_URL = _get_default_database_url()
        elif self.DATABASE_URL.startswith("sqlite:///./"):
            # 替换相对路径为绝对路径
            db_name = self.DATABASE_URL.replace("sqlite:///./", "").replace("data/", "")
            self.DATABASE_URL = f"sqlite:///{data_dir}/{db_name}"

        # 动态设置其他路径（如果不是绝对路径或环境变量已设置）
        if self.CACHE_DIR.startswith("./"):
            self.CACHE_DIR = f"{data_dir}/cache"
        if self.LOG_DIR.startswith("./"):
            # 日志也放在用户数据目录下
            if getattr(sys, "frozen", False):
                self.LOG_DIR = f"{data_dir}/logs"
                self.LOG_FILE = f"{data_dir}/logs/app.log"
        if self.UPLOAD_DIR.startswith("./"):
            self.UPLOAD_DIR = _get_default_uploads_dir()
        if self.EXPORT_DIR.startswith("./"):
            self.EXPORT_DIR = _get_default_exports_dir()
        # 额外安全网：如果 UPLOAD_DIR 仍然是相对路径（如 env var 设为 "uploads"），
        # 转换为绝对路径，避免在 Program Files 等只读目录下创建文件夹失败
        import os as _os
        if self.UPLOAD_DIR and not _os.path.isabs(self.UPLOAD_DIR):
            self.UPLOAD_DIR = _get_default_uploads_dir()
        if self.EXPORT_DIR and not _os.path.isabs(self.EXPORT_DIR):
            self.EXPORT_DIR = _get_default_exports_dir()
        if self.CACHE_DIR and not _os.path.isabs(self.CACHE_DIR):
            self.CACHE_DIR = _get_default_cache_dir()


# SECRET_KEY 安全校验：
# 无论 production 还是 dev，如果 SECRET_KEY 为空则自动生成并持久化到 runtime_secrets.json。
# 这避免了因 .env 文件路径不匹配（如从 backend/ 目录启动时找不到根目录 .env）导致启动崩溃。
from app.utils.runtime_secrets import ensure_runtime_secrets  # noqa: E402


def _generate_fernet_key() -> str:
    """生成 Fernet 格式密钥（延迟导入 cryptography，避免模块加载顺序问题）"""
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


ensure_runtime_secrets()

# 全局设置实例（在 ensure_runtime_secrets 之后实例化，确保能读取到环境变量）
settings = Settings()
