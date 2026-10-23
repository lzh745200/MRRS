"""实体写操作的审批门控 —— 「真门禁」（W27）。

## 背景：W26 全栈检测跨域共性问题 C2「审批伪闭环」

帮扶村 / 学校 / 政策三类实体的写操作此前都会调用
:func:`~app.services.approval_workflow_service.submit_entity_change_approval`
创建审批任务，但：

* 对应的回写处理器是空实现 ``_ = (db, task)``；
* 变更在写库时**已即时生效**（创建/更新即刻落库，驳回也不回滚）。

结果：审批中心里的「通过 / 驳回」对这三类实体**零效果**，纯装饰；且审批队列被
"发布/归档/导入/恢复"等通知塞满。**审计员会误以为"未审批不得生效"**。

## 真门禁语义

* **管理员（``is_admin``）→ 直通**：立即生效。
  理由：单机部署里常见"一人既是录入者又是审批者"，若管理员也必须走审批会形成
  自我审批死锁；且管理员已具备回收站/彻底删除等高风险能力，直通不降低安全性。
  直通路径仍写审计留痕。
* **非管理员 → 门控**：变更**不落库**，只登记一条待审批任务（携带 ``change_data``
  与 ``original_data``）。审批**通过**后由注册的 apply handler 真正写入；
  **驳回**则什么都不发生（实体保持原值）。
* **创建类操作不门控**：新增是增量操作，且门控创建需要"占位实体"机制
  （实体尚无 id，审批任务无法引用），故创建即时生效，并**不再**创建审批任务
  —— 避免伪任务污染审批队列。

## ``change_data`` 约定

| 操作 | change_data |
|---|---|
| 更新 | 待应用字段的**扁平字典**（便于审批页做字段级 diff） |
| 删除 | ``{"__deleted__": True}`` |
| 恢复 | ``{"__restored__": True}`` |

保留键以双下划线开头；实体字段名均为普通 snake_case，不会冲突。
"""

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.core.permission_utils import is_admin
from app.services.approval_workflow_service import submit_entity_change_approval

logger = logging.getLogger(__name__)

# 保留键：标记"这不是字段更新，而是删除/恢复语义"
DELETED_KEY = "__deleted__"
RESTORED_KEY = "__restored__"

# 应用变更时永不覆盖的字段（主键与归属审计列）
_IMMUTABLE_FIELDS = frozenset({"id", "created_by", "created_at", "organization_id"})


def requires_approval(current_user) -> bool:
    """该用户的操作是否需要走审批门。

    管理员直通（单机运维闭环），其余一律门控。
    """
    return not is_admin(current_user)


def open_change_approval(
    db,
    *,
    current_user,
    entity_type: str,
    entity_id: int,
    title: str,
    change_data: Optional[Dict[str, Any]] = None,
    original_data: Optional[Dict[str, Any]] = None,
) -> int:
    """登记一条待审批变更，返回任务 id。

    门控路径下**不写入实体**，只创建审批任务。若无法创建任务（无启用中的工作流
    且自动建流程失败），必须**拒绝整次请求** —— 否则会出现"既没落库也没审批任务"
    的静默丢失。

    Raises:
        HTTPException(400): 无法创建审批任务。
    """
    task_id = submit_entity_change_approval(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        submitter_id=getattr(current_user, "id", None),
        title=title,
        change_data=change_data,
        original_data=original_data,
    )
    if task_id is None:
        logger.error(
            "审批门控：无法为 %s#%s 创建审批任务，已拒绝本次变更", entity_type, entity_id
        )
        raise HTTPException(
            status_code=400,
            detail="变更已提交审批但无法创建审批任务，请检查是否存在启用中的审批流程后重试",
        )
    return task_id


def apply_field_changes(record, change_data: Optional[Dict[str, Any]]) -> int:
    """把 ``change_data`` 中的字段真正写入 *record*，返回应用字段数。

    * 跳过以 ``__`` 开头的保留键（删除/恢复标记）、主键与归属审计列；
    * 模型上不存在的字段记 WARNING 并跳过（与既有 update 行为一致，防字段漂移静默）；
    * 不做 commit —— 由调用方（apply handler）在事务边界内统一提交。
    """
    applied = 0
    for key, value in (change_data or {}).items():
        if not isinstance(key, str) or key.startswith("__"):
            continue
        if key in _IMMUTABLE_FIELDS:
            logger.warning("审批回写：忽略不可变字段 %s", key)
            continue
        if hasattr(record, key):
            setattr(record, key, value)
            applied += 1
        else:
            logger.warning("审批回写：字段 %s 在模型上不存在，已跳过", key)
    return applied


def is_delete_marker(change_data: Optional[Dict[str, Any]]) -> bool:
    """``change_data`` 是否表示"删除"语义。"""
    return bool((change_data or {}).get(DELETED_KEY))


def is_restore_marker(change_data: Optional[Dict[str, Any]]) -> bool:
    """``change_data`` 是否表示"恢复"语义。"""
    return bool((change_data or {}).get(RESTORED_KEY))
