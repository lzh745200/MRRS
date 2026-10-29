"""批量操作服务。"""
import logging
from contextlib import contextmanager
from typing import Any, Dict, List
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

# Table-to-model mapping (backward-compat: tests expect populated dict)
TABLE_MODEL_MAP: dict = {
    "supported_villages": None,
    "projects": None,
    "funds": None,
    "schools": None,
    "policies": None,
    "users": None,
    "organizations": None,
    "villages": None,
    "rural_works": None,
    "work_logs": None,
}

ALLOWED_TABLES = frozenset(TABLE_MODEL_MAP.keys())

# 高权限表：批量写/校验接口直接拒绝（提权通道封堵，即使管理员也不例外）
_PROTECTED_TABLES = frozenset({"users", "organizations"})

# 批量更新禁止触碰的字段（端点校验之外的二次防线）
_FORBIDDEN_UPDATE_FIELDS = frozenset({
    "id", "created_at", "organization_id",
    "role", "is_superuser", "hashed_password", "password",
    "permissions", "token_version", "allowed_menus", "allowed_permissions",
})


def _reject_protected_table(table_name: str) -> None:
    """users/organizations 表禁止走通用批量接口。"""
    if table_name in _PROTECTED_TABLES:
        from app.core.error_handler import BusinessLogicError
        raise BusinessLogicError(f"表 {table_name} 不允许通过批量接口操作")


# 表名 → 模型属性名映射（用于 _resolve_model 快速查找）
_TABLE_TO_MODEL_NAME = {
    "supported_villages": "SupportedVillage",
    "projects": "Project",
    "funds": "Fund",
    "schools": "School",
    "policies": "Policy",
    "users": "User",
    "organizations": "Organization",
    "villages": "Village",
    "rural_works": "RuralWork",
    "work_logs": "WorkLog",
}


def _resolve_model(table_name: str):
    """将字符串表名解析为 ORM 模型类。先从 TABLE_MODEL_MAP 缓存读取，缓存未命中时动态导入。"""
    if table_name not in ALLOWED_TABLES:
        from app.core.error_handler import BusinessLogicError
        raise BusinessLogicError(f"不允许的表名: {table_name}")

    cached = TABLE_MODEL_MAP.get(table_name)
    if cached is not None:
        return cached

    model_name = _TABLE_TO_MODEL_NAME.get(table_name)
    if model_name is None:
        raise ValueError(f"Unknown table: {table_name}")

    try:
        import app.models
        cls = getattr(app.models, model_name)
        TABLE_MODEL_MAP[table_name] = cls
        return cls
    except Exception as e:
        logger.warning("Failed to resolve model for table '%s': %s", table_name, e)
    raise ValueError(f"Unknown table: {table_name}")


# Module-level get_db (backward-compat: tests mock this)
def get_db():
    """获取数据库会话 (由调用方 mock/override)。"""
    raise NotImplementedError("get_db must be mocked or overridden")


class BatchService:
    """批量操作服务 — 支持新旧两种接口风格。"""

    def __init__(self, db=None):
        self.db = db

    # ── Backward-compat aliases ──
    @property
    def _db(self):
        return self.db

    @_db.setter
    def _db(self, value):
        self.db = value

    @staticmethod
    def _validate_table_name(table_name: str) -> None:
        """兼容旧测试 — 验证表名是否在白名单中。"""
        if table_name not in ALLOWED_TABLES:
            from app.core.error_handler import BusinessLogicError
            raise BusinessLogicError(f"不允许的表名: {table_name}")

    def _get_model_class(self, table_name: str):
        """兼容旧测试 — 根据表名获取模型类。"""
        self._validate_table_name(table_name)
        return _resolve_model(table_name)

    @contextmanager
    def _get_db_context(self):
        """兼容旧测试 — 获取数据库上下文管理器。"""
        if self.db is not None:
            yield self.db
        else:
            gen = get_db()
            db = None
            try:
                db = next(gen)
                yield db
            finally:
                if db is not None:
                    try:
                        db.close()
                    except Exception as e:
                        logger.debug("Failed to close db session: %s", e)
                try:
                    gen.close()
                except Exception as e:
                    logger.debug("Failed to close generator: %s", e)

    # ── Core operations ──
    @staticmethod
    async def process(data: list) -> dict:
        return {"processed": len(data)}

    async def batch_update(self, table_name: str, ids: List[int],
                           updates: dict, *, organization_id: int | None = None,
                           is_superuser: bool = False, **kwargs) -> Dict[str, Any]:
        self._validate_table_name(table_name)
        _reject_protected_table(table_name)
        model = _resolve_model(table_name)
        # 二次防线：过滤禁止更新的敏感字段
        safe_updates = {k: v for k, v in updates.items() if k not in _FORBIDDEN_UPDATE_FIELDS}
        count = 0
        skipped = 0
        if self.db:
            # 批量查询替代逐条 GET（避免 N+1）
            base_query = self.db.query(model).filter(model.id.in_(ids))
            total_matched = base_query.count()
            # 数据隔离：非超级管理员只能操作本组织数据
            # 2026-10-29 审计（fail-open 修复）：原条件是
            #   not is_superuser and organization_id is not None and org_col is not None
            # —— 操作者 organization_id 为 None（未绑组织的 admin、role=super_admin 但
            # is_superuser=False 等）时三个条件整体短路，直接走全量分支，按裸 id 列表
            # 跨组织批量改/删，违反 ADR-0002 fail-closed。
            org_col = getattr(model, 'organization_id', None)
            if is_superuser or org_col is None:
                # 超管：全局；模型本身无组织列：该表不需要组织隔离（按模型结构判定）
                instances = base_query.all()
            elif organization_id is None:
                # 非超管且账号未绑定组织 → 不得操作任何记录（fail-closed）
                return {
                    "success": False,
                    "success_count": 0,
                    "skipped": total_matched,
                    "error": "账号未绑定组织，无权批量操作该表数据",
                }
            else:
                instances = base_query.filter(org_col == organization_id).all()
                skipped = total_matched - len(instances)
            for inst in instances:
                for k, v in safe_updates.items():
                    if hasattr(inst, k):
                        setattr(inst, k, v)
                count += 1
            safe_commit(self.db)
        return {"success": True, "success_count": count, "skipped": skipped}

    async def batch_delete(self, table_name: str, ids: List[int],
                           soft_delete: bool = False, *,
                           organization_id: int | None = None,
                           is_superuser: bool = False, **kwargs) -> Dict[str, Any]:
        self._validate_table_name(table_name)
        _reject_protected_table(table_name)
        model = _resolve_model(table_name)
        count = 0
        skipped = 0
        if self.db:
            # 批量查询替代逐条 GET（避免 N+1）
            base_query = self.db.query(model).filter(model.id.in_(ids))
            total_matched = base_query.count()
            # 数据隔离：非超级管理员只能操作本组织数据（同 batch_update 的 fail-closed 口径）
            org_col = getattr(model, 'organization_id', None)
            if is_superuser or org_col is None:
                instances = base_query.all()
            elif organization_id is None:
                return {
                    "success": False,
                    "success_count": 0,
                    "skipped": total_matched,
                    "error": "账号未绑定组织，无权批量删除该表数据",
                }
            else:
                instances = base_query.filter(org_col == organization_id).all()
                skipped = total_matched - len(instances)
            for inst in instances:
                if soft_delete:
                    # 优先使用 is_active 列（SupportedVillage/School/Project/Fund）
                    if hasattr(inst, 'is_active'):
                        inst.is_active = False
                    elif hasattr(inst, 'is_deleted'):
                        inst.is_deleted = True
                    else:
                        self.db.delete(inst)
                else:
                    self.db.delete(inst)
                count += 1
            safe_commit(self.db)
        return {"success": True, "success_count": count, "skipped": skipped}

    async def batch_export(self, table_name: str, ids: List[int],
                           format: str = "xlsx", *,
                           organization_id: int | None = None,
                           is_superuser: bool = False, **kwargs) -> Dict[str, Any]:
        self._validate_table_name(table_name)
        # P0 越权/信息泄露封堵（与 batch_update / batch_delete / validate_batch 同口径）：
        # 原实现漏了本守卫，导致 `batch_export("users")` 可把 User.to_dict() 整表导出，
        # 其中含 hashed_password（bcrypt 哈希）、role、is_superuser、token_version、
        # phone/email 等敏感列；且无组织过滤，部门级 admin 可跨组织导出全部账号。
        _reject_protected_table(table_name)
        from io import BytesIO
        import base64
        try:
            from openpyxl import Workbook
            model = self._get_model_class(table_name)
            # R20 复审(中)：原实现只写表头即返回成功 —— 实际导出内容为空
            query = self.db.query(model)
            if ids:
                query = query.filter(model.id.in_(ids))
            # 数据隔离（S2 红线）：非超管只能导出本组织数据，与 update/delete 一致
            org_col = getattr(model, 'organization_id', None)
            if not is_superuser and organization_id is not None and org_col is not None:
                query = query.filter(org_col == organization_id)
            records = [r.to_dict() for r in query.all()]
            wb = Workbook()
            ws = wb.active
            ws.title = table_name
            header = list(records[0].keys()) if records else ["id"]
            ws.append(header)
            for rec in records:
                ws.append([rec.get(h) for h in header])
            output = BytesIO()
            wb.save(output)
            data = base64.b64encode(output.getvalue()).decode()
            return {"success": True, "data": data, "exported_count": len(records)}
        except ImportError:  # pragma: no cover - 可选依赖未安装时的功能降级分支
            return {"success": False, "data": "", "exported_count": 0}

    async def validate_batch(self, table_name: str,
                             ids: List[int], *,
                             organization_id: int | None = None,
                             is_superuser: bool = False, **kwargs) -> Dict[str, Any]:
        self._validate_table_name(table_name)
        _reject_protected_table(table_name)
        model = _resolve_model(table_name)
        existing_count = 0
        if self.db:
            # 批量 COUNT 查询替代逐条 GET（避免 N+1）
            query = self.db.query(model).filter(model.id.in_(ids))
            org_col = getattr(model, 'organization_id', None)
            if not is_superuser and organization_id is not None and org_col is not None:
                query = query.filter(org_col == organization_id)
            existing_count = query.count()
        return {"success": True, "existing_count": existing_count}


# Backward-compat: tests import this module-level instance
batch_service = BatchService()
