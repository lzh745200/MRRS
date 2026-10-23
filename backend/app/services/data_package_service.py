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
import time
import uuid
import zipfile
from datetime import timezone, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import inspect
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from fastapi import HTTPException

from app.core.database import db_coordinator
from app.core.exceptions import BusinessError
from app.core.json_encoder import CustomJSONEncoder
from app.core.logging import logger
from app.models.data_package import DataPackage, PackageStatus, PackageType
from app.models.project import Fund, Project
from app.models.school import School
from app.models.supported_village import SupportedVillage
from app.utils.upload_helper import ensure_zip_within_limit, read_zip_member
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
from app.services.package_record_validator import validate_records
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


# W18-D1：跨机导入的业务键（用于判定"主键相同的两行是不是同一条业务记录"）。
# 背景：数据包导出包含自增 id，两台机器都从 id=1 起步 —— 以 id 作冲突键会把
# 目标机的真实记录整体覆写成源机数据（organization_id/created_at 一并改写，
# 不可逆）。SQLite 下这不是概率问题而是必现。
#
# 业务键原则：**能稳定区分"同一条记录"与"两条不同记录"**。
#
# W27 修复（W26 全栈检测 P0-1「同组织跨机主键碰撞」）
# --------------------------------------------------
# 旧定义只有一个字段：
#     {"supported_villages": ("organization_id",), ... 全部仅 organization_id }
# 而导入时 ``_clean_record`` 又把**每条记录**的 organization_id 强制改写为目标组织
# （见下方 :698-701 附近）—— 于是「同组织两台机器」这一**最常见部署**下，所有
# 记录的业务键完全相同，"判定为同一条记录"恒成立：
#     * overwrite=True  → 本机真实记录被源机数据覆写（不可逆）
#     * overwrite=False → 源机记录被静默丢弃
#     * relocated（换新 id 插入）分支永不触发
# 即 W18-D1 当年的修复**只在跨组织场景成立**。
#
# 现改为「组织 + 业务唯一标识」：
#   * projects / schools 的 ``code`` 在 DB 层就是 **UNIQUE** 列，天然可作身份；
#   * funds 的 ``code`` 按 ADR-0011（``ZJ+年份+6位流水``）生成，是业务编号；
#   * supported_villages 无单列唯一键，用「组织 + 县 + 村名」复合键。
#     **为什么只到"县"不再细分乡镇**：县内的行政村名在行政区划上唯一，足以区分
#     记录；而乡镇/街道常因历史数据未填而在导入时缺失 —— 把可选字段纳入业务键会
#     让键频繁"不可判定"，退化成 relocated（每次都新增重复行）。用最少的必填字段
#     换取"既不误合并、也不无谓重复"。
# 仍保留 organization_id：导入会把记录归到目标组织，带组织可确保**跨组织**导出/
# 导入时不会把别组织的同编号记录误认为同一条（保持 W18-D1 的正确行为）。
#
# 已知取舍（有意为之）：村庄**改名**会导致业务键变化 → 判为"两条不同记录" →
# 源机记录以新 id 插入，产生重复行。重复行可人工合并（可恢复），而覆写不可恢复，
# 故在"重复"与"丢失"之间必须选前者。
BUSINESS_KEYS: Dict[str, tuple] = {
    "supported_villages": ("organization_id", "county", "village_name"),
    "projects": ("organization_id", "code"),
    "funds": ("organization_id", "code"),
    "schools": ("organization_id", "code"),
}


def _business_key_of(model: Any, record: Dict) -> Optional[tuple]:
    """取记录的业务键值；任一键缺失/为空则返回 None（无法判定 → 按"不同记录"处理）。"""
    keys = BUSINESS_KEYS.get(getattr(model, "__tablename__", ""))
    if not keys:
        return None
    values = []
    for k in keys:
        v = record.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        values.append(v)
    return tuple(values)


def _enum_column_map(model: Any) -> Dict[str, Any]:
    """收集模型的 Enum 列 → 枚举类映射（W22 上报链路：导出时枚举名归一枚举值）。"""
    enum_columns: Dict[str, Any] = {}
    for column in model.__table__.columns:
        enum_class = getattr(getattr(column, "type", None), "enum_class", None)
        if enum_class is not None:
            enum_columns[column.name] = enum_class
    return enum_columns


def _normalize_enum_export_value(value: Any, enum_class: Any) -> Any:
    """把数据库中的枚举名（SQLAlchemy 默认存储形态）归一为枚举值。

    导入侧字段校验只接受枚举值（如 ``primary``）；若导出保留 ORM 名称
    （``PRIMARY``）会导致上报包整表校验失败。非字符串/历史脏值原样返回，
    由导入校验给出明细。
    """
    if enum_class is None or not isinstance(value, str):
        return value
    try:
        return enum_class[value].value
    except KeyError:
        try:
            return enum_class(value).value
        except ValueError:
            return value


def _normalize_export_data_value(value: Any) -> Any:
    """导出值归一：datetime→ISO、Decimal→float、其他非 JSON 原生类型→str。"""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
        return str(value)
    return value


def _local_pii_key_fingerprint() -> str:
    """本机 PII 密钥指纹；密钥不可用时返回空串（导出不因密钥问题失败）。"""
    try:
        from app.core.pii_crypto import key_fingerprint

        return key_fingerprint()
    except Exception:
        logger.warning("读取 PII 密钥指纹失败，数据包将不携带指纹", exc_info=True)
        return ""


class PackageValidationError(BusinessError):
    """数据包验证错误"""
    def __init__(self, errors: List[str]):
        super().__init__(f"数据包验证失败: {', '.join(errors[:3])}")
        self.errors = errors


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
        owner_id: Optional[int] = None,
        exported_by_name: Optional[str] = None,
        base_package_id: Optional[int] = None,
    ) -> DataPackageExportResult:
        """导出数据包（incremental=True 时按 sync_version 或 updated_at 时间过滤变更记录）

        owner_id 非 None 时仅导出该用户本人录入（created_by）的记录，
        manifest 标记 export_scope=self；为 None 时导出全组织（export_scope=org）。
        """
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
                    owner_id=owner_id,
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
            base_package_id=base_package_id,
            export_scope="self" if owner_id is not None else "org",
            exported_by_name=exported_by_name,
            key_fingerprint=_local_pii_key_fingerprint(),
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
            # `DataPackage.data_types` 是 JSON 列，**必须直接存列表**。
            # R28 修复：这里曾 `json.dumps(...)` 双重编码，列里落的是 JSON *字符串*，
            # 读出来是 `'["villages", …]'` → 消费方按可迭代对象遍历时逐字符处理
            # （版本变更摘要的键变成 `[`、`"`、`v`… 见 _package_version_changes）。
            data_types=data_types,
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
        owner_id: Optional[int] = None,
    ) -> List[Dict]:
        """导出指定类型的数据（增量模式: 按 sync_version 或 updated_at 时间过滤）

        owner_id 非 None 且模型有 created_by 列时，仅导出该用户本人录入的记录。
        """
        # W18-D8：改用 raw SQL 拉取 —— 走 ORM 时 EncryptedText 的 TypeDecorator 会把
        # PII 列**解密成明文**带进数据包（uploads/packages/*.zip 明文存活 7 天，还会被
        # include_uploads 备份一起带走）；data_sync 链（.zip/.rrs）走 raw SQL 拿到的就是
        # **密文**。两条同步链对 PII 处理相反是 D8 的核心：统一为密文出包（跨机部署本就
        # 要求相同 ENCRYPTION_KEY，见 ADR-0005），导入侧沿用 TypeDecorator 透明解密/加密，
        # 同密钥跨机导入后可读。表名/列名来自模型元数据，非用户输入，无注入面。
        from sqlalchemy import text as _sql_text

        table = model.__tablename__
        col_names = [c.name for c in model.__table__.columns]
        col_list = ", ".join(col_names)
        # 本行的表名/列名全部来自模型元数据（非用户输入），过滤值一律走 text() 绑定参数
        sql = "SELECT %s FROM %s" % (col_list, table)  # nosec B608 - 表名/列名取自 model.__table__ 元数据，无用户输入拼接
        params = {}
        conditions = []
        if hasattr(model, "org_id"):
            conditions.append("org_id = :org_id")
            params["org_id"] = org_id
        elif hasattr(model, "organization_id"):
            conditions.append("organization_id = :org_id")
            params["org_id"] = org_id
        if owner_id is not None and hasattr(model, "created_by"):
            conditions.append("created_by = :owner_id")
            params["owner_id"] = owner_id
        if since_sync_version is not None and hasattr(model, "sync_version"):
            conditions.append("sync_version > :since_sync")
            params["since_sync"] = since_sync_version
        if since_time is not None and hasattr(model, "updated_at"):
            conditions.append("updated_at > :since_time")
            params["since_time"] = since_time
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        rows = self.db.execute(_sql_text(sql), params).fetchall()

        # W22 数据上报链路修复：raw SQL 取到的是数据库存储值 —— SQLAlchemy Enum
        # （native_enum=False）默认落库的是**枚举名**（如 `PRIMARY`/`INACTIVE`），
        # 而导入侧字段校验只接受**枚举值**（`primary`/`inactive`）→ 上报包被整表
        # rejected，上级接收后学校/项目等数据不可见。这里把枚举列归一为 `.value`
        # （PII 列仍保持密文原样，不影响 W18-D8）。
        enum_columns = _enum_column_map(model)
        result = []
        for row in rows:
            record_dict = {}
            for col_name, value in zip(col_names, row):
                value = _normalize_enum_export_value(value, enum_columns.get(col_name))
                record_dict[col_name] = _normalize_export_data_value(value)
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
            # R9：校验失败分支**不落 file_path**——该路径是 API 层的临时文件，
            # 由调用方 finally 立即 unlink（见 data_packages.py import 端点），
            # 落库后记录会永久指向不存在的文件：/validate、/download 恒报
            # "文件不存在"且无修复路径。此处置 NULL，端点对 file_path 为空
            # 返回 409 明确语义（校验失败已拒绝），错误明细随 error_message 保留。
            package = self._create_package_record(
                None, file_name, org_id, imported_by,
                status=PackageStatus.failed,
                error_message="; ".join([e.message for e in validation.errors]),
            )
            return DataPackageImportResult(
                package_id=package.id, package_code=package.package_code,
                # R9 顺带修复：PackageStatusEnum 成员为**大写** FAILED，
                # 原 `PackageStatusEnum.failed` 必抛 AttributeError → 校验失败
                # 分支被端点兜底成 500「导入失败」，用户看不到真实校验原因
                # （既有单测用 patch 掩盖了该缺陷）。
                status=PackageStatusEnum.FAILED, manifest=validation.manifest,
                preview=[], validation=validation,
            )

        package_code = self._generate_package_code(validation.manifest.org_code or "UNKNOWN", "IMP")
        permanent_path = os.path.join(self.upload_dir, f"{package_code}.zip")
        shutil.copy(file_path, permanent_path)

        preview = await self.preview_package_data_from_file(permanent_path)

        manifest_dict = None
        if validation.manifest:
            manifest_dict = json.loads(json.dumps(validation.manifest.model_dump(), cls=CustomJSONEncoder))
            # 校验摘要随包记录落库（additive），供 /received 接收记录展示
            manifest_dict["validation_summary"] = validation.warnings

        package = DataPackage(
            package_code=package_code, org_id=org_id, file_path=permanent_path,
            file_name=file_name, file_size=os.path.getsize(permanent_path),
            manifest=manifest_dict, status=PackageStatus.validated.value,
            version=validation.manifest.version, checksum=self._calculate_checksum(permanent_path),
            # JSON 列直接存列表（R28 修复双重编码，同 export_package）
            data_types=validation.manifest.data_types,
            record_count=sum(validation.manifest.record_counts.values()), created_by=imported_by,
        )
        self.db.add(package)
        safe_commit(self.db)
        self.db.refresh(package)

        return DataPackageImportResult(
            package_id=package.id, package_code=package_code,
            status=PackageStatusEnum.VALIDATED, manifest=validation.manifest,
            preview=preview, validation=validation,
        )

    def _check_pii_key_fingerprint(self, manifest_dict: dict, errors: List) -> None:
        """PII 密钥漂移校验（P1-2）。

        PII 列以**密文**出包（见 `_export_data_type` 的 W18-D8 决策），目标机密钥
        不同则密文永久不可解（UI 显示 `enc.v1:...` 乱码，用户以为"同步成功"）。
        旧包无该字段 → 跳过（向后兼容）；本机指纹不可用 → 不误拦。
        """
        package_fp = str(manifest_dict.get("key_fingerprint") or "").strip()
        if not package_fp:
            return
        local_fp = _local_pii_key_fingerprint()
        if local_fp and package_fp != local_fp:
            errors.append(DataPackageValidationError(
                field="key_fingerprint",
                message=(
                    "数据包由不同 PII 密钥的机器导出（包 %s / 本机 %s），"
                    "导入后身份证、手机号等加密字段将无法解密。"
                    "请先在「系统管理→运维与监控→PII 密钥」导入源机密钥，"
                    "或改用不含 PII 的数据包。" % (package_fp, local_fp)
                ),
            ))

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
                # R2 第三层（遗留风险治理补漏）：上传的包是**用户可控 zip**，
                # 容器体积合规 ≠ 解压后合规（1MB deflate 可膨胀到数十 GB）。
                # 原先此处直接 zf.read 全量物化 → 单请求即可耗尽内存。
                ensure_zip_within_limit(zf)
                if "manifest.json" not in zf.namelist():
                    errors.append(DataPackageValidationError(field="manifest", message="缺少manifest.json文件"))
                    return DataPackageValidationResult(is_valid=False, errors=errors, warnings=warnings, manifest=None)

                manifest_content = read_zip_member(zf, "manifest.json").decode("utf-8")
                manifest_dict = json.loads(manifest_content)

                version = manifest_dict.get("version", "unknown")
                if version not in SUPPORTED_VERSIONS:
                    errors.append(DataPackageValidationError(field="version", message=f"不支持的版本: {version}"))

                try:
                    manifest = DataPackageManifest(**manifest_dict)
                except Exception as e:
                    errors.append(DataPackageValidationError(field="manifest", message=f"manifest格式错误: {str(e)}"))

                self._check_pii_key_fingerprint(manifest_dict, errors)

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
                            data_content = read_zip_member(zf, data_file).decode("utf-8")
                            data = json.loads(data_content)
                            expected_count = manifest_dict.get("record_counts", {}).get(data_type, 0)
                            actual_count = len(data)
                            if actual_count != expected_count:
                                warnings.append(f"{data_type}: 记录数不匹配 (期望: {expected_count}, 实际: {actual_count})")
                            # 字段级校验：摘要写入 warnings（additive，不影响 errors 语义）
                            warnings.extend(self._field_validation_warnings(data_type, data))
                        except json.JSONDecodeError as e:
                            errors.append(DataPackageValidationError(
                                field=data_type,
                                message=f"JSON格式错误: {str(e)}",
                                data_type=data_type,
                            ))

        except HTTPException as e:
            # 解压后超限（压缩炸弹）是可读的业务结论，不该降级成"验证失败: ..." 噪声
            errors.append(DataPackageValidationError(field="file", message=str(e.detail)))
        except zipfile.BadZipFile:
            errors.append(DataPackageValidationError(field="file", message="ZIP文件损坏"))
        except Exception as e:
            errors.append(DataPackageValidationError(field="file", message=f"验证失败: {str(e)}"))

        return DataPackageValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings, manifest=manifest
        )

    @staticmethod
    def _field_validation_warnings(data_type: str, data: Any, max_detail: int = 5) -> List[str]:
        """字段级校验摘要（各类型 ok/corrected/rejected 计数 + 前 N 条问题明细）"""
        if not isinstance(data, list) or data_type not in DATA_TYPE_MODELS:
            return []
        fv = validate_records(data_type, data)
        lines = [
            f"{data_type}: 字段校验 通过{len(fv['ok'])}条/纠正{len(fv['corrected'])}条/拒绝{len(fv['rejected'])}条"
        ]
        for item in fv["rejected"][:max_detail]:
            lines.append(f"{data_type} 第{item['row'] + 1}行 校验未通过: {'；'.join(item['reasons'])}")
        for item in fv["corrected"][:max_detail]:
            lines.append(f"{data_type} 第{item['row'] + 1}行 已自动纠正: {'；'.join(item['fixes'])}")
        return lines

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
                ensure_zip_within_limit(zf)  # R2 第三层：预览同样不得物化未限长的成员
                manifest_content = read_zip_member(zf, "manifest.json").decode("utf-8")
                manifest_dict = json.loads(manifest_content)
                for data_type in manifest_dict.get("data_types", []):
                    data_file = f"data/{data_type}.json"
                    if data_file in zf.namelist():
                        data_content = read_zip_member(zf, data_file).decode("utf-8")
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
        self, package_id: int, confirmed_by: int, overwrite_existing: bool = False,
        selected_types: List[str] = None, ts_guard: bool = False,
    ) -> DataPackageConfirmResult:
        """确认导入数据。

        ts_guard（W18-D5）：True 时覆盖更新仅在包内记录比本地新时执行 ——
        增量包重复应用不再把本机新编辑打回旧版本。
        """
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
                    ensure_zip_within_limit(zf)  # R2 第三层：确认导入前先卡解压后总量
                    manifest_content = read_zip_member(zf, "manifest.json").decode("utf-8")
                    manifest_dict = json.loads(manifest_content)

                    # W18-D3（越权写）：原实现无条件用包内 manifest.org_code 反查本地
                    # 组织并**覆盖**调用者指定的目标组织，且不再校验调用者对该组织是否
                    # 可达 —— 部门级管理员把包导进本部门，数据实际写进别的部门
                    # （实证 org=B 导入落库 org=A）。
                    # 现改为：包内 org_code 只作**择一提示**，最终必须落在调用者有权写入的
                    # 组织集合内；不可达则沿用调用者指定的 package.org_id（端点已校验可达）。
                    resolved_org_id = package.org_id
                    source_org_code = manifest_dict.get("org_code", "")
                    if source_org_code:
                        from app.models.organization import Organization
                        local_org = self.db.query(Organization).filter(
                            Organization.code == source_org_code
                        ).first()
                        if local_org and local_org.id == package.org_id:
                            resolved_org_id = local_org.id
                        elif local_org:
                            logger.warning(
                                "W18-D3: 数据包 %s 的 manifest.org_code=%s 指向组织 %s，"
                                "与调用者指定的目标组织 %s 不一致；已忽略包内组织，按目标组织导入",
                                package_id, source_org_code, local_org.id, package.org_id,
                            )

                    data_types = selected_types or manifest_dict.get("data_types", [])

                    for data_type in data_types:
                        if data_type not in DATA_TYPE_MODELS:
                            continue
                        data_file = f"data/{data_type}.json"
                        if data_file not in zf.namelist():
                            continue

                        data_content = read_zip_member(zf, data_file).decode("utf-8")
                        records = json.loads(data_content)
                        model = DATA_TYPE_MODELS[data_type]

                        # 字段级校验：ok + corrected(纠正后数据) 进 upsert，rejected 跳过并记录明细
                        fv = validate_records(data_type, records)
                        accepted = fv["ok"] + [c["data"] for c in fv["corrected"]]
                        rejected = fv["rejected"]
                        for item in rejected:
                            errors.append(DataPackageValidationError(
                                field=data_type,
                                message=f"第{item['row'] + 1}行校验未通过: {'；'.join(item['reasons'])}",
                                row=item["row"] + 1,
                                data_type=data_type,
                            ))

                        # 🚀 调用批量 Upsert 方法
                        imp, skip, errs = self._bulk_upsert_records(
                            model, accepted, resolved_org_id, overwrite_existing,
                            ts_guard=ts_guard,
                        )
                        imported_counts[data_type] = imp
                        skipped_counts[data_type] = skip + len(rejected)
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
        # W18-D8：datetime 列集合（按列类型判定，字符串形态无论有无 "T" 都要解析 ——
        # raw SQL 导出的 ISO 串也可能以空格分隔，SQLite DateTime 只收 datetime 对象）
        datetime_cols = {
            c.name for c in model.__table__.columns
            if isinstance(getattr(c.type, "impl", None), type) and "DateTime" in type(c.type).__name__
            or (c.type is not None and "DateTime" in type(c.type).__name__)
        }
        clean_data = {}
        for k, v in record.items():
            if k not in valid_columns:
                continue
            if k in datetime_cols and isinstance(v, str):
                try:
                    parsed = datetime.fromisoformat(v.replace("Z", "+00:00").replace(" ", "T", 1))
                    # W18-D5：aware → naive UTC 归一。SQLite 存储侧是 naive UTC
                    # 字符串（TimestampMixin/DateTime 无时区），aware datetime 作为
                    # 绑定参数会被序列化成 "...+00:00" 后缀形态，与库内字符串比较时
                    # 字典序错乱 → 时间戳守卫（where excluded > local）失效。
                    if parsed.tzinfo is not None:
                        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
                    clean_data[k] = parsed
                    continue
                except ValueError:
                    pass
            elif isinstance(v, str) and "T" in v:
                try:
                    parsed = datetime.fromisoformat(v.replace("Z", "+00:00"))
                    if parsed.tzinfo is not None:
                        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
                    clean_data[k] = parsed
                    continue
                except ValueError:
                    pass
            elif isinstance(v, datetime) and v.tzinfo is not None:
                # 同上：直接传 datetime 的调用方（如回归测试）也要归一
                clean_data[k] = v.astimezone(timezone.utc).replace(tzinfo=None)
                continue
            clean_data[k] = v

        if "organization_id" in valid_columns:
            clean_data["organization_id"] = org_id
        elif "org_id" in valid_columns:
            clean_data["org_id"] = org_id

        return clean_data

    def _build_upsert_statement(
        self, model: Any, clean_records: List[Dict], pk_name: str, overwrite: bool,
        ts_guard: bool = False,
    ):
        """构造 SQLite upsert 语句。

        ts_guard（W18-D5）：True 时 UPDATE 仅在「包内 updated_at **晚于** 本地」时
        才执行 —— 增量包被重复应用时，旧包不能再覆盖本机新编辑（实测旧包把
        "版本2-本地新编辑"打回"版本1"）。DO NOTHING（非覆盖）不受影响。
        """
        stmt = sqlite_insert(model).values(clean_records)
        if overwrite:
            # M29（R27 排查）：`stmt.excluded` 为**表内全部列**提供伪列 —— 未出现在
            # VALUES 中的列在 excluded 里是 NULL，全量 set_ 会把「记录未携带的字段」
            # 写成 NULL、覆盖目标库已有值。分组（见 _bulk_upsert_records）保证组内
            # 键集合一致，这里只对本组实际携带的列生成 UPDATE。
            carried = set(clean_records[0].keys())
            update_cols = {
                c.name: c
                for c in stmt.excluded
                if c.name != pk_name and c.name in carried
            }
            if update_cols:
                if ts_guard and "updated_at" in update_cols:
                    # W18-D5：时间戳守卫 —— 本地行更新（或相等）时不覆盖。
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[pk_name],
                        set_=update_cols,
                        where=stmt.excluded.updated_at > model.updated_at,
                    )
                else:
                    stmt = stmt.on_conflict_do_update(index_elements=[pk_name], set_=update_cols)
            else:
                # 记录只带主键（无任何可更新列）：DO UPDATE 空 SET 是非法 SQL，
                # 语义等价于「冲突则忽略」。
                stmt = stmt.on_conflict_do_nothing(index_elements=[pk_name])
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=[pk_name])
        return stmt

    def _classify_import_records(
        self, model: Any, clean_records: List[Dict], pk_name: str
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """按主键占用情况把导入记录分成三类（W18-D1）。

        返回 (可直接插入, 同一业务记录, 需换新主键)：
          * 可直接插入：主键在本库空闲；
          * 同一业务记录：主键已占用且业务键相同（按 overwrite 决定更新或跳过）；
          * 需换新主键：主键已占用但业务键不同 —— 是本机另一条记录恰好撞了 id，
            绝不能覆写，改为去掉主键后插入。

        「无法判定业务身份」（无业务键模型/键为空）按同一业务记录保守处理，
        避免凭空插入重复行。
        """
        existing_ids: set = set()
        ids = [r[pk_name] for r in clean_records if r.get(pk_name) is not None]
        if ids:
            existing_ids = {
                row[0] for row in
                self.db.query(getattr(model, pk_name)).filter(getattr(model, pk_name).in_(ids)).all()
            }

        free_records = [r for r in clean_records if r.get(pk_name) is None or r[pk_name] not in existing_ids]
        collided = [r for r in clean_records if r.get(pk_name) is not None and r[pk_name] in existing_ids]

        same_records: List[Dict] = []
        relocated: List[Dict] = []
        for rec in collided:
            key = _business_key_of(model, rec)
            if key is None:
                # W27 fail-safe（W26-P0-1）：业务键**不可判定**时绝不能当成
                # "同一条记录"去覆写本机数据 —— 那是不可逆的数据丢失。
                # 改为 relocated：去掉主键后以新 id 插入，本机原记录保持不动。
                # 代价是可能产生重复行（可人工合并、可恢复），这是有意的取舍。
                relocated.append(rec)
                continue
            local = self.db.query(model).filter(getattr(model, pk_name) == rec[pk_name]).first()
            local_key = None
            if local is not None:
                local_key = _business_key_of(model, {k: getattr(local, k, None) for k in rec.keys()})
            if local_key is not None and local_key == key:
                same_records.append(rec)
            else:
                relocated.append(rec)
        return free_records, same_records, relocated

    def _bulk_upsert_records(
        self, model: Any, records: List[Dict], org_id: int, overwrite: bool,
        ts_guard: bool = False,
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

        # M29（R27 排查）：旧实现把所有记录按**键并集**补齐 None 后一次性 upsert，
        # overwrite 时 `stmt.excluded` 会把"某条记录未携带的字段"写成 NULL，
        # 覆盖掉目标库已有值。现按「记录实际携带的键集合」分组：组内键集合完全
        # 一致，每组独立编译 upsert（update set_ 仅含组内真实携带的列）——
        # 既保留批量写入，又不会用缺失键清空既有列；显式携带的 None 仍照写
        # （语义与"字段不存在"区分开）。多组并非常态（同一类型的导出记录字段集
        # 通常一致），分组开销可忽略。
        # W18-D1（跨机主键碰撞）：把记录分成两类——
        #   A. 主键在本库空闲  → 直接插入（安全，行为不变）
        #   B. 主键在本库已占用 → **不能**直接 ON CONFLICT DO UPDATE（会把本机真实
        #      记录整体覆写成源机数据，organization_id/created_at 一并改写且不可逆）。
        #      改为按业务键判定：
        #        · 业务键相同 → 确实是同一条业务记录 → 按 overwrite 决定更新或跳过；
        #        · 业务键不同 → 是**另一条记录恰好撞了 id** → 换新 id 插入，
        #          并登记 源id→新id 映射，供后续外键重写。
        free_records, same_records, relocated = self._classify_import_records(
            model, clean_records, pk_name
        )

        groups: Dict[frozenset, List[Dict]] = {}
        for r in free_records + same_records:
            groups.setdefault(frozenset(r.keys()), []).append(r)

        # W18-D4（回执失真）：imported 按**真实写入行数**（result.rowcount）累计。
        # 原实现 `imported += len(group_records)`：DO NOTHING（主键冲突且非覆盖）
        # 的行一个都没写也照计数 —— 前端弹"导入成功 3 条"，库里 0 条新数据。
        # rowcount 语义：INSERT 插入行计 1；DO UPDATE 命中更新计 1；DO NOTHING 计 0。
        skipped = 0
        imported = 0
        for group_records in groups.values():
            stmt = self._build_upsert_statement(model, group_records, pk_name, overwrite, ts_guard=ts_guard)

            try:
                # 本组使用独立 SAVEPOINT：失败只回滚本组，保留同一外层事务中已导入的
                # 前序数据类型与前序分组。历史实现在此处调用整事务 rollback() —— 会
                # 连同 confirm_import 的 begin_nested() 内已导入的前序类型一起丢弃，
                # 而 imported_counts 仍按"成功"计数并照常 commit（计数与数据不一致、
                # 静默丢数据）。
                with self.db.begin_nested():
                    result = self.db.execute(stmt)
                    written = getattr(result, "rowcount", 0) or 0
                    # rowcount 在 SQLite upsert 下 = 插入 + 实际更新的行数；
                    # DO NOTHING 的行不计入 → 与"真实落库"一致。
                    imported += max(0, written)
                    skipped += max(0, len(group_records) - max(0, written))
            except Exception as e:
                errors.append(DataPackageValidationError(
                    field=model.__tablename__, message=f"批量写入数据库失败: {e}", data_type=model.__tablename__
                ))

        # 业务键不同但主键相撞：去掉主键后插入，让数据库分配新 id。
        # 这样既不会覆写本机已有记录，也能把源机记录完整带进来。
        for rec in relocated:
            payload = {k: v for k, v in rec.items() if k != pk_name}
            try:
                with self.db.begin_nested():
                    self.db.execute(sqlite_insert(model).values([payload]))
                imported += 1
            except Exception as e:
                errors.append(DataPackageValidationError(
                    field=model.__tablename__,
                    message=f"主键 {rec.get(pk_name)} 与本地记录冲突且业务键不同，改用新 id 插入失败: {e}",
                    data_type=model.__tablename__,
                ))

        return imported, skipped, errors

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
                    read_zip_member(zf, "manifest.json")
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

            # 三步链路（upload-encrypted → decrypt-preview → confirm-import）要求
            # 解密预览通过后把包推进到 validated：confirm 只接受 validated 状态，
            # 历史实现不落状态使确认导入恒失败（前端表现为"导入"永远报错）。
            package.status = PackageStatus.validated.value
            self.db.commit()

            return DataPackageImportResult(
                package_id=package.id, package_code=package.package_code,
                status=PackageStatusEnum.VALIDATED, manifest=validation_result.manifest,
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
                    ensure_zip_within_limit(zf)  # R2 第三层：冲突导入路径同样先卡总量
                    manifest_dict = json.loads(read_zip_member(zf, "manifest.json").decode("utf-8"))
                    data_types = manifest_dict.get("data_types", [])

                    resolver = SmartConflictResolver(self.db)

                    # 收集所有支持类型的数据，一次性交给冲突解决器导入，
                    # 保证跨类型外键映射（projects.village_id -> villages 新 id）正确
                    data_dict: Dict[str, List[Dict]] = {}
                    for data_type in data_types:
                        if data_type not in DATA_TYPE_MODELS:
                            continue
                        data_file = f"data/{data_type}.json"
                        if data_file not in zf.namelist():
                            continue

                        records = json.loads(read_zip_member(zf, data_file).decode("utf-8"))
                        if records:
                            data_dict[data_type] = records

                    if data_dict:
                        resolver.import_with_id_mapping(data_dict, conflict_strategy)

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
        # 毫秒级时间戳 + 4位随机后缀：同一组织同一秒内多次导出/接收不再撞唯一约束
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")[:-3]
        suffix = uuid.uuid4().hex[:4]
        safe_org_code = org_code if org_code else "UNKNOWN"
        return f"{prefix}-{safe_org_code}-{timestamp}-{suffix}"

    def _calculate_checksum(self, file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return f"sha256:{sha256_hash.hexdigest()}"

    def _create_package_record(
        self, file_path: Optional[str], file_name: str, org_id: int, created_by: int,
        status: PackageStatus, error_message: str = None,
    ) -> DataPackage:
        """创建数据包记录（R9：file_path 允许为 None——校验拒绝的包无实体文件）。"""
        package_code = self._generate_package_code("UNKNOWN", "ERR")
        package = DataPackage(
            package_code=package_code, org_id=org_id, file_path=file_path,
            file_name=file_name,
            file_size=(
                os.path.getsize(file_path)
                if file_path and os.path.exists(file_path)
                else 0
            ),
            status=status.value, version=CURRENT_VERSION,
            error_message=error_message, created_by=created_by,
        )
        self.db.add(package)
        safe_commit(self.db)
        self.db.refresh(package)
        return package

    # ========================================================================
    # 保留策略（W18 P1-6）
    # ========================================================================
    def cleanup_exported_files(self, retention_days: int) -> int:
        """删除超过保留期的数据包导出文件（累计清理）。

        单机离线环境下用户会频繁导出数据包（每个数十~数百 MB），原实现
        **没有任何累计清理** —— 长期运行后磁盘被撑满 → 备份/导入失败，且首页
        不会提前预警。这里复用备份保留策略的口径（按天），由每日调度任务调用。

        Args:
            retention_days: 保留天数（<=0 表示不清理）

        Returns:
            删除的文件数
        """
        if retention_days <= 0:
            return 0
        cutoff = time.time() - retention_days * 86400
        deleted = 0
        try:
            names = os.listdir(self.upload_dir)
        except OSError as exc:
            logger.warning("数据包目录不可读，跳过保留期清理: %s (%s)", self.upload_dir, exc)
            return 0
        for name in names:
            path = os.path.join(self.upload_dir, name)
            try:
                if not os.path.isfile(path):
                    continue
                if os.path.getmtime(path) >= cutoff:
                    continue
                os.unlink(path)
                deleted += 1
            except OSError as exc:
                # 单个文件删不掉不应中断整轮清理（下个周期会再试）
                logger.warning("数据包文件清理失败（下轮重试）: %s (%s)", path, exc)
        if deleted:
            logger.info(
                "数据包保留期清理：删除 %d 个超过 %d 天的导出文件", deleted, retention_days
            )
        return deleted

    def get_upload_dir_size(self) -> int:
        """返回数据包导出目录占用字节数（供诊断包/运维摘要使用）。"""
        total = 0
        try:
            for name in os.listdir(self.upload_dir):
                path = os.path.join(self.upload_dir, name)
                try:
                    if os.path.isfile(path):
                        total += os.path.getsize(path)
                except OSError:
                    continue
        except OSError:
            return 0
        return total

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
