"""时间基准统一工具（本项目唯一口径，Single Source of Truth）。

## 约定

1. **持久化一律 naive UTC**
   所有 ``DateTime`` 列写入 naive UTC：ORM 默认值由 ``models.base._utcnow()``
   提供（timezone-aware UTC），但 SQLite 的 ``DateTime`` 不保存时区，落库时
   偏移被丢弃、读回即为 naive —— 其**语义是 UTC**。

2. **比较必须同基准**
   任何「与当前时刻比较」都必须用 :func:`utcnow`（aware UTC）或
   :func:`utcnow_naive`（naive UTC），**禁止**用 ``datetime.now()``（本机本地
   时间，naive）去和库中读回的值比较 —— 非 UTC 主机（如 UTC+8）上会产生固定
   偏移。历史上已两次踩坑：

   * ``user_management`` 审批超时提醒：阈值与 ``elapsed_hours`` 整体偏移 8 小时，
     超时提醒晚 8 小时才触发（见 ``services/reminder_engine.py`` 注释）；
   * 报表订阅 ``next_send_at`` / 到期派发：派发任务传本地 ``datetime.now()``，
     与 UTC 基准算出的 ``due_at`` 比较 → 新建订阅可能被提前派发，且列表返回的
     ``next_send_at`` 会落到本地过去时刻（2026-10-02 修复）。

3. **面向用户的调度语义按本机本地时区解释**
   用户配置「每天 08:00 发送」意指**本地** 08:00，而非 08:00 UTC。因此调度计算
   须先把 UTC 基准转本地（:func:`to_local`）、用本地时间做日历运算，再用
   :func:`to_utc` 转回 UTC 存储/传输，使前端展示回本地 08:00。

## 刻意保留的例外

`SystemConfig` 中少数**文本**时间戳（`last_backup_time`、`last_package_time`）以
**本地墙钟**字符串存储，并与本地 `datetime.now()` 做日历比较 —— 读写自洽、无错位，
且 `last_package_time` 的「月份间隔」判定依赖**本地日历**字段（改 UTC 会跨月边界），
故保持不变。它们不是 `DateTime` 列，不受 `UtcDateTime` 影响。

本模块是上述转换的唯一入口；此前 ``services/reminder_engine.py`` 与
``services/async_export_service.py`` 各有一份私有 ``_as_utc``，已统一到此。
"""

from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    """当前时刻（timezone-aware UTC）。替代 ``datetime.now()`` 用于与库中值比较。"""
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    """当前时刻的 naive UTC，用于写入 ``DateTime`` 列。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """把库中读回的时间统一为 aware UTC。

    naive 值按约定视为 UTC 语义（见模块文档）；aware 值统一换算到 UTC。
    ``None`` 原样返回，便于直接用于可空列；已是 UTC 的对象**原样返回**（保持
    对象恒等，调用方可安全地做 ``is`` 比较/复用）。
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    if value.tzinfo == timezone.utc:
        return value
    return value.astimezone(timezone.utc)


def as_utc_naive(value: Optional[datetime]) -> Optional[datetime]:
    """把任意来源的时间统一为 naive UTC（写库用）。"""
    converted = as_utc(value)
    return None if converted is None else converted.replace(tzinfo=None)


def to_local(value: Optional[datetime]) -> Optional[datetime]:
    """把库中读回的时间转换为 aware 本地时间。

    naive 值先按 UTC 语义补齐（见 :func:`as_utc`），再换算到本机时区。
    返回 aware 值，可直接与 ``datetime.now().astimezone()`` 比较。
    """
    converted = as_utc(value)
    return None if converted is None else converted.astimezone()


def local_naive(value: datetime) -> datetime:
    """把库中读回的 naive UTC 转换为**本地墙钟**（naive，无时区）。

    用于「按本地日历语义做运算」的场景（如报表订阅的 send_day/send_time）：
    ``next_run_at`` 这类纯日历函数只认墙钟，不认时区。
    本函数不接受 None（调用方需先判空），因此无 Optional 分支。
    """
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone().replace(tzinfo=None)


def local_naive_to_utc(value: datetime) -> datetime:
    """把**本地墙钟**（naive）解释为本地时刻并换算成 aware UTC。

    与 :func:`to_utc` 的差别：本函数不接受 None，供已判空的内部链路使用。
    """
    aware = value if value.tzinfo is not None else value.astimezone()
    return aware.astimezone(timezone.utc)


def to_utc(value: Optional[datetime]) -> Optional[datetime]:
    """把本地/未知基准的时间转换为 aware UTC。

    naive 值按**本地**时区解释（与 :func:`as_utc` 的 naive 视为 UTC 相反），
    用于把以本地时间算出的调度结果转回 UTC 传输/存储。
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.astimezone().astimezone(timezone.utc)
    return value.astimezone(timezone.utc)


def to_utc_naive(value: Optional[datetime]) -> Optional[datetime]:
    """把本地/未知基准的时间转换为 naive UTC（写库用）。"""
    converted = to_utc(value)
    return None if converted is None else converted.replace(tzinfo=None)


def now_local() -> datetime:
    """当前时刻的 aware 本地时间。"""
    return datetime.now().astimezone()
