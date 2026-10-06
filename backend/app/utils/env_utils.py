"""环境变量解析工具（单一事实源）。

集中处理「环境变量是字符串、代码要整数」这类解析：
非法值必须**回退默认并记 warning**，而不是抛未捕获异常 ——
本仓库曾因此吃过两次苦：

- ``BACKUP_COMPRESSION_LEVEL`` 非数字 → 每次构造 ``BackupService`` 即抛
  ``ValueError`` → 备份创建/列表/清理整条链路失效；
- ``ACCESS_TOKEN_EXPIRE_MINUTES`` / ``REFRESH_TOKEN_EXPIRE_DAYS`` 在 ``security``
  **模块导入期**解析 → 一处笔误直接让整个后端无法启动（且报错是 ImportError，
  排查成本极高）。

原先该逻辑以私有函数 ``core/database._parse_env_int`` 的形式只存在于 DB 模块，
其余调用点各自为政（有的裸 ``int()``、有的就地 try）。现收敛到本模块。
"""

import logging
import os

logger = logging.getLogger(__name__)


def parse_env_int(name: str, default: int) -> int:
    """读取环境变量 ``name`` 并转为 ``int``；缺失/非数字时回退 ``default``。

    Args:
        name: 环境变量名
        default: 缺失或非法时使用的默认值

    Returns:
        解析后的整数（非法值一律返回 ``default`` 并记 warning，绝不抛异常）
    """
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("%s=%r 不是有效整数，使用默认值 %d", name, raw, default)
        return default
