"""数据同步服务"""

import json
import logging
import re
import zipfile
from dataclasses import dataclass
from datetime import timezone, datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.error_handler import app_logger, BusinessLogicError
from app.core.transaction import safe_commit
from app.models.data_sync import DataSyncLog, DataConflict
from app.services.encrypted_package import create_encrypted_package, extract_encrypted_package
import hashlib as _hashlib

logger = logging.getLogger(__name__)
# 预编译正则表达式，避免每次调用重新编译
_TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# 允许同步的表名白名单（防止 SQL 注入）
_ALLOWED_TABLES = frozenset({
    "users",
    "organizations",
    "projects",
    "funds",
    "work_logs",
    "supported_villages",
    "schools",
    "policies",
    "attachments",
    "audit_logs",
    "data_packages",
    "sync_logs",
    "data_conflicts",
    "machine_codes",
    "update_logs",
    "fund_budgets",
})

# 敏感表: 禁止导入(防提权/数据篡改)
_SENSITIVE_TABLES = frozenset({"users", "machine_codes", "audit_logs"})


@dataclass
class ExportConfig:
    """导出配置参数对象"""

    since: Optional[datetime] = None
    modules: Optional[List[str]] = None
    include_files: bool = False
    user_id: Optional[int] = None
    user_name: Optional[str] = None


class DataSyncService:
    """数据同步服务"""

    def __init__(self):
        from app.utils.paths import get_app_data_dir

        self.logger = app_logger
        self.sync_dir = get_app_data_dir() / "data_sync"
        try:
            self.sync_dir.mkdir(exist_ok=True)
        except Exception as e:
            self.logger.warning(f"创建同步目录失败: {e}")

        # 支持同步的表
        self.syncable_tables = {
            "supported_villages": "帮扶村",
            "village_populations": "人口数据",
            "village_incomes": "收入数据",
            "organizations": "组织",
            "policies": "政策",
            "force_investments": "专项投入",
            "industry_supports": "产业帮扶",
            "infrastructure_improvements": "基础设施",
            "party_building_supports": "党建帮扶",
            "medical_supports": "医疗帮扶",
            "consumption_supports": "消费帮扶",
            "employment_supports": "就业帮扶",
            "education_supports": "教育帮扶",
        }

    @contextmanager
    def _get_db_context(self):
        """数据库连接上下文管理器，确保连接正确关闭"""
        db_gen = get_db()
        db = next(db_gen)
        try:
            yield db
        finally:
            try:
                db.close()
            except Exception as e:
                self.logger.error(f"关闭数据库连接失败: {e}")

    async def export_incremental(
        self,
        config: ExportConfig,
    ) -> Dict[str, Any]:
        """
        导出增量数据包

        Args:
            config: 导出配置参数对象

        Returns:
            导出结果字典
        """
        try:
            export_time = datetime.now(timezone.utc)
            package_name = f"export_{export_time.strftime('%Y%m%d_%H%M%S')}"

            self.logger.info(f"开始导出增量数据: {package_name}")

            # 使用上下文管理器确保连接正确关闭
            with self._get_db_context() as db:
                sync_log = DataSyncLog(
                    sync_type="export",
                    status="processing",
                    package_name=package_name,
                    since_time=config.since,
                    modules=config.modules or list(self.syncable_tables.keys()),
                    include_files=config.include_files,
                    user_id=config.user_id,
                    user_name=config.user_name,
                    started_at=export_time,
                )
                db.add(sync_log)
                safe_commit(db, self.logger)
                db.refresh(sync_log)

                # 准备导出数据
                export_data = {
                    "export_info": {
                        "package_name": package_name,
                        "exported_at": export_time.isoformat(),
                        "since": config.since.isoformat() if config.since else None,
                        "modules": config.modules or list(self.syncable_tables.keys()),
                        "include_files": config.include_files,
                        "version": "1.0.0",
                    },
                    "data": {},
                }

                # 导出表数据
                total_records = 0
                tables_to_export = config.modules or list(self.syncable_tables.keys())

                for table_name in tables_to_export:
                    if table_name not in self.syncable_tables:
                        continue

                    try:
                        records = await self._export_table_data(db, table_name, config.since)
                        export_data["data"][table_name] = records
                        total_records += len(records)
                        self.logger.info(f"表 {table_name} 导出 {len(records)} 条记录")
                    except Exception as e:
                        self.logger.warning(f"导出表 {table_name} 失败: {str(e)}")
                        export_data["data"][table_name] = []

                # 保存数据包
                package_path = await self._save_export_package(export_data, package_name, config.include_files)

                # 更新同步日志
                sync_log.status = "completed"
                sync_log.package_path = str(package_path)
                sync_log.total_records = total_records
                sync_log.success_records = total_records
                sync_log.completed_at = datetime.now(timezone.utc)
                sync_log.details = {"tables": {k: len(v) for k, v in export_data["data"].items()}}
                safe_commit(db, self.logger)

                result = {
                    "success": True,
                    "package_name": package_name,
                    "package_path": str(package_path),
                    "total_records": total_records,
                    "exported_at": export_time.isoformat(),
                    "size": package_path.stat().st_size if package_path.exists() else 0,
                    "message": "数据导出成功",
                }

                self.logger.info("data_exported", details=result)
                return result

        except Exception as e:
            self.logger.error(f"导出数据失败: {str(e)}")
            raise BusinessLogicError(f"数据导出失败: {str(e)}")

    async def _export_table_data(
        self, db: Session, table_name: str, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """导出表数据"""
        try:
            # 构建查询（表名已在调用处通过 syncable_tables 白名单验证）
            safe_table = self._validate_table_name(table_name)
            if since:
                query = text(f"""
                    SELECT * FROM {safe_table}
                    WHERE updated_at > :since OR created_at > :since
                    ORDER BY id
                """)  # nosec B608 — _validate_table_name 白名单验证
                result = db.execute(query, {"since": since})
            else:
                query = text(f"SELECT * FROM {safe_table} ORDER BY id")  # nosec B608
                result = db.execute(query)

            rows = result.fetchall()
            columns = result.keys()

            # 转换为可序列化格式
            records = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                # 处理特殊类型
                for key, value in row_dict.items():
                    if hasattr(value, "isoformat"):
                        row_dict[key] = value.isoformat()
                    elif isinstance(value, bytes):
                        row_dict[key] = value.hex()
                records.append(row_dict)

            return records

        except Exception as e:
            self.logger.error(f"导出表 {table_name} 数据失败: {str(e)}")
            return []

    async def _save_export_package(self, export_data: Dict[str, Any], package_name: str, include_files: bool) -> Path:
        """保存导出数据包"""
        package_path = self.sync_dir / f"{package_name}.zip"

        with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # 保存数据JSON
            zipf.writestr("data.json", json.dumps(export_data, ensure_ascii=False, indent=2))

            # 如果需要，打包上传文件
            if include_files:
                from app.utils.paths import get_uploads_path

                uploads_dir = get_uploads_path()
                resolved_uploads = uploads_dir.resolve()
                if uploads_dir.exists():
                    for item in uploads_dir.rglob("*"):
                        if item.is_file():
                            # 路径安全校验：确保文件仍在 uploads_dir 内部
                            try:
                                item.resolve().relative_to(resolved_uploads)
                            except ValueError:
                                self.logger.warning(f"跳过不安全的上传文件路径: {item}")
                                continue
                            arcname = f"files/{item.relative_to(uploads_dir)}"
                            zipf.write(item, arcname)

        self.logger.info(f"数据包已保存: {package_path}")
        return package_path

    async def import_package(
        self,
        package_path: str,
        strategy: str = "skip",  # skip/overwrite/merge/manual
        user_id: Optional[int] = None,
        user_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """导入数据包"""
        try:
            self.logger.info(f"开始导入数据包: {package_path}")

            package_file = Path(package_path)
            if not package_file.exists():
                raise BusinessLogicError("数据包文件不存在")

            # 加载数据包
            import_data = await self._load_import_package(package_file)
            if not import_data:
                raise BusinessLogicError("数据包格式错误")

            export_info = import_data.get("export_info", {})
            package_name = export_info.get("package_name", "unknown")

            # 使用上下文管理器确保连接正确关闭
            with self._get_db_context() as db:
                sync_log = DataSyncLog(
                    sync_type="import",
                    status="processing",
                    package_name=package_name,
                    package_path=package_path,
                    conflict_strategy=strategy,
                    user_id=user_id,
                    user_name=user_name,
                    started_at=datetime.now(timezone.utc),
                )
                db.add(sync_log)
                safe_commit(db, self.logger)
                db.refresh(sync_log)

                # 导入数据
                result = {
                    "success": False,
                    "package_name": package_name,
                    "imported_at": datetime.now(timezone.utc).isoformat(),
                    "total_records": 0,
                    "success_records": 0,
                    "failed_records": 0,
                    "conflicts": [],
                    "errors": [],
                }

                data_dict = import_data.get("data", {})
                for table_name, records in data_dict.items():
                    if table_name not in self.syncable_tables:
                        continue
                    # 敏感表硬禁止导入（防止构造 ZIP 覆盖用户/机器码/审计数据提权）
                    if table_name in _SENSITIVE_TABLES:
                        result["errors"].append(f"禁止导入敏感表: {table_name}")
                        continue

                    try:
                        import_result = await self._import_table_data(db, table_name, records, strategy, sync_log.id)
                        result["total_records"] += import_result["total"]
                        result["success_records"] += import_result["success"]
                        result["failed_records"] += import_result["failed"]
                        result["conflicts"].extend(import_result["conflicts"])

                    except Exception as e:
                        error_msg = f"导入表 {table_name} 失败: {str(e)}"
                        result["errors"].append(error_msg)
                        self.logger.error(error_msg)

                # 更新同步日志
                sync_log.status = "completed"
                sync_log.total_records = result["total_records"]
                sync_log.success_records = result["success_records"]
                sync_log.failed_records = result["failed_records"]
                sync_log.conflicts_count = len(result["conflicts"])
                sync_log.completed_at = datetime.now(timezone.utc)
                sync_log.details = result
                safe_commit(db, self.logger)

                result["success"] = True
                result["sync_log_id"] = sync_log.id
                result["message"] = "数据导入成功"

                self.logger.info("data_imported", details=result)
                return result

        except Exception as e:
            self.logger.error(f"导入数据失败: {str(e)}")
            raise BusinessLogicError(f"数据导入失败: {str(e)}")

    async def _load_import_package(self, package_path: Path) -> Dict[str, Any]:
        """加载导入数据包"""
        try:
            with zipfile.ZipFile(package_path, "r") as zipf:
                with zipf.open("data.json") as f:
                    return json.loads(f.read().decode("utf-8"))
        except Exception as e:
            self.logger.error(f"加载数据包失败: {str(e)}")
            return {}

    async def _import_table_data(
        self,
        db: Session,
        table_name: str,
        records: List[Dict[str, Any]],
        strategy: str,
        sync_log_id: int,
    ) -> Dict[str, Any]:
        """导入表数据"""
        safe_table = self._validate_table_name(table_name)
        result = {"total": len(records), "success": 0, "failed": 0, "conflicts": []}

        for record in records:
            try:
                # 检查记录是否存在
                record_id = record.get("id")
                if record_id:
                    existing = db.execute(
                        text(f"SELECT * FROM {safe_table} WHERE id = :id"),  # nosec B608
                        {"id": record_id},
                    ).fetchone()

                    if existing:
                        # 处理冲突
                        if strategy == "skip":
                            result["success"] += 1
                            continue
                        elif strategy == "overwrite":
                            # 更新记录
                            await self._update_record(db, table_name, record)
                            result["success"] += 1
                        elif strategy == "manual":
                            # 记录冲突
                            conflict = DataConflict(
                                sync_log_id=sync_log_id,
                                table_name=table_name,
                                record_id=str(record_id),
                                conflict_type="duplicate",
                                local_data=dict(zip(existing.keys(), existing)),
                                import_data=record,
                                resolution="pending",
                            )
                            db.add(conflict)
                            result["conflicts"].append(
                                {
                                    "table": table_name,
                                    "record_id": record_id,
                                    "type": "duplicate",
                                }
                            )
                            result["success"] += 1
                    else:
                        # 插入新记录
                        await self._insert_record(db, table_name, record)
                        result["success"] += 1
                else:
                    # 没有ID，直接插入
                    await self._insert_record(db, table_name, record)
                    result["success"] += 1

            except Exception as e:
                self.logger.error(f"导入记录失败: {str(e)}")
                result["failed"] += 1

        safe_commit(db, self.logger)
        return result

    @staticmethod
    def _sanitize_column_name(col: str) -> str:
        """
        校验列名只含安全字符（字母、数字、下划线），防止列名注入。
        非法列名会抛出 ValueError。
        """
        if not _TABLE_NAME_PATTERN.match(col):
            raise ValueError(f"非法的列名: {col!r}")
        return col

    @staticmethod
    def _validate_table_name(table_name: str) -> str:
        """
        校验表名在白名单中，防止 SQL 注入。
        非法表名抛出 ValueError。
        """
        if not _TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"非法的表名: {table_name!r}")
        if table_name not in _ALLOWED_TABLES:
            raise ValueError(f"表名不在允许列表中: {table_name!r}")
        return table_name

    async def _insert_record(self, db: Session, table_name: str, record: Dict[str, Any]):
        """插入记录"""
        safe_cols = [self._sanitize_column_name(k) for k in record.keys()]
        columns = ", ".join(safe_cols)
        placeholders = ", ".join([f":{k}" for k in record.keys()])
        safe_table = self._validate_table_name(table_name)
        query = text(f"INSERT INTO {safe_table} ({columns}) VALUES ({placeholders})")  # nosec B608
        db.execute(query, record)

    async def _update_record(self, db: Session, table_name: str, record: Dict[str, Any]):
        """更新记录"""
        record_id = record.pop("id")
        safe_cols = [self._sanitize_column_name(k) for k in record.keys()]
        set_clause = ", ".join([f"{col} = :{col}" for col in safe_cols])
        safe_table = self._validate_table_name(table_name)
        query = text(f"UPDATE {safe_table} SET {set_clause} WHERE id = :id")  # nosec B608
        record["id"] = record_id
        db.execute(query, record)

    async def get_conflicts(self, sync_log_id: int) -> List[Dict[str, Any]]:
        """获取冲突列表"""
        with self._get_db_context() as db:
            conflicts = (
                db.query(DataConflict)
                .filter(
                    DataConflict.sync_log_id == sync_log_id,
                    DataConflict.resolved == False,  # noqa: E712
                )
                .all()
            )

            return [
                {
                    "id": c.id,
                    "table_name": c.table_name,
                    "record_id": c.record_id,
                    "conflict_type": c.conflict_type,
                    "local_data": c.local_data,
                    "import_data": c.import_data,
                    "created_at": c.created_at.isoformat(),
                }
                for c in conflicts
            ]

    async def resolve_conflict(
        self,
        conflict_id: int,
        resolution: str,  # keep_local/use_import/merge
        merged_data: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """解决冲突"""
        with self._get_db_context() as db:
            conflict = db.query(DataConflict).filter(DataConflict.id == conflict_id).first()
            if not conflict:
                raise BusinessLogicError("冲突记录不存在")

            # 应用解决方案
            if resolution == "keep_local":
                # 保持本地数据，不做任何操作
                pass
            elif resolution == "use_import":
                # 使用导入数据
                await self._update_record(db, conflict.table_name, conflict.import_data)
            elif resolution == "merge":
                # 使用合并后的数据
                if not merged_data:
                    raise BusinessLogicError("合并数据不能为空")
                await self._update_record(db, conflict.table_name, merged_data)
                conflict.merged_data = merged_data

            # 更新冲突记录
            conflict.resolution = resolution
            conflict.resolved = True
            conflict.resolved_at = datetime.now(timezone.utc)
            conflict.resolved_by = user_id
            safe_commit(db, self.logger)

            return {"success": True, "message": "冲突已解决"}

    async def export_encrypted(
        self,
        export_type: str = "full",  # full/selective
        tables: Optional[List[str]] = None,
        password: str = None,
        since: Optional[datetime] = None,
        user_id: Optional[int] = None,
        user_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        导出加密数据包（.rrs 格式）

        Args:
            export_type: 导出类型（full=完整导出, selective=选择性导出）
            tables: 要导出的表列表（仅在 selective 模式下使用）
            password: 加密密码
            since: 起始时间（增量导出）
            user_id: 用户ID
            user_name: 用户名

        Returns:
            导出结果
        """
        try:
            if not password:
                raise BusinessLogicError("密码不能为空")

            if len(password) < 8:
                raise BusinessLogicError("密码长度至少为8位")

            export_time = datetime.now(timezone.utc)
            package_name = f"export_{export_time.strftime('%Y%m%d_%H%M%S')}"

            self.logger.info(f"开始导出加密数据包: {package_name}")

            with self._get_db_context() as db:
                # 确定要导出的表
                if export_type == "full":
                    tables_to_export = list(self.syncable_tables.keys())
                else:
                    tables_to_export = tables or []

                # 准备导出数据
                export_data = {}
                total_records = 0

                for table_name in tables_to_export:
                    if table_name not in self.syncable_tables:
                        continue

                    try:
                        records = await self._export_table_data(db, table_name, since)
                        export_data[table_name] = records
                        total_records += len(records)
                        self.logger.info(f"表 {table_name} 导出 {len(records)} 条记录")
                    except Exception as e:
                        self.logger.warning(f"导出表 {table_name} 失败: {str(e)}")
                        export_data[table_name] = []

                # 准备元数据
                metadata = {
                    "package_name": package_name,
                    "export_type": export_type,
                    "exported_at": export_time.isoformat(),
                    "since": since.isoformat() if since else None,
                    "tables": tables_to_export,
                    "total_records": total_records,
                    "version": "1.0.0",
                }

                # 加密并创建 .rrs 文件 (AES-256-GCM + PBKDF2-SHA256)
                package_path = self.sync_dir / f"{package_name}.rrs"
                package_data = {
                    "metadata": metadata,
                    "data": export_data,
                }
                create_encrypted_package(
                    data=package_data,
                    output_path=str(package_path),
                    password=password,
                )

                # 计算文件哈希
                file_hash = _hashlib.sha256(package_path.read_bytes()).hexdigest()
                file_size = package_path.stat().st_size

                # 保存导出记录
                sync_log = DataSyncLog(
                    sync_type="export",
                    status="completed",
                    package_name=package_name,
                    package_path=str(package_path),
                    since_time=since,
                    modules=tables_to_export,
                    include_files=False,
                    total_records=total_records,
                    success_records=total_records,
                    user_id=user_id,
                    user_name=user_name,
                    started_at=export_time,
                    completed_at=datetime.now(timezone.utc),
                    details={
                        "export_type": export_type,
                        "file_hash": file_hash,
                        "file_size": file_size,
                        "encrypted": True,
                        "tables": {k: len(v) for k, v in export_data.items()},
                    },
                )
                db.add(sync_log)
                safe_commit(db, self.logger)

                result = {
                    "success": True,
                    "package_name": package_name,
                    "package_path": str(package_path),
                    "total_records": total_records,
                    "exported_at": export_time.isoformat(),
                    "size": file_size,
                    "file_hash": file_hash,
                    "message": "数据导出成功",
                }

                self.logger.info("encrypted_data_exported", details=result)
                return result

        except Exception as e:
            self.logger.error(f"导出加密数据失败: {str(e)}")
            raise BusinessLogicError(f"数据导出失败: {str(e)}")

    async def import_encrypted(
        self,
        package_path: str,
        password: str,
        strategy: str = "merge",  # skip/overwrite/merge
        user_id: Optional[int] = None,
        user_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        导入加密数据包（.rrs 格式）

        Args:
            package_path: 数据包文件路径
            password: 解密密码
            strategy: 合并策略
            user_id: 用户ID
            user_name: 用户名

        Returns:
            导入结果
        """
        try:
            self.logger.info(f"开始导入加密数据包: {package_path}")

            package_file = Path(package_path)
            if not package_file.exists():
                raise BusinessLogicError("数据包文件不存在")

            # 读取并解密文件 (AES-256-GCM + PBKDF2-SHA256)
            try:
                package_data = extract_encrypted_package(str(package_file), password)
            except ValueError as e:
                raise BusinessLogicError(str(e))

            metadata = package_data.get("metadata", {})
            import_data = package_data.get("data", {})
            package_name = metadata.get("package_name", "unknown")

            with self._get_db_context() as db:
                sync_log = DataSyncLog(
                    sync_type="import",
                    status="processing",
                    package_name=package_name,
                    package_path=package_path,
                    conflict_strategy=strategy,
                    user_id=user_id,
                    user_name=user_name,
                    started_at=datetime.now(timezone.utc),
                )
                db.add(sync_log)
                safe_commit(db, self.logger)
                db.refresh(sync_log)

                # 导入数据
                result = {
                    "success": False,
                    "package_name": package_name,
                    "imported_at": datetime.now(timezone.utc).isoformat(),
                    "total_records": 0,
                    "success_records": 0,
                    "failed_records": 0,
                    "inserted_count": 0,
                    "updated_count": 0,
                    "skipped_count": 0,
                    "conflicts": [],
                    "errors": [],
                }

                for table_name, records in import_data.items():
                    if table_name not in self.syncable_tables:
                        continue

                    try:
                        import_result = await self._import_table_data_enhanced(
                            db, table_name, records, strategy, sync_log.id
                        )
                        result["total_records"] += import_result["total"]
                        result["success_records"] += import_result["success"]
                        result["failed_records"] += import_result["failed"]
                        result["inserted_count"] += import_result["inserted"]
                        result["updated_count"] += import_result["updated"]
                        result["skipped_count"] += import_result["skipped"]
                        result["conflicts"].extend(import_result["conflicts"])

                    except Exception as e:
                        error_msg = f"导入表 {table_name} 失败: {str(e)}"
                        result["errors"].append(error_msg)
                        self.logger.error(error_msg)

                # 更新同步日志
                sync_log.status = "completed"
                sync_log.total_records = result["total_records"]
                sync_log.success_records = result["success_records"]
                sync_log.failed_records = result["failed_records"]
                sync_log.conflicts_count = len(result["conflicts"])
                sync_log.completed_at = datetime.now(timezone.utc)
                sync_log.details = result
                safe_commit(db, self.logger)

                result["success"] = True
                result["sync_log_id"] = sync_log.id
                result["message"] = "数据导入成功"

                self.logger.info("encrypted_data_imported", details=result)
                return result

        except Exception as e:
            self.logger.error(f"导入加密数据失败: {str(e)}")
            raise BusinessLogicError(f"数据导入失败: {str(e)}")

    async def _import_table_data_enhanced(
        self,
        db: Session,
        table_name: str,
        records: List[Dict[str, Any]],
        strategy: str,
        sync_log_id: int,
    ) -> Dict[str, Any]:
        """
        增强的表数据导入（支持智能合并）

        Args:
            db: 数据库会话
            table_name: 表名
            records: 记录列表
            strategy: 合并策略
            sync_log_id: 同步日志ID

        Returns:
            导入统计
        """
        result = {
            "total": len(records),
            "success": 0,
            "failed": 0,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "conflicts": [],
        }

        safe_table = self._validate_table_name(table_name)

        for record in records:
            try:
                record_id = record.get("id")
                if record_id:
                    # 检查记录是否存在
                    existing = db.execute(
                        text(f"SELECT * FROM {safe_table} WHERE id = :id"),  # nosec B608
                        {"id": record_id},
                    ).fetchone()

                    if existing:
                        # 记录存在，根据策略处理
                        if strategy == "skip":
                            result["skipped"] += 1
                            result["success"] += 1
                        elif strategy == "overwrite":
                            await self._update_record(db, table_name, record)
                            result["updated"] += 1
                            result["success"] += 1
                        elif strategy == "merge":
                            # 智能合并：比较时间戳
                            existing_dict = dict(zip(existing.keys(), existing))
                            should_update = self._should_update_record(existing_dict, record)
                            if should_update:
                                await self._update_record(db, table_name, record)
                                result["updated"] += 1
                            else:
                                result["skipped"] += 1
                            result["success"] += 1
                    else:
                        # 记录不存在，插入
                        await self._insert_record(db, table_name, record)
                        result["inserted"] += 1
                        result["success"] += 1
                else:
                    # 没有ID，直接插入
                    await self._insert_record(db, table_name, record)
                    result["inserted"] += 1
                    result["success"] += 1

            except Exception as e:
                self.logger.error(f"导入记录失败: {str(e)}")
                result["failed"] += 1

        safe_commit(db, self.logger)
        return result

    def _should_update_record(self, existing: Dict[str, Any], imported: Dict[str, Any]) -> bool:
        """
        判断是否应该更新记录（基于时间戳）

        Args:
            existing: 现有记录
            imported: 导入记录

        Returns:
            是否应该更新
        """
        # 如果导入记录有 updated_at 字段，比较时间戳
        if "updated_at" in imported and "updated_at" in existing:
            try:
                from dateutil import parser

                imported_time = (
                    parser.parse(imported["updated_at"])
                    if isinstance(imported["updated_at"], str)
                    else imported["updated_at"]
                )
                existing_time = existing["updated_at"]

                # 如果导入的记录更新，则更新
                return imported_time > existing_time
            except Exception:
                # 时间解析失败会静默跳过该记录 → 数据不一致，升级为 warning 可观测
                logger.warning(
                    "数据同步更新比较失败（记录可能被跳过）: %s", imported.get("id", "?"), exc_info=True
                )

        # 默认不更新
        return False


# 创建全局实例
data_sync_service = DataSyncService()
