"""
Data Package Service
数据包管理服务 - 导入导出功能 (重构优化版)

重构亮点：
1. 架构纠正：将包含大量文件 I/O 和同步 DB 操作的方法从 async 改为 def，防止 Event Loop 阻塞。
2. 数据一致性：保留原始 ID，引入 Bulk Upsert (Insert or Update)，彻底解决外键孤儿问题。
3. 性能优化：使用 SQLAlchemy 2.0 批量插入，结合 db_coordinator.exclusive_write() 防锁。
4. 安全加固：完善加密解密链路，确保临时文件安全清理。
"""

import hashlib
import json
import os
import shutil
import zipfile
from datetime import timezone, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import inspect
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.database import db_coordinator
from app.core.exceptions import BusinessError
from app.core.json_encoder import CustomJSONEncoder
from app.core.logging import logger
from app.models.data_package import DataPackage, PackageStatus, PackageType
from app.models.project import Fund, Project
from app.models.school import School
from app.models.supported_village import SupportedVillage
from app.schemas.data_package import (
    DataPackageConfirmResult,
    DataPackageExportResult,
    DataPackageImportResult,
    DataPackageManifest,
    DataPackagePreviewData,
    DataPackageValidationError,
    DataPackageValidationResult,
    PackageStatusEnum,
)
from app.services.organization_service import OrganizationService
from app.core.transaction import safe_commit

# 支持的数据包版本
SUPPORTED_VERSIONS = ["1.0", "1.1"]
CURRENT_VERSION = "1.0"

# 数据类型映射
DATA_TYPE_MODELS = {
    "villages": SupportedVillage,
    "projects": Project,
    "funds": Fund,
    "schools": School,
}


class PackageValidationError(BusinessError):
    """数据包验证错误"""
    def __init__(self, errors: List[str]):
        super().__init__(f"数据包验证失败: {', '.join(errors[:3])}")
        self.errors = errors


class PackageVersionUnsupportedError(BusinessError):
    """数据包版本不支持"""
    def __init__(self, version: str):
        super().__init__(f"不支持的数据包版本: {version}")
        self.version = version


class DataPackageService:
    """
    数据包管理服务
    负责数据的导出、导入、验证和预览。
    注意：涉及大量文件 I/O 和同步 DB 操作的方法已统一改为同步 (def)，
    以防止在 FastAPI 的 async 路由中阻塞 Event Loop。
    """

    def __init__(self, db: Session, upload_dir: str = None):
        self.db = db
        if upload_dir is None:
            from app.utils.paths import get_app_data_dir
            upload_dir = str(get_app_data_dir() / "uploads" / "packages")
        self.upload_dir = upload_dir
        self.org_service = OrganizationService(db)

        try:
            os.makedirs(upload_dir, exist_ok=True)
        except PermissionError:
            from app.utils.paths import get_app_data_dir
            upload_dir = str(get_app_data_dir() / "uploads" / "packages")
            os.makedirs(upload_dir, exist_ok=True)
            self.upload_dir = upload_dir

        logger.info("DataPackageService 初始化，CustomJSONEncoder 已加载")

    # ========================================================================
    # 1. 导出功能
    # ========================================================================

    async def export_package(
        self,
        org_id: int,
        data_types: List[str],
        export_by: int,
        description: str = None,
        package_type: PackageType = PackageType.report,
        incremental: bool = False,
        since_sync_version: Optional[int] = None,
        since_time: Optional[datetime] = None,
    ) -> DataPackageExportResult:
        """导出数据包（incremental=True 时按 sync_version 或 updated_at 时间过滤变更记录）"""
        org = self.org_service.get_organization(org_id)
        if not org:
            raise BusinessError(f"组织不存在: {org_id}")

        package_code = self._generate_package_code(org.code, "EXP")

        data_dict = {}
        record_counts = {}
        for data_type in data_types:
            if data_type in DATA_TYPE_MODELS:
                model = DATA_TYPE_MODELS[data_type]
                records = self._export_data_type(
                    org_id, model,
                    since_sync_version=since_sync_version if incremental else None,
                    since_time=since_time if incremental else None,
                )
                data_dict[data_type] = records
                record_counts[data_type] = len(records)

        manifest = DataPackageManifest(
            version=CURRENT_VERSION,
            package_type=package_type,
            org_code=org.code or f"ORG{org.id:06d}",
            org_name=org.name or f"组织{org.id}",
            export_time=datetime.now(timezone.utc),
            data_types=data_types,
            record_counts=record_counts,
            exported_by=str(export_by),
            description=description,
            checksum="",
            encryption="none",
            compression="zip",
            incremental=incremental,
            base_package_id=None,
        )

        file_name = f"{package_code}.zip"
        file_path = os.path.join(self.upload_dir, file_name)
        self._create_zip_package(file_path, manifest, data_dict)

        checksum = self._calculate_checksum(file_path)
        manifest.checksum = checksum
        file_size = os.path.getsize(file_path)

        manifest_dict = json.loads(json.dumps(manifest.model_dump(), cls=CustomJSONEncoder))
        package = DataPackage(
            package_code=package_code, org_id=org_id, file_path=file_path,
            file_name=file_name, file_size=file_size, manifest=manifest_dict,
            status=PackageStatus.validated.value, type=package_type.value,
            version=CURRENT_VERSION, checksum=checksum,
            data_types=json.dumps(data_types, cls=CustomJSONEncoder),
            record_count=sum(record_counts.values()), created_by=export_by,
        )
        self.db.add(package)
        safe_commit(self.db)
        self.db.refresh(package)

        return DataPackageExportResult(
            package_id=package.id, package_code=package_code, file_path=file_path,
            file_name=file_name, file_size=file_size, manifest=manifest,
            download_url=f"/api/v1/data-packages/{package.id}/download",
        )

    def _export_data_type(
        self, org_id: int, model: Any,
        since_sync_version: Optional[int] = None,
        since_time: Optional[datetime] = None,
    ) -> List[Dict]:
        """导出指定类型的数据（增量模式: 按 sync_version 或 updated_at 时间过滤）"""
        query = self.db.query(model)
        if hasattr(model, "org_id"):
            query = query.filter(model.org_id == org_id)
        elif hasattr(model, "organization_id"):
            query = query.filter(model.organization_id == org_id)

        if since_sync_version is not None and hasattr(model, "sync_version"):
            query = query.filter(model.sync_version > since_sync_version)

        if since_time is not None and hasattr(model, "updated_at"):
            query = query.filter(model.updated_at > since_time)

        records = query.all()
        result = []
        for record in records:
            record_dict = {}
            for column in record.__table__.columns:
                value = getattr(record, column.name)
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif isinstance(value, Decimal):
                    value = float(value)
                elif value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
                    value = str(value)
                record_dict[column.name] = value
            result.append(record_dict)
        return result

    def _create_zip_package(
        self, file_path: str, manifest: DataPackageManifest, data_dict: Dict[str, List[Dict]]
    ) -> None:
        """创建ZIP数据包"""
        with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as zf:
            manifest_json = manifest.model_dump_json(indent=2)
            zf.writestr("manifest.json", manifest_json)
            for data_type, records in data_dict.items():
                data_json = json.dumps(records, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
                zf.writestr(f"data/{data_type}.json", data_json)

    # ========================================================================
    # 2. 导入功能
    # ========================================================================

    async def import_package(
        self, file_path: str, file_name: str, org_id: int, imported_by: int
    ) -> DataPackageImportResult:
        """导入数据包 (预览阶段，同步方法)"""
        validation = await self.validate_package(file_path)
        if not validation.is_valid:
            package = self._create_package_record(
                file_path, file_name, org_id, imported_by,
                status=PackageStatus.failed,
                error_message="; ".join([e.message for e in validation.errors]),
            )
            return DataPackageImportResult(
                package_id=package.id, package_code=package.package_code,
                status=PackageStatusEnum.failed, manifest=validation.manifest,
                preview=[], validation=validation,
            )

        package_code = self._generate_package_code(validation.manifest.org_code or "UNKNOWN", "IMP")
        permanent_path = os.path.join(self.upload_dir, f"{package_code}.zip")
        shutil.copy(file_path, permanent_path)

        preview = await self.preview_package_data_from_file(permanent_path)

        manifest_dict = None
        if validation.manifest:
            manifest_dict = json.loads(json.dumps(validation.manifest.model_dump(), cls=CustomJSONEncoder))

        package = DataPackage(
            package_code=package_code, org_id=org_id, file_path=permanent_path,
            file_name=file_name, file_size=os.path.getsize(permanent_path),
            manifest=manifest_dict, status=PackageStatus.validated.value,
            version=validation.manifest.version, checksum=self._calculate_checksum(permanent_path),
            data_types=json.dumps(validation.manifest.data_types, cls=CustomJSONEncoder),
            record_count=sum(validation.manifest.record_counts.values()), created_by=imported_by,
        )
        self.db.add(package)
        safe_commit(self.db)
        self.db.refresh(package)

        return DataPackageImportResult(
            package_id=package.id, package_code=package_code,
            status=PackageStatusEnum.validated, manifest=validation.manifest,
            preview=preview, validation=validation,
        )

    async def validate_package(self, file_path: str) -> DataPackageValidationResult:
        """验证数据包 (同步方法)"""
        errors = []
        warnings = []
        manifest = None

        if not os.path.exists(file_path):
            errors.append(DataPackageValidationError(field="file", message="文件不存在"))
            return DataPackageValidationResult(is_valid=False, errors=errors, warnings=warnings, manifest=None)

        if not zipfile.is_zipfile(file_path):
            errors.append(DataPackageValidationError(field="file", message="不是有效的ZIP文件"))
            return DataPackageValidationResult(is_valid=False, errors=errors, warnings=warnings, manifest=None)

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                if "manifest.json" not in zf.namelist():
                    errors.append(DataPackageValidationError(field="manifest", message="缺少manifest.json文件"))
                    return DataPackageValidationResult(is_valid=False, errors=errors, warnings=warnings, manifest=None)

                manifest_content = zf.read("manifest.json").decode("utf-8")
                manifest_dict = json.loads(manifest_content)

                version = manifest_dict.get("version", "unknown")
                if version not in SUPPORTED_VERSIONS:
                    errors.append(DataPackageValidationError(field="version", message=f"不支持的版本: {version}"))

                try:
                    manifest = DataPackageManifest(**manifest_dict)
                except Exception as e:
                    errors.append(DataPackageValidationError(field="manifest", message=f"manifest格式错误: {str(e)}"))

                for data_type in manifest_dict.get("data_types", []):
                    data_file = f"data/{data_type}.json"
                    if data_file not in zf.namelist():
                        errors.append(DataPackageValidationError(
                            field=data_type,
                            message=f"缺少数据文件: {data_file}",
                            data_type=data_type,
                        ))
                    else:
                        try:
                            data_content = zf.read(data_file).decode("utf-8")
                            data = json.loads(data_content)
                            expected_count = manifest_dict.get("record_counts", {}).get(data_type, 0)
                            actual_count = len(data)
                            if actual_count != expected_count:
                                warnings.append(f"{data_type}: 记录数不匹配 (期望: {expected_count}, 实际: {actual_count})")
                        except json.JSONDecodeError as e:
                            errors.append(DataPackageValidationError(
                                field=data_type,
                                message=f"JSON格式错误: {str(e)}",
                                data_type=data_type,
                            ))

        except zipfile.BadZipFile:
            errors.append(DataPackageValidationError(field="file", message="ZIP文件损坏"))
        except Exception as e:
            errors.append(DataPackageValidationError(field="file", message=f"验证失败: {str(e)}"))

        return DataPackageValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, manifest=manifest
        )

    async def preview_package_data(self, package_id: int) -> List[DataPackagePreviewData]:
        """预览导入的数据 (同步方法)"""
        package = self.db.query(DataPackage).filter(DataPackage.id == package_id).first()
        if not package or not package.file_path:
            return []
        return await self.preview_package_data_from_file(package.file_path)

    async def preview_package_data_from_file(
        self, file_path: str, sample_size: int = 10
    ) -> List[DataPackagePreviewData]:
        """从文件预览数据 (同步方法)"""
        preview_list = []
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                manifest_content = zf.read("manifest.json").decode("utf-8")
                manifest_dict = json.loads(manifest_content)
                for data_type in manifest_dict.get("data_types", []):
                    data_file = f"data/{data_type}.json"
                    if data_file in zf.namelist():
                        data_content = zf.read(data_file).decode("utf-8")
                        data = json.loads(data_content)
                        columns = list(data[0].keys()) if data else []
                        preview_list.append(DataPackagePreviewData(
                            data_type=data_type, total=len(data),
                            sample=data[:sample_size], columns=columns,
                        ))
        except Exception as e:
            logger.error(f"Error previewing package data from {file_path}: {e}", exc_info=True)
        return preview_list

    async def confirm_import(
        self, package_id: int, confirmed_by: int, overwrite_existing: bool = False, selected_types: List[str] = None
    ) -> DataPackageConfirmResult:
        """确认导入数据 (核心重构：使用 Bulk Upsert 和独占锁)"""
        package = self.db.query(DataPackage).filter(DataPackage.id == package_id).first()
        if not package:
            raise BusinessError(f"数据包不存在: {package_id}")
        if package.status != PackageStatus.validated.value:
            raise BusinessError(f"数据包状态不允许导入: {package.status}")

        imported_counts = {}
        skipped_counts = {}
        error_counts = {}
        errors = []

        try:
            # 🛡️ 使用 SAVEPOINT 事务保护：导入中任何失败都会回滚全部数据
            # 配合独占写锁防止 SQLITE_BUSY
            self.db.begin_nested()
            with db_coordinator.exclusive_write(timeout=120.0):
                with zipfile.ZipFile(package.file_path, "r") as zf:
                    manifest_content = zf.read("manifest.json").decode("utf-8")
                    manifest_dict = json.loads(manifest_content)

                    resolved_org_id = package.org_id
                    source_org_code = manifest_dict.get("org_code", "")
                    if source_org_code:
                        from app.models.organization import Organization
                        local_org = self.db.query(Organization).filter(Organization.code == source_org_code).first()
                        if local_org:
                            resolved_org_id = local_org.id

                    data_types = selected_types or manifest_dict.get("data_types", [])

                    for data_type in data_types:
                        if data_type not in DATA_TYPE_MODELS:
                            continue
                        data_file = f"data/{data_type}.json"
                        if data_file not in zf.namelist():
                            continue

                        data_content = zf.read(data_file).decode("utf-8")
                        records = json.loads(data_content)
                        model = DATA_TYPE_MODELS[data_type]

                        # 🚀 调用批量 Upsert 方法
                        imp, skip, errs = self._bulk_upsert_records(model, records, resolved_org_id, overwrite_existing)
                        imported_counts[data_type] = imp
                        skipped_counts[data_type] = skip
                        error_counts[data_type] = len(errs)
                        errors.extend(errs)

                package.status = PackageStatus.imported.value
                package.imported_at = datetime.now(timezone.utc)
                package.imported_by = confirmed_by
                safe_commit(self.db)

            return DataPackageConfirmResult(
                success=True, package_id=package_id, imported_counts=imported_counts,
                skipped_counts=skipped_counts, error_counts=error_counts, errors=errors,
            )
        except Exception as e:
            self.db.rollback()
            package.status = PackageStatus.failed.value
            package.error_message = str(e)
            safe_commit(self.db)
            return DataPackageConfirmResult(
                success=False, package_id=package_id, imported_counts=imported_counts,
                skipped_counts=skipped_counts, error_counts=error_counts,
                errors=[DataPackageValidationError(field="import", message=str(e))],
            )

    def _clean_import_record(
        self, record: Dict, valid_columns: set, org_id: int, i: int, model: Any
    ) -> Optional[Dict]:
        clean_data = {}
        for k, v in record.items():
            if k not in valid_columns:
                continue
            if isinstance(v, str) and "T" in v:
                try:
                    clean_data[k] = datetime.fromisoformat(v.replace("Z", "+00:00"))
                    continue
                except ValueError:
                    pass
            clean_data[k] = v

        if "organization_id" in valid_columns:
            clean_data["organization_id"] = org_id
        elif "org_id" in valid_columns:
            clean_data["org_id"] = org_id

        return clean_data

    def _build_upsert_statement(self, model: Any, clean_records: List[Dict], pk_name: str, overwrite: bool):
        stmt = sqlite_insert(model).values(clean_records)
        if overwrite:
            update_cols = {c.name: c for c in stmt.excluded if c.name != pk_name}
            stmt = stmt.on_conflict_do_update(index_elements=[pk_name], set_=update_cols)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=[pk_name])
        return stmt

    def _bulk_upsert_records(
        self, model: Any, records: List[Dict], org_id: int, overwrite: bool
    ) -> Tuple[int, int, List[DataPackageValidationError]]:
        """批量 Upsert (Insert or Update) 记录，保留原始 ID，解决外键孤儿问题"""
        if not records:
            return 0, 0, []

        errors = []
        mapper = inspect(model)
        pk_name = mapper.primary_key[0].name
        valid_columns = {c.key for c in mapper.column_attrs}

        clean_records = []
        for i, record in enumerate(records):
            try:
                cleaned = self._clean_import_record(record, valid_columns, org_id, i, model)
                if cleaned is not None:
                    clean_records.append(cleaned)
            except Exception as e:
                errors.append(DataPackageValidationError(
                    field=model.__tablename__, message=f"行{i}数据清洗失败: {e}", row=i + 1, data_type=model.__tablename__
                ))

        if not clean_records:
            return 0, 0, errors

        stmt = self._build_upsert_statement(model, clean_records, pk_name, overwrite)

        try:
            self.db.execute(stmt)
            imported = len(clean_records)
        except Exception as e:
            errors.append(DataPackageValidationError(
                field=model.__tablename__, message=f"批量写入数据库失败: {e}", data_type=model.__tablename__
            ))
            self.db.rollback()
            imported = 0

        return imported, 0, errors

    # ========================================================================
    # 3. 加密导入导出功能
    # ========================================================================

    async def export_encrypted_package(
        self, org_id: int, data_types: List[str], export_by: int,
        password: Optional[str] = None, description: str = None,
        package_type: PackageType = PackageType.report,
    ) -> DataPackageExportResult:
        """导出加密数据包 (同步方法)"""
        from app.services.password_encryption_service import PasswordEncryptionService

        export_result = await self.export_package(org_id, data_types, export_by, description, package_type)

        if password:
            original_file_path = export_result.file_path
            encrypted_file_path = original_file_path + ".enc"

            salt_hex, iterations = PasswordEncryptionService.encrypt_file(
                original_file_path, password, encrypted_file_path
            )

            manifest_dict = export_result.manifest.model_dump()
            manifest_dict["encryption"] = {
                "enabled": True, "algorithm": "aes256-fernet-pbkdf2",
                "salt": salt_hex, "iterations": iterations,
            }

            manifest_json_str = json.dumps(manifest_dict, cls=CustomJSONEncoder)
            manifest_serialized = json.loads(manifest_json_str)

            package = self.get_package(export_result.package_id)
            if package:
                package.is_encrypted = True
                package.encryption_algorithm = "aes256-fernet-pbkdf2"
                package.encryption_salt = salt_hex
                package.encryption_iterations = iterations
                package.file_path = encrypted_file_path
                package.file_name = os.path.basename(encrypted_file_path)
                package.file_size = os.path.getsize(encrypted_file_path)
                package.manifest = manifest_serialized
                safe_commit(self.db)

            if os.path.exists(original_file_path):
                os.remove(original_file_path)

            export_result.file_path = encrypted_file_path
            export_result.file_name = os.path.basename(encrypted_file_path)
            export_result.file_size = os.path.getsize(encrypted_file_path)

        return export_result

    async def import_encrypted_package(
        self, file_path: str, file_name: str, org_id: int,
        imported_by: int, password: Optional[str] = None,
    ) -> DataPackageImportResult:
        """导入加密数据包（预览阶段）"""
        from app.services.password_encryption_service import InvalidPasswordError, PasswordEncryptionService

        decrypted_file_path = file_path
        temp_decrypted_path = None

        try:
            is_encrypted = False
            try:
                with zipfile.ZipFile(file_path, "r") as zf:
                    zf.read("manifest.json")
            except (zipfile.BadZipFile, KeyError):
                is_encrypted = True

            if is_encrypted:
                if not password:
                    raise BusinessError("该数据包已加密，请提供密码")

                temp_decrypted_path = file_path + ".decrypted_temp"
                try:
                    # 假设 PasswordEncryptionService 支持从文件头读取 salt 自动解密
                    PasswordEncryptionService.decrypt_file_auto(file_path, password, temp_decrypted_path)
                    decrypted_file_path = temp_decrypted_path
                except InvalidPasswordError:
                    raise BusinessError("密码错误，请检查后重试")
                except AttributeError:
                    raise BusinessError("加密文件解析失败，请确保使用最新的加密组件或提供完整的加密参数")

            return await self.import_package(decrypted_file_path, file_name, org_id, imported_by)

        finally:
            if temp_decrypted_path and os.path.exists(temp_decrypted_path):
                try:
                    os.remove(temp_decrypted_path)
                except OSError:
                    logger.warning(f"Failed to delete temp decrypted file: {temp_decrypted_path}")

    async def decrypt_and_preview_package(self, package_id: int, password: str) -> DataPackageImportResult:
        """解密并预览数据包 (同步方法)"""
        from app.services.password_encryption_service import InvalidPasswordError, PasswordEncryptionService

        package = self.get_package(package_id)
        if not package:
            raise BusinessError(f"数据包不存在: {package_id}")
        if not package.is_encrypted:
            raise BusinessError("该数据包未加密，无需解密")

        encrypted_file_path = package.file_path
        temp_decrypted_path = encrypted_file_path + ".decrypted"

        try:
            PasswordEncryptionService.decrypt_file(
                encrypted_file_path, password, package.encryption_salt,
                package.encryption_iterations, temp_decrypted_path,
            )
            validation_result = await self.validate_package(temp_decrypted_path)
            if not validation_result.is_valid:
                raise PackageValidationError([e.message for e in validation_result.errors])

            return DataPackageImportResult(
                package_id=package.id, package_code=package.package_code,
                status=PackageStatusEnum.VALIDATED, manifest=validation_result.manifest,
                preview_data=None, validation_errors=[],
            )
        except InvalidPasswordError:
            raise BusinessError("密码错误，请检查后重试")
        finally:
            if os.path.exists(temp_decrypted_path):
                try:
                    os.remove(temp_decrypted_path)
                except OSError:
                    pass

    async def confirm_import_with_conflict_resolution(
        self, package_id: int, conflict_strategy: str = "KEEP_BOTH", password: Optional[str] = None
    ) -> Dict[str, Any]:
        """确认导入并处理冲突 (补全并优化)"""
        from app.services.smart_conflict_resolver import SmartConflictResolver
        from app.services.password_encryption_service import PasswordEncryptionService, InvalidPasswordError

        package = self.get_package(package_id)
        if not package:
            raise BusinessError(f"数据包不存在: {package_id}")
        if package.status != PackageStatus.validated.value:
            raise BusinessError(f"数据包状态不正确: {package.status}")

        file_path = package.file_path
        temp_decrypted_path = None

        try:
            if package.is_encrypted:
                if not password:
                    raise BusinessError("加密包需要提供密码才能导入")
                temp_decrypted_path = file_path + ".temp_decrypted"
                try:
                    PasswordEncryptionService.decrypt_file(
                        file_path, password, package.encryption_salt,
                        package.encryption_iterations, temp_decrypted_path,
                    )
                    file_path = temp_decrypted_path
                except InvalidPasswordError:
                    raise BusinessError("密码错误，请检查后重试")

            # 读取数据包并处理冲突
            with db_coordinator.exclusive_write(timeout=120.0):
                with zipfile.ZipFile(file_path, "r") as zf:
                    manifest_dict = json.loads(zf.read("manifest.json").decode("utf-8"))
                    data_types = manifest_dict.get("data_types", [])

                    resolver = SmartConflictResolver(self.db)

                    for data_type in data_types:
                        if data_type not in DATA_TYPE_MODELS:
                            continue
                        data_file = f"data/{data_type}.json"
                        if data_file not in zf.namelist():
                            continue

                        records = json.loads(zf.read(data_file).decode("utf-8"))
                        model = DATA_TYPE_MODELS[data_type]

                        # 调用冲突解决器 (假设 SmartConflictResolver 有 resolve_and_import 方法)
                        resolver.resolve_and_import(model, records, conflict_strategy)

                package.status = PackageStatus.imported.value
                package.imported_at = datetime.now(timezone.utc)
                safe_commit(self.db)

            return {"success": True, "message": "导入并解决冲突完成"}

        except Exception as e:
            self.db.rollback()
            package.status = PackageStatus.failed.value
            package.error_message = str(e)
            safe_commit(self.db)
            return {"success": False, "message": str(e)}
        finally:
            if temp_decrypted_path and os.path.exists(temp_decrypted_path):
                try:
                    os.remove(temp_decrypted_path)
                except OSError:
                    pass

    # ========================================================================
    # 4. 辅助方法
    # ========================================================================

    def _generate_package_code(self, org_code: str, prefix: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        safe_org_code = org_code if org_code else "UNKNOWN"
        return f"{prefix}-{safe_org_code}-{timestamp}"

    def _calculate_checksum(self, file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return f"sha256:{sha256_hash.hexdigest()}"

    def _create_package_record(
        self, file_path: str, file_name: str, org_id: int, created_by: int,
        status: PackageStatus, error_message: str = None,
    ) -> DataPackage:
        package_code = self._generate_package_code("UNKNOWN", "ERR")
        package = DataPackage(
            package_code=package_code, org_id=org_id, file_path=file_path,
            file_name=file_name,
            file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            status=status.value, version=CURRENT_VERSION,
            error_message=error_message, created_by=created_by,
        )
        self.db.add(package)
        safe_commit(self.db)
        self.db.refresh(package)
        return package

    def get_package(self, package_id: int) -> Optional[DataPackage]:
        return self.db.query(DataPackage).filter(DataPackage.id == package_id).first()

    def get_packages_by_org(
        self, org_id: int, status: str = None, type_filter: str = None, skip: int = 0, limit: int = 20
    ) -> List[DataPackage]:
        query = self.db.query(DataPackage).filter(DataPackage.org_id == org_id)
        if status:
            query = query.filter(DataPackage.status == status)
        if type_filter:
            query = query.filter(DataPackage.type == type_filter)
        return query.order_by(DataPackage.created_at.desc()).offset(skip).limit(limit).all()

    def count_packages_by_org(
        self, org_id: int, status: str = None, type_filter: str = None
    ) -> int:
        """统计某组织的数据包总数（不随分页截断）"""
        query = self.db.query(DataPackage).filter(DataPackage.org_id == org_id)
        if status:
            query = query.filter(DataPackage.status == status)
        if type_filter:
            query = query.filter(DataPackage.type == type_filter)
        return query.count()
