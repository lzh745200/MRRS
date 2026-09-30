"""导入导出历史服务。

同时支持同步 Session（路由注入）和 AsyncSession（兼容旧调用）。
所有便捷方法（record_export / record_import / …）均为同步，因为路由层
注入的是同步 Session。
"""
import json
import logging
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.import_export_history import ImportExportHistory, OperationResult
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)


class ImportExportHistoryService:
    def __init__(self, db: Union[Session, AsyncSession]):
        self.db = db
        self._is_async = isinstance(db, AsyncSession)

    # ------------------------------------------------------------------
    # 同步便捷方法（路由层使用）
    # ------------------------------------------------------------------

    @staticmethod
    def _dump_json(value: Optional[Union[str, list, Dict[str, Any]]]) -> Optional[str]:
        """把列表/字典统一序列化为 JSON 文本；已是字符串的原样透传。"""
        if value is None or isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def create_history(
        self,
        *,
        package_id: Optional[int] = None,
        operation_type: str = "export",
        result: Union[str, OperationResult] = OperationResult.SUCCESS,
        user_id: int = 0,
        org_id: Optional[int] = None,
        duration_ms: Optional[int] = None,
        client_ip: Optional[str] = None,
        error_message: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        record_count: Optional[int] = None,
        data_types: Optional[Union[str, list]] = None,
        user_agent: Optional[str] = None,
        details_json: Optional[Union[str, Dict[str, Any]]] = None,
        **extra,
    ) -> Optional[ImportExportHistory]:
        """创建一条操作历史记录（同步）。

        兼容路由中 history_service.create_history(...) 的调用签名。

        审计元数据修复：record_export / record_import / record_confirm 一直以关键字
        传入 file_name / file_size / record_count / data_types / user_agent /
        details_json，但本方法此前未声明这 6 个参数 → 全部落进 **extra 被静默丢弃，
        模型上对应的 6 个审计列永远为 NULL。现显式声明并写库；仍未声明的键改为
        告警日志，不再无声吞掉。
        """
        if extra:
            logger.warning("create_history 收到未声明的审计元数据，已忽略: %s", sorted(extra))
        result_value = result.value if isinstance(result, OperationResult) else str(result)
        record = ImportExportHistory(
            package_id=package_id,
            operation_type=operation_type,
            org_id=org_id,
            user_id=user_id,
            result=result_value,
            duration_ms=duration_ms,
            ip_address=client_ip,
            error_message=error_message,
            file_name=file_name,
            file_size=file_size,
            record_count=record_count,
            data_types=self._dump_json(data_types),
            user_agent=user_agent,
            details_json=self._dump_json(details_json),
        )
        self.db.add(record)
        try:
            safe_commit(self.db)
            self.db.refresh(record)
        except Exception:
            self.db.rollback()
            raise
        return record

    def record_export(
        self,
        *,
        package_id: Optional[int] = None,
        org_id: int,
        user_id: int,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        record_count: Optional[int] = None,
        data_types: Optional[list] = None,
        duration_ms: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        result: Union[str, OperationResult] = OperationResult.SUCCESS,
        error_message: Optional[str] = None,
        **extra,
    ) -> Optional[ImportExportHistory]:
        """记录导出操作历史（同步）"""
        return self.create_history(
            package_id=package_id,
            operation_type="export",
            org_id=org_id,
            user_id=user_id,
            result=result,
            duration_ms=duration_ms,
            client_ip=ip_address,
            error_message=error_message,
            file_name=file_name,
            file_size=file_size,
            record_count=record_count,
            data_types=json.dumps(data_types) if data_types else None,
            user_agent=user_agent,
        )

    def record_import(
        self,
        *,
        package_id: Optional[int] = None,
        org_id: int,
        user_id: int,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        record_count: Optional[int] = None,
        data_types: Optional[list] = None,
        duration_ms: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        result: Union[str, OperationResult] = OperationResult.SUCCESS,
        error_message: Optional[str] = None,
        **extra,
    ) -> Optional[ImportExportHistory]:
        """记录导入操作历史（同步）"""
        return self.create_history(
            package_id=package_id,
            operation_type="import",
            org_id=org_id,
            user_id=user_id,
            result=result,
            duration_ms=duration_ms,
            client_ip=ip_address,
            error_message=error_message,
            file_name=file_name,
            file_size=file_size,
            record_count=record_count,
            data_types=json.dumps(data_types) if data_types else None,
            user_agent=user_agent,
        )

    def record_validate(
        self,
        *,
        package_id: Optional[int] = None,
        org_id: int,
        user_id: int,
        result: Union[str, OperationResult] = OperationResult.SUCCESS,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        **extra,
    ) -> Optional[ImportExportHistory]:
        """记录验证操作历史（同步）"""
        return self.create_history(
            package_id=package_id,
            operation_type="validate",
            org_id=org_id,
            user_id=user_id,
            result=result,
            client_ip=ip_address,
            error_message=error_message,
        )

    def record_preview(
        self,
        *,
        package_id: Optional[int] = None,
        org_id: int,
        user_id: int,
        ip_address: Optional[str] = None,
        **extra,
    ) -> Optional[ImportExportHistory]:
        """记录预览操作历史（同步）"""
        return self.create_history(
            package_id=package_id,
            operation_type="preview",
            org_id=org_id,
            user_id=user_id,
            client_ip=ip_address,
        )

    def record_confirm(
        self,
        *,
        package_id: Optional[int] = None,
        org_id: int,
        user_id: int,
        record_count: Optional[int] = None,
        data_types: Optional[list] = None,
        duration_ms: Optional[int] = None,
        result: Union[str, OperationResult] = OperationResult.SUCCESS,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        **extra,
    ) -> Optional[ImportExportHistory]:
        """记录确认导入操作历史（同步）"""
        return self.create_history(
            package_id=package_id,
            operation_type="confirm",
            org_id=org_id,
            user_id=user_id,
            result=result,
            duration_ms=duration_ms,
            client_ip=ip_address,
            record_count=record_count,
            data_types=json.dumps(data_types) if data_types else None,
            details_json=json.dumps(details, ensure_ascii=False) if details else None,
        )

    def record_delete(
        self,
        *,
        package_id: Optional[int] = None,
        org_id: int,
        user_id: int,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        **extra,
    ) -> Optional[ImportExportHistory]:
        """记录删除操作历史（同步）"""
        return self.create_history(
            package_id=package_id,
            operation_type="delete",
            org_id=org_id,
            user_id=user_id,
            client_ip=ip_address,
            error_message=reason,
        )

    def get_history_by_package(
        self, package_id: int, *, skip: int = 0, limit: int = 20
    ) -> List[ImportExportHistory]:
        """获取指定数据包的操作历史（同步）"""
        query = (
            self.db.query(ImportExportHistory)
            .filter(ImportExportHistory.package_id == package_id)
            .order_by(desc(ImportExportHistory.created_at))
            .offset(skip)
            .limit(limit)
        )
        return list(query.all())

    # ------------------------------------------------------------------
    # 异步方法（保留兼容旧调用者）
    # ------------------------------------------------------------------

    async def list_history(self, *, page: int = 1, page_size: int = 20,
                           user_id: Optional[int] = None) -> dict:
        query = select(ImportExportHistory).order_by(desc(ImportExportHistory.created_at))
        count_q = select(func.count(ImportExportHistory.id))
        if user_id:
            query = query.where(ImportExportHistory.user_id == user_id)
            count_q = count_q.where(ImportExportHistory.user_id == user_id)
        total = (await self.db.execute(count_q)).scalar() or 0
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return {"items": result.scalars().all(), "total": total, "page": page, "page_size": page_size}

    async def record(self, **kwargs) -> ImportExportHistory:
        record = ImportExportHistory(**kwargs)
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record
