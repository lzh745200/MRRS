"""审计/日志大表保留期清理（W5-T8）。

背景（检测 P1-3）：六张审计/日志表只增不减 —— ``audit_logs``（操作审计）、
``api_access_logs``（逐请求访问日志，H9 前为每请求一写）、``login_attempts``、
``security_events``、``data_export_logs``、``token_blacklist``。长期运行下库体积、
WAL 与索引维护成本持续上升（备份/体检/迁移变慢），而军事审计只要求「保留期内
可追溯」，不要求永久保留全部原始请求日志。

策略（与 ``backup_retention_days`` 同口径：按天、可配置、超期即删）：

- ``audit_logs`` 默认 180 天；``api_access_logs`` 默认 180 天（量最大的一档）；
- ``login_attempts`` 默认 90 天（登录失败排查窗口足够）；
- ``security_events`` / ``data_export_logs`` 默认 365 天（安全事件与数据出站
  留痕属合规追溯材料，保留期最长）；
- ``token_blacklist`` 删除已过期条目（``expires_at < now``）；``expires_at IS
  NULL`` 表示**永久吊销**（W1 安全不变量），绝不删除；
- 保留期 <= 0 视为禁用该表清理（与 ``BackupService.cleanup_by_retention_days``
  同语义，防误配 0 造成整表清空）。

时间基准：相关列均为 ``UtcDateTime``（naive UTC 存储 / aware UTC 读回），截止点
必须取 ``time_utils.utcnow()``；用本地 ``datetime.now()`` 会整体偏一个时区差
（UTC+8 晚删 8 小时，与 user_sessions 清理同口径）。

提交语义：``get_db()`` 成功路径只 close 不 commit，删除必须显式提交，否则会话
关闭时隐式回滚、清理静默失效。本模块在删除后统一 ``safe_commit``；任一步失败
即抛给调用方（调度作业记日志并吞掉，下个周期重试）。
"""

import logging
from datetime import datetime, timedelta
from typing import Mapping

from app.core.transaction import safe_commit
from app.models.audit import (
    APIAccessLog,
    AuditLog,
    DataExportLog,
    LoginAttempt,
    SecurityEvent,
)
from app.models.token_blacklist import TokenBlacklist
from app.utils.time_utils import utcnow

logger = logging.getLogger(__name__)

# 各表保留期默认值（天）。键同时是 SystemConfig 配置键（见
# SystemConfigService.DEFAULT_CONFIGS），可由配置覆盖；0/负数 = 禁用该表清理。
DEFAULT_RETENTION_DAYS: dict[str, int] = {
    "audit_log_retention_days": 180,
    "api_access_log_retention_days": 180,
    "login_attempt_retention_days": 90,
    "security_event_retention_days": 365,
    "data_export_log_retention_days": 365,
}

# 表清理清单：(配置键, 结果标签, 模型, 时间列)
_RETENTION_TABLES = (
    ("audit_log_retention_days", "audit_logs", AuditLog, AuditLog.created_at),
    ("api_access_log_retention_days", "api_access_logs", APIAccessLog, APIAccessLog.created_at),
    ("login_attempt_retention_days", "login_attempts", LoginAttempt, LoginAttempt.attempt_time),
    ("security_event_retention_days", "security_events", SecurityEvent, SecurityEvent.created_at),
    ("data_export_log_retention_days", "data_export_logs", DataExportLog, DataExportLog.created_at),
)


def purge_expired_audit_rows(
    db,
    retention_days: Mapping[str, int],
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """按保留期删除超期审计/日志行，返回 ``{表名: 删除行数}``。

    Args:
        db: SQLAlchemy 会话（删除后由本函数提交）。
        retention_days: 配置键 -> 保留天数。键缺省时回退到
            :data:`DEFAULT_RETENTION_DAYS`（而非 0/禁用），避免调用方漏传键
            导致某表静默不再清理；显式传 0/负数才是禁用。
        now: 时间基准（默认真实 UTC 当前时刻）；测试注入固定时刻用。

    Returns:
        每个表/清理项的删除行数，键为 ``audit_logs`` / ``api_access_logs`` /
        ``login_attempts`` / ``security_events`` / ``data_export_logs`` /
        ``token_blacklist``。

    判定为**严格早于**截止点（``时间列 < now - retention_days``）：恰好落在
    截止点上的行保留（``<`` 而非 ``<=``），与备份保留期清理一致。
    """
    cutoff_base = now or utcnow()
    counts: dict[str, int] = {}

    for config_key, label, model, column in _RETENTION_TABLES:
        days = retention_days.get(config_key, DEFAULT_RETENTION_DAYS[config_key])
        if days <= 0:
            # 0/负数 = 显式禁用该表清理（防误配清空整表），与备份保留期同语义
            counts[label] = 0
            continue
        cutoff = cutoff_base - timedelta(days=days)
        counts[label] = db.query(model).filter(column < cutoff).delete(synchronize_session=False)

    # token_blacklist：只删「已过期」条目。expires_at IS NULL = 永久吊销（W1
    # 安全不变量），任何情况下都不得删除，否则已吊销令牌在重启装载后复活。
    counts["token_blacklist"] = (
        db.query(TokenBlacklist)
        .filter(TokenBlacklist.expires_at.isnot(None), TokenBlacklist.expires_at < cutoff_base)
        .delete(synchronize_session=False)
    )

    safe_commit(db)
    return counts
