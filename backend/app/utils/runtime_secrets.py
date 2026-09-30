"""
运行时密钥管理模块

确保 SECRET_KEY / CSRF_SECRET_KEY 可用，支持自动生成和持久化。
用于开发环境或安装包异常启动时的密钥兜底。
"""

import json
import logging
import os
import secrets
import tempfile
from pathlib import Path

from app.utils.paths import get_data_path

_logger = logging.getLogger(__name__)


def ensure_runtime_secrets() -> None:
    """
    确保 SECRET_KEY 和 CSRF_SECRET_KEY 可用。

    策略：
    1. 若环境变量已提供，直接使用；
    2. 否则读取 runtime_secrets.json；
    3. 仍不存在则生成并原子落盘，随后注入到环境变量。
    """
    secret_key = os.environ.get("SECRET_KEY", "").strip()
    csrf_secret_key = os.environ.get("CSRF_SECRET_KEY", "").strip()

    # 验证已存在的密钥强度（至少 32 字符），弱密钥视为无效需重新生成
    _min_key_length = 32
    if secret_key and len(secret_key) < _min_key_length:
        _logger.warning(
            "环境变量 SECRET_KEY 长度不足（%d < %d），将被忽略并重新生成",
            len(secret_key), _min_key_length,
        )
        secret_key = ""
    if csrf_secret_key and len(csrf_secret_key) < _min_key_length:
        _logger.warning(
            "环境变量 CSRF_SECRET_KEY 长度不足（%d < %d），将被忽略并重新生成",
            len(csrf_secret_key), _min_key_length,
        )
        csrf_secret_key = ""

    if secret_key and csrf_secret_key:
        return

    secrets_file = _resolve_secrets_file()
    loaded: dict[str, str] = {}

    try:
        with open(secrets_file, "r", encoding="utf-8") as f:
            loaded = json.load(f) or {}
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as exc:
        _logger.warning("运行时密钥文件 JSON 格式损坏，将重新生成: %s", exc)
    except PermissionError as exc:
        _logger.warning("运行时密钥文件无读取权限，将使用进程内密钥: %s", exc)
    except Exception as exc:
        _logger.warning("读取运行时密钥文件失败，将重新生成: %s", exc)

    secret_key = secret_key or loaded.get("SECRET_KEY", "")
    csrf_secret_key = csrf_secret_key or loaded.get("CSRF_SECRET_KEY", "")

    changed = False
    if not secret_key:
        secret_key = secrets.token_urlsafe(48)
        changed = True
    if not csrf_secret_key:
        csrf_secret_key = secrets.token_urlsafe(48)
        changed = True

    os.environ["SECRET_KEY"] = secret_key
    os.environ["CSRF_SECRET_KEY"] = csrf_secret_key

    if changed:
        try:
            _atomic_write_json(
                secrets_file,
                {
                    "SECRET_KEY": secret_key,
                    "CSRF_SECRET_KEY": csrf_secret_key,
                },
            )
            _logger.info("已初始化运行时密钥文件: %s", secrets_file)
        except PermissionError as exc:
            _logger.warning("运行时密钥落盘失败（无写入权限），将仅使用进程内密钥: %s", exc)
        except Exception as exc:
            _logger.warning("运行时密钥落盘失败，将仅使用进程内密钥: %s", exc)


def get_or_create_secret(key: str, *, generate=None, require_persisted: bool = False) -> str:
    """获取或创建任意持久化密钥。

    从 runtime_secrets.json 读取指定 key，若不存在则调用 generate()
    生成新值、持久化并返回。

    Args:
        key: 密钥名称（如 "ENCRYPTION_FERNET_KEY"）
        generate: 无参回调函数，返回新密钥字符串。默认为 token_urlsafe(48)
        require_persisted: 为 True 时，读取/写入失败一律抛 RuntimeError，
            绝不用"进程内一次性密钥"顶替。用于**加密静态数据**的密钥：
            落盘失败时静默返回进程内值，会让历史密文在重启后永久无法解密
            （深审 critical）。默认 False 保持既有调用方语义。

    Returns:
        密钥字符串

    Raises:
        RuntimeError: require_persisted=True 且密钥无法读取/持久化。
    """
    if generate is None:
        def _default_generate() -> str:
            return secrets.token_urlsafe(48)
        generate = _default_generate

    secrets_file = _resolve_secrets_file()
    loaded: dict[str, str] = {}

    try:
        with open(secrets_file, "r", encoding="utf-8") as f:
            loaded = json.load(f) or {}
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, PermissionError) as exc:
        if require_persisted:
            # 文件存在却读不出来：若就此重新生成，会把既有密钥覆盖掉，
            # 历史密文同样不可解 —— 必须显式失败。
            raise RuntimeError(f"无法读取运行时密钥文件 {secrets_file}: {exc}") from exc
        _logger.warning("读取运行时密钥文件失败 (%s)，将重新生成 %s", exc, key)

    if key in loaded and loaded[key]:
        return loaded[key]

    new_value = generate()
    loaded[key] = new_value
    try:
        _atomic_write_json(secrets_file, loaded)
        _logger.info("已持久化新密钥 '%s' 到 %s", key, secrets_file)
    except Exception as exc:
        if require_persisted:
            raise RuntimeError(f"无法持久化密钥 {key} 到 {secrets_file}: {exc}") from exc
        _logger.warning("无法持久化密钥 '%s'，将仅使用进程内值: %s", key, exc)
    return new_value


def _resolve_secrets_file() -> Path:
    """解析 runtime_secrets.json 文件路径。"""
    if os.environ.get("RUNTIME_SECRETS_FILE"):
        return Path(os.environ["RUNTIME_SECRETS_FILE"])

    return get_data_path("runtime_secrets.json")


def _atomic_write_json(path: Path, data: dict) -> None:
    """原子写入 JSON 文件，并在 Unix 系统上限制文件权限为 0o600。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd = None
    tmp_path = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
        )
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        fd = None

        os.replace(tmp_path, path)
        tmp_path = None

        if os.name != "nt":  # pragma: no cover
            os.chmod(path, 0o600)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None and tmp_path.exists():
            try:
                os.remove(tmp_path)
            except OSError:
                pass
