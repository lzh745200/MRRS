"""
Excel导入服务
提供帮扶村数据的Excel批量导入功能

Requirements: 1.4, 1.6, 1.7, 1.10 - 批量创建帮扶村记录，支持事务回滚，增量 / 全量模式，1000条限制
"""

import logging
from dataclasses import dataclass, field
from datetime import timezone, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.data_scope_query import scoped_filter  # B1 下沉：服务层统一入口
from app.models.fund import Fund
from app.models.household import Household
from app.models.import_history import ImportHistory, ImportMode, ImportStatus
from app.models.organization import Organization
from app.models.project import Project
from app.models.school import School
from app.models.supported_village import SupportedVillage
from app.services.data_validator_service import (
    DataValidatorService,
    ValidationErrorCode,
)
from app.services.entity_import_validator import EntityImportValidator
from app.services.office_reader import read_rows
from app.core.transaction import safe_commit

# R61：帮扶村可写字段（创建与按 ID 更新共用，避免字段清单漂移）
_VILLAGE_FIELDS = frozenset({
    "sequence_no",
    "department",
    "support_unit",
    "village_name",
    "region_scope",
    "is_three_regions",
    "is_border_area",
    "is_ethnic_area",
    "is_revolutionary_area",
    "is_key_county",
    "is_revitalization_tier",
    "is_provincial_demo",
    "is_hundred_village_demo",
    "is_tiered_development",
    "is_cross_province",
    "is_cross_city",
    "is_cross_unit_cooperation",
    "is_in_overall_plan",
    "honors",
})

logger = logging.getLogger(__name__)

# 尝试导入 pandas 加速模块（可选依赖）
try:
    from app.services.batch_import_optimizer import read_excel_raw as _pandas_read_raw
    _HAS_PANDAS_FAST_READ = True
except ImportError:  # pragma: no cover - 可选依赖未安装时的功能降级分支
    _HAS_PANDAS_FAST_READ = False

# 注意: ImportMode 枚举已在 app.models.import_history 中定义，此处统一使用该定义，避免重复


@dataclass
class ImportError:
    """导入错误"""

    row_number: int
    field_name: str
    error_code: str
    message: str
    value: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_number": self.row_number,
            "field_name": self.field_name,
            "error_code": self.error_code,
            "message": self.message,
            "value": str(self.value) if self.value is not None else None,
        }


@dataclass
class ImportResult:
    """导入结果"""

    success: bool
    total_rows: int = 0
    success_rows: int = 0
    failed_rows: int = 0
    skipped_rows: int = 0  # 增量模式下跳过的重复记录
    errors: List[ImportError] = field(default_factory=list)
    created_ids: List[int] = field(default_factory=list)
    import_history_id: Optional[int] = None
    # R61：解析成功但没有任何数据行（官方模板只含示例行/页脚）——API 层据此返回 400，
    # 与「文件损坏/格式不支持」区分开（后者仍按既有契约返回 200 + errors 明细）。
    no_data_rows: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "total_rows": self.total_rows,
            "success_rows": self.success_rows,
            "failed_rows": self.failed_rows,
            "skipped_rows": self.skipped_rows,
            "error_count": len(self.errors),
            "errors": [e.to_dict() for e in self.errors],
            "created_ids": self.created_ids,
            "import_history_id": self.import_history_id,
        }


class ExcelImporterService:
    """
    Excel导入服务

    提供帮扶村数据的Excel批量导入功能，支持：
    - Excel文件解析
    - 增量导入模式（跳过已存在记录）
    - 全量覆盖模式（删除现有记录后导入）
    - 事务回滚机制
    - 1000条记录限制
    """

    # 最大导入行数
    MAX_ROWS = 1000

    # 示例数据行的标识（绿色背景行）
    EXAMPLE_ROW_INDEX = 2  # Excel中的第2行是示例数据

    def __init__(self, db: Session, current_user=None):
        self.db = db
        self.current_user = current_user
        self.validator = DataValidatorService()

    def parse_excel(
        self, file_content: bytes, entity_type: str = "supported_village"
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        解析Excel文件内容

        优先使用 pandas 加速读取（比 openpyxl 快 3-5 倍），
        pandas 不可用时自动回退到 openpyxl 逐行模式。
        两条路径统一做：表头行自动探测（兼容官方模板第1-5行装饰标题区）、
        中文列名 → 英文字段映射、示例行跳过。

        Args:
            file_content: Excel文件的字节内容
            entity_type: 实体类型

        Returns:
            Tuple[List[Dict], List[str]]: (解析后的数据行列表, 表头列表)
        """
        # 根据实体类型选择验证器
        if entity_type == "supported_village":
            header_parser = self.validator.parse_excel_headers
            example_markers = ["某某部门", "示例部门"]
            known_fields = set(self.validator.COLUMN_MAPPING.values())
        else:
            entity_validator = EntityImportValidator(entity_type)
            header_parser = entity_validator.parse_excel_headers
            example_markers = ["某某村", "示例名称", "某某希望小学", "某某帮扶单位"]
            known_fields = set(entity_validator.get_column_mapping().values())

        def _parse_headers(candidate: List[str]) -> Dict[int, str]:
            """中文标签映射 + 英文字段名恒等映射（兼容机器生成的英文表头）"""
            mapping = header_parser(candidate)
            for idx, h in enumerate(candidate):
                if idx not in mapping and h in known_fields:
                    mapping[idx] = h
                # 表格填报回导：ID 是导出时追加的隐藏更新键，不在模板字段表里
                if idx not in mapping and str(h).strip().upper() == "ID":
                    mapping[idx] = "id"
            return mapping

        # 读取全部原始行（pandas 快速路径 / openpyxl 回退，均不带表头假设）
        raw_rows = self._read_raw_rows(file_content)

        # 表头行自动探测：前 10 行内第一个能映射 ≥2 列的行
        headers, header_mapping, header_idx = self._detect_header_row(raw_rows, _parse_headers)

        rows = []
        for row in raw_rows[header_idx + 1:]:
            if self._is_skippable_row(row, example_markers):
                continue
            row_data = self._row_to_dict(row, headers, header_mapping)
            if row_data:
                rows.append(row_data)

        return rows, headers

    @staticmethod
    def _read_raw_rows(file_content: bytes) -> List[list]:
        """读取全部原始行：pandas 快速路径优先，失败回退 openpyxl（均不带表头假设）"""
        if _HAS_PANDAS_FAST_READ:
            try:
                return _pandas_read_raw(file_content)
            except Exception as e:
                logger.warning("pandas 快速读取失败，回退到 openpyxl: %s", e)
        # 回退分支同样统一走 office_reader：按容器魔数选 openpyxl / xlrd，
        # 从而 .xls（OLE2）与 WPS .et（两种容器）在 pandas 不可用时也能导入。
        return read_rows(file_content)

    @staticmethod
    def _detect_header_row(raw_rows: List[list], parse_headers_fn) -> Tuple[List[str], Dict[int, str], int]:
        """表头行自动探测：前 10 行内第一个能映射 ≥2 列的行；未识别则假定第 1 行"""
        for idx, row in enumerate(raw_rows[:10]):
            candidate = [str(cell).strip() if cell is not None else "" for cell in row]
            mapping = parse_headers_fn(candidate)
            if len(mapping) >= 2:
                return candidate, mapping, idx
        # 未识别到表头：保持旧行为（假定第 1 行为表头）
        headers = [str(c).strip() if c is not None else "" for c in (raw_rows[0] if raw_rows else [])]
        return headers, parse_headers_fn(headers), 0

    @staticmethod
    def _is_skippable_row(row: list, example_markers: List[str]) -> bool:
        """示例行/填写说明/页脚/空行 跳过。

        R61 修复：此前只要行内任意单元格含「示例行」就整行跳过——用户在官方模板
        的示例行上直接改成真实数据（尾列「← 示例行（导入时自动跳过）」注释仍在）
        时，整行被静默丢弃，界面提示导入成功但 0 条入库。现在只有「示例标记值
        仍在」的行才跳过；真实数据行即使保留该注释也照常导入。
        """
        texts = [str(c).strip() for c in row if c is not None and str(c).strip()]
        if not texts:
            return True
        if texts[0] in example_markers:
            return True
        has_marker = any(text in example_markers for text in texts)
        if has_marker and any("示例行" in text for text in texts):
            return True
        if len(texts) == 1 and any(
            key in texts[0] for key in ("填写说明", "填报说明", "帮扶管理信息系统 v")
        ):
            return True
        return False

    @staticmethod
    def _row_to_dict(row: list, headers: List[str], header_mapping: Dict[int, str]) -> Dict[str, Any]:
        """按表头映射将行数据转换为英文字段名字典"""
        if not header_mapping:
            # 完全未识别的表头：回退为原始表头键（旧 pandas 快读路径行为，
            # 交由下游校验器报"必填字段缺失"而不是静默丢弃）
            return {
                headers[col_idx]: cell_value
                for col_idx, cell_value in enumerate(row)
                if col_idx < len(headers) and headers[col_idx]
            }
        return {
            header_mapping[col_idx]: cell_value
            for col_idx, cell_value in enumerate(row)
            if col_idx in header_mapping
        }

    def import_data(  # noqa: C901 - 多实体/多模式导入分支，拆分风险高
        self,
        file_content: bytes,
        file_name: str,
        file_size: int,
        user_id: int,
        mode: ImportMode = ImportMode.INCREMENTAL,
        entity_type: str = "supported_village",
    ) -> ImportResult:
        """
        导入Excel数据

        Args:
            file_content: Excel文件的字节内容
            file_name: 文件名
            file_size: 文件大小
            user_id: 操作用户ID
            mode: 导入模式（增量 / 全量）
            entity_type: 实体类型

        Returns:
            ImportResult: 导入结果
        """
        # 创建导入历史记录
        import_history = ImportHistory(
            user_id=user_id,
            file_name=file_name,
            file_size=file_size,
            import_mode=mode.value,
            entity_type=entity_type,
            status=ImportStatus.PROCESSING.value,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(import_history)
        self.db.flush()  # 获取ID但不提交

        result = ImportResult(success=False, import_history_id=import_history.id)

        try:
            # 解析Excel
            rows, headers = self.parse_excel(file_content, entity_type=entity_type)
            result.total_rows = len(rows)

            # 检查行数限制
            if len(rows) > self.MAX_ROWS:
                result.errors.append(
                    ImportError(
                        row_number=0,
                        field_name="",
                        error_code=ValidationErrorCode.ROW_LIMIT_EXCEEDED.value,
                        message=f"数据行数超过限制，单次最多导入 {self.MAX_ROWS} 条记录，当前 {len(rows)} 条",
                    )
                )
                self._update_import_history(import_history, result, ImportStatus.FAILED)
                safe_commit(self.db)
                return result

            # full 模式会先软删；0 行必须在删除之前返回，否则模板空表会清空台账
            if not rows:
                result.no_data_rows = True
                result.errors.append(
                    ImportError(
                        row_number=0,
                        field_name="",
                        error_code=ValidationErrorCode.MISSING_REQUIRED_FIELD.value,
                        message="未解析到任何数据行：示例行不会导入，请在示例行下方新增数据行",
                    )
                )
                self._update_import_history(import_history, result, ImportStatus.FAILED)
                safe_commit(self.db)
                return result

            # 根据实体类型选择验证器和导入逻辑
            if entity_type == "supported_village":
                validation_result = self.validator.validate_batch(rows)
                duplicate_errors = self.validator.check_duplicates(rows)
                rows = [self.validator.convert_row_types(r) for r in rows]
            else:
                entity_validator = EntityImportValidator(entity_type)
                validation_result = entity_validator.validate_batch(rows)
                duplicate_errors = entity_validator.check_duplicates(rows)
                rows = [entity_validator.convert_row_types(r) for r in rows]

            # 验证数据
            if not validation_result.is_valid:
                for error in validation_result.errors:
                    result.errors.append(
                        ImportError(
                            row_number=error.row_number,
                            field_name=error.field_name,
                            error_code=error.error_code.value,
                            message=error.message,
                            value=error.value,
                        )
                    )
                result.failed_rows = len(rows)
                self._update_import_history(import_history, result, ImportStatus.FAILED)
                safe_commit(self.db)
                return result

            # 检查重复数据
            if duplicate_errors:
                for error in duplicate_errors:
                    result.errors.append(
                        ImportError(
                            row_number=error.row_number,
                            field_name=error.field_name,
                            error_code=error.error_code.value,
                            message=error.message,
                            value=error.value,
                        )
                    )
                result.failed_rows = len(rows)
                self._update_import_history(import_history, result, ImportStatus.FAILED)
                safe_commit(self.db)
                return result

            # 执行导入
            if entity_type == "supported_village":
                if mode == ImportMode.FULL:
                    result = self._import_full_mode(rows, result, import_history)
                else:
                    result = self._import_incremental_mode(rows, result, import_history)
            elif entity_type == "project":
                result = self._import_projects(rows, result, import_history, mode)
            elif entity_type == "fund":
                result = self._import_funds(rows, result, import_history, mode)
            elif entity_type == "school":
                result = self._import_schools(rows, result, import_history, mode)
            elif entity_type == "household":
                result = self._import_households(rows, result, import_history, mode)

            # full 模式是“先软删再写”：任何一行失败都必须整体回滚，
            # 否则旧数据已消失、新数据只写一半（业务数据不可逆丢失）。
            if mode == ImportMode.FULL and result.failed_rows > 0:
                self.db.rollback()
                result.success = False
                result.success_rows = 0
                result.created_ids = []
                failed_history = ImportHistory(
                    user_id=user_id,
                    file_name=file_name,
                    file_size=file_size,
                    import_mode=mode.value,
                    entity_type=entity_type,
                    status=ImportStatus.FAILED.value,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    total_rows=result.total_rows,
                    success_rows=0,
                    failed_rows=result.failed_rows,
                    error_details=[e.to_dict() for e in result.errors],
                )
                self.db.add(failed_history)
                safe_commit(self.db)
                result.import_history_id = failed_history.id
                return result

            # 更新导入历史
            status = ImportStatus.COMPLETED if result.success else ImportStatus.FAILED
            self._update_import_history(import_history, result, status)

            safe_commit(self.db)
            return result

        except SQLAlchemyError as e:
            # 数据库错误，回滚事务
            self.db.rollback()
            result.errors.append(
                ImportError(
                    row_number=0,
                    field_name="",
                    error_code=ValidationErrorCode.DATABASE_ERROR.value,
                    message=f"数据库错误: {str(e)}",
                )
            )
            result.failed_rows = result.total_rows

            # 重新创建导入历史记录（因为回滚了）
            import_history = ImportHistory(
                user_id=user_id,
                file_name=file_name,
                file_size=file_size,
                import_mode=mode.value,
                entity_type=entity_type,
                status=ImportStatus.FAILED.value,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                total_rows=result.total_rows,
                success_rows=0,
                failed_rows=result.total_rows,
                error_details=[e.to_dict() for e in result.errors],
            )
            self.db.add(import_history)
            safe_commit(self.db)
            result.import_history_id = import_history.id

            return result

        except Exception as e:
            logger.warning('_parse_headers 兜底失败（已降级）: %s', e, exc_info=True)
            # 其他错误
            self.db.rollback()
            result.errors.append(
                ImportError(
                    row_number=0,
                    field_name="",
                    error_code="IMPORT_999",
                    message=f"导入失败: {str(e)}",
                )
            )
            result.failed_rows = result.total_rows
            # 回滚会删掉此前 flush 的 import_history；重建失败历史，
            # 避免“导入失败但历史查不到 + 返回悬空 id”。
            try:
                failed_history = ImportHistory(
                    user_id=user_id,
                    file_name=file_name,
                    file_size=file_size,
                    import_mode=mode.value,
                    entity_type=entity_type,
                    status=ImportStatus.FAILED.value,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    total_rows=result.total_rows,
                    success_rows=0,
                    failed_rows=result.total_rows,
                    error_details=[e.to_dict() for e in result.errors],
                )
                self.db.add(failed_history)
                safe_commit(self.db)
                result.import_history_id = failed_history.id
            except Exception:  # nosec:swallow - 失败历史写入异常不阻断原始导入结果返回
                result.import_history_id = None
            return result

    def _import_incremental_mode(
        self,
        rows: List[Dict[str, Any]],
        result: ImportResult,
        import_history: ImportHistory,
    ) -> ImportResult:
        """
        增量导入模式
        跳过已存在的记录（根据village_name判断）
        """
        # 批量查询：仅检查本次导入涉及的名称，避免全表扫描
        from sqlalchemy import func as sql_func
        imported_names = list({
            row.get("village_name", "").lower()
            for row in rows
            if row.get("village_name", "")
        })
        existing_names = set()
        if imported_names:
            existing = (
                self.db.query(sql_func.lower(SupportedVillage.village_name))
                .filter(sql_func.lower(SupportedVillage.village_name).in_(imported_names))
                .all()
            )
            existing_names = {r[0] for r in existing if r[0]}

        for row_idx, row in enumerate(rows, 1):
            # 转换数据类型
            converted_row = self.validator.convert_row_types(row)

            row_id = self._coerce_row_id(converted_row.get("id"))
            if row_id:
                existing_village = self._scoped_get(SupportedVillage, row_id)
                if existing_village is None:
                    result.errors.append(ImportError(
                        row_number=row_idx, field_name="id",
                        error_code=ValidationErrorCode.INVALID_DATA_FORMAT.value,
                        message=f"ID={row_id} 不存在或无权限", value=row_id,
                    ))
                    result.failed_rows += 1
                    continue
                with self.db.begin_nested():
                    self._apply_update(existing_village, converted_row)
                result.created_ids.append(existing_village.id)
                result.success_rows += 1
                continue

            village_name = converted_row.get("village_name", "")
            if village_name and village_name.lower() in existing_names:
                # 跳过已存在的记录
                result.skipped_rows += 1
                continue

            # 创建新记录
            try:
                with self.db.begin_nested():
                    village = self._create_village(converted_row)
                result.created_ids.append(village.id)
                result.success_rows += 1

                # 添加到已存在集合，避免同批次重复
                if village_name:
                    existing_names.add(village_name.lower())

            except Exception as e:
                logger.warning('_parse_headers 兜底失败（已降级）: %s', e, exc_info=True)
                result.errors.append(
                    ImportError(
                        row_number=row_idx,
                        field_name="",
                        error_code=ValidationErrorCode.DATABASE_ERROR.value,
                        message=f"创建记录失败: {str(e)}",
                    )
                )
                result.failed_rows += 1

        result.success = result.failed_rows == 0
        return result

    @staticmethod
    def _coerce_row_id(value: Any) -> Optional[int]:
        if value is None or str(value).strip() == "":
            return None
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return None

    def _scoped_get(self, model: Any, row_id: int):
        query = self.db.query(model).filter(model.id == row_id)
        if self.current_user is not None:
            query = scoped_filter(query, model, self.current_user)
        return query.first()

    def _apply_update(self, instance: Any, data: Dict[str, Any]) -> None:
        """按 ORM 列白名单更新（ID 回导），跳过归属/时间/主键列。"""
        skip = {"id", "created_at", "updated_at", "organization_id", "created_by"}
        for column in instance.__table__.columns.keys():
            if column in skip or column not in data:
                continue
            value = data[column]
            if value is not None:
                setattr(instance, column, value)
        self.db.flush()

    def _assert_org_reachable(self, target_org_id: Any) -> None:
        """校验调用者可将数据写入 *target_org_id*（W25 跨组织写入守卫）。

        Excel 行的 ``organization_code`` 决定落库组织；校验失败抛
        ``PermissionError``，由调用方逐行捕获并计入 ``result.errors``
        （该行被拒绝，其余行继续，不整体失败）。

        放行条件（fail-closed 之外的白名单）：
          * 无 ``current_user``（CLI/迁移/内部受信上下文）；
          * 全局管理员（super_admin / is_superuser）；
          * 目标组织 == 调用者本组织，或位于其组织子树内。
        """
        if self.current_user is None or target_org_id is None:
            return
        from app.core.permission_utils import is_superuser

        if is_superuser(self.current_user):
            return
        user_org = getattr(self.current_user, "organization_id", None)
        if user_org is None:
            raise PermissionError("调用者无组织归属，不得导入到指定组织")
        try:
            target = int(target_org_id)
            own = int(user_org)
        except (TypeError, ValueError):
            raise PermissionError(f"非法的目标组织标识: {target_org_id!r}")
        if target == own:
            return
        from app.core.data_permission import _get_org_subtree

        subtree_ids, _names = _get_org_subtree(self.db, own)
        if target in [int(i) for i in (subtree_ids or [])]:
            return
        raise PermissionError(f"无权向组织 {target} 导入数据（超出本组织及子树范围）")

    def _soft_delete_scoped(self, model: Any) -> int:
        """全量覆盖导入时的「清空」改为**软删除**（W18-D2）。

        原实现用 `query.delete()` 物理删除，且不过滤 `is_active`：
          1. 连回收站里的软删行一起物理抹掉（彻底不可恢复）；
          2. `projects.village_id` / `funds.project_id` / `funds.village_id` 均为
             `ON DELETE CASCADE` —— 只导入「帮扶村」一张表，也会把项目与经费
             级联物理删除（实证 1村/1项目/1经费 → 项目0/经费0）。

        改为软删除：符合本项目的软删模式（`is_active=False`），既满足「全量覆盖」
        的语义（旧数据不再出现在列表/统计中），又不触发级联物理删除，且可随时
        通过回收站恢复。返回影响行数。
        """
        if not hasattr(model, "is_active"):  # pragma: no cover - 本服务只处理带软删列的模型
            query = scoped_filter(self.db.query(model), model, self.current_user) \
                if self.current_user else self.db.query(model)
            return query.delete(synchronize_session=False)

        query = scoped_filter(self.db.query(model), model, self.current_user) \
            if self.current_user else self.db.query(model)
        # 只处理当前可见（未软删）的行，避免重复计数与无意义更新
        query = query.filter(model.is_active.is_(True))
        return query.update({model.is_active: False}, synchronize_session=False)

    def _import_full_mode(
        self,
        rows: List[Dict[str, Any]],
        result: ImportResult,
        import_history: ImportHistory,
    ) -> ImportResult:
        """
        全量覆盖模式
        删除现有所有记录后导入新数据
        """
        # W18-D2：改为软删除（原先 query.delete() 物理删除，且级联抹掉项目/经费）
        self._soft_delete_scoped(SupportedVillage)

        for row_idx, row in enumerate(rows, 1):
            # 转换数据类型
            converted_row = self.validator.convert_row_types(row)

            try:
                village = self._create_village(converted_row)
                result.created_ids.append(village.id)
                result.success_rows += 1

            except Exception as e:
                logger.warning('_parse_headers 兜底失败（已降级）: %s', e, exc_info=True)
                result.errors.append(
                    ImportError(
                        row_number=row_idx,
                        field_name="",
                        error_code=ValidationErrorCode.DATABASE_ERROR.value,
                        message=f"创建记录失败: {str(e)}",
                    )
                )
                result.failed_rows += 1

        result.success = result.failed_rows == 0
        return result

    def _create_village(self, data: Dict[str, Any]) -> SupportedVillage:
        """
        创建帮扶村记录

        Args:
            data: 转换后的数据字典

        Returns:
            SupportedVillage: 创建的记录
        """
        # 过滤掉None值和非模型字段
        filtered_data = {k: v for k, v in data.items() if k in _VILLAGE_FIELDS and v is not None}

        # 设置布尔字段的默认值
        bool_fields = [
            "is_three_regions",
            "is_border_area",
            "is_ethnic_area",
            "is_revolutionary_area",
            "is_key_county",
            "is_provincial_demo",
            "is_hundred_village_demo",
            "is_tiered_development",
            "is_cross_province",
            "is_cross_city",
            "is_cross_unit_cooperation",
            "is_in_overall_plan",
        ]
        for bool_field in bool_fields:
            if bool_field not in filtered_data:
                filtered_data[bool_field] = False

        village = SupportedVillage(**filtered_data)
        # 归属字段：与手工创建一致，保证导入者在数据权限范围内可见/可编辑
        if self.current_user is not None:
            village.organization_id = getattr(self.current_user, "organization_id", None)
            village.created_by = getattr(self.current_user, "id", None)
        self.db.add(village)
        self.db.flush()  # 获取ID
        return village

    def _update_import_history(self, import_history: ImportHistory, result: ImportResult, status: ImportStatus):
        """更新导入历史记录"""
        import_history.status = status.value
        import_history.total_rows = result.total_rows
        import_history.success_rows = result.success_rows
        import_history.failed_rows = result.failed_rows
        import_history.error_details = [e.to_dict() for e in result.errors] if result.errors else None
        import_history.completed_at = datetime.now(timezone.utc)

    # ============== 项目导入 ==============

    def _import_projects(
        self,
        rows: List[Dict[str, Any]],
        result: ImportResult,
        import_history: ImportHistory,
        mode: ImportMode,
    ) -> ImportResult:
        validator = EntityImportValidator("project")
        existing_names = set()
        if mode == ImportMode.INCREMENTAL:
            existing_names = set(name[0].strip().lower() for name in self.db.query(Project.name).all() if name[0])
        else:
            # W18-D2：软删除（避免物理删除后无法恢复）
            self._soft_delete_scoped(Project)

        # 预加载组织编码映射
        org_map = {o.code: o.id for o in self.db.query(Organization).all() if o.code}

        for row_idx, row in enumerate(rows, 1):
            converted = validator.convert_row_types(row)
            row_id = self._coerce_row_id(converted.get("id"))
            if row_id:
                existing_project = self._scoped_get(Project, row_id)
                if existing_project is None:
                    result.errors.append(ImportError(
                        row_number=row_idx, field_name="id",
                        error_code=ValidationErrorCode.INVALID_DATA_FORMAT.value,
                        message=f"ID={row_id} 不存在或无权限", value=row_id,
                    ))
                    result.failed_rows += 1
                    continue
                with self.db.begin_nested():
                    self._apply_update(existing_project, converted)
                result.created_ids.append(existing_project.id)
                result.success_rows += 1
                continue
            name = converted.get("name", "")
            if mode == ImportMode.INCREMENTAL and name and name.lower() in existing_names:
                result.skipped_rows += 1
                continue

            try:
                project_data = {
                    "name": converted.get("name"),
                    "code": converted.get("code"),
                    "type": converted.get("type") or "other",
                    "status": converted.get("status") or "draft",
                    "description": converted.get("description"),
                    "budget": converted.get("budget") or 0,
                    "start_date": converted.get("start_date"),
                    "end_date": converted.get("end_date"),
                    "leader": converted.get("leader"),
                    "contact_phone": converted.get("contact_phone"),
                    "responsible_unit": converted.get("responsible_unit"),
                }
                org_code = converted.get("organization_code")
                if org_code and org_code in org_map:
                    target_org_id = org_map[org_code]
                    # W25：Excel 内的 organization_code 决定落库组织，必须校验调用者
                    # 可达性 —— 否则导入可把数据写进任意组织（跨组织写入）。
                    self._assert_org_reachable(target_org_id)
                    project_data["organization_id"] = target_org_id
                elif self.current_user is not None:
                    # 模板未填组织编码时回落到调用者本组织，避免导入成“幽灵台账”
                    current_org = getattr(self.current_user, "organization_id", None)
                    if current_org:
                        project_data["organization_id"] = current_org
                if self.current_user is not None:
                    project_data["created_by"] = getattr(self.current_user, "id", None)

                with self.db.begin_nested():
                    project = Project(**project_data)
                    self.db.add(project)
                    self.db.flush()
                result.created_ids.append(project.id)
                result.success_rows += 1
                if name:
                    existing_names.add(name.lower())
            except Exception as e:
                logger.warning('_parse_headers 兜底失败（已降级）: %s', e, exc_info=True)
                result.errors.append(
                    ImportError(
                        row_number=row_idx,
                        field_name="",
                        error_code=ValidationErrorCode.DATABASE_ERROR.value,
                        message=f"创建项目失败: {str(e)}",
                    )
                )
                result.failed_rows += 1

        result.success = result.failed_rows == 0
        return result

    # ============== 一户一档导入 ==============

    def _import_households(
        self,
        rows: List[Dict[str, Any]],
        result: ImportResult,
        import_history: ImportHistory,
        mode: ImportMode,
    ) -> ImportResult:
        """导入一户一档主档。

        帮扶村按“名称 + 县/市 + 乡镇”解析；同名多村时该行报错，要求补充
        县/乡镇，不做猜测。户编号在村内唯一；留空时按“村 + 户主姓名”
        做增量去重（避免重复导入同一户）。
        """
        validator = EntityImportValidator("household")
        if mode == ImportMode.FULL:
            self._soft_delete_scoped(Household)

        # 预加载可见帮扶村：只取有效村，按名称/县/乡镇建索引。
        villages = self.db.query(SupportedVillage).filter(
            SupportedVillage.is_active.is_(True)
        ).all()
        by_name: Dict[tuple, List[SupportedVillage]] = {}
        for village in villages:
            key = (
                (village.village_name or "").strip(),
                (getattr(village, "county", None) or "").strip(),
                (getattr(village, "township", None) or "").strip(),
            )
            by_name.setdefault(key, []).append(village)

        existing: set = set()
        if mode == ImportMode.INCREMENTAL:
            for h in self.db.query(Household).filter(Household.is_active.is_(True)).all():
                if h.household_code:
                    existing.add((h.supported_village_id, h.household_code.strip().lower()))
                else:
                    existing.add((h.supported_village_id, h.household_name.strip().lower()))

        for row_idx, row in enumerate(rows, 1):
            converted = validator.convert_row_types(row)
            village_name = str(converted.get("village_name") or "").strip()
            county = str(converted.get("county") or "").strip()
            township = str(converted.get("township") or "").strip()
            household_name = str(converted.get("household_name") or "").strip()
            household_code = str(converted.get("household_code") or "").strip() or None

            row_id = self._coerce_row_id(converted.get("id"))
            if row_id:
                existing_household = self._scoped_get(Household, row_id)
                if existing_household is None:
                    result.errors.append(ImportError(
                        row_number=row_idx, field_name="id",
                        error_code=ValidationErrorCode.INVALID_DATA_FORMAT.value,
                        message=f"ID={row_id} 不存在或无权限", value=row_id,
                    ))
                    result.failed_rows += 1
                    continue
                with self.db.begin_nested():
                    self._apply_update(existing_household, converted)
                result.created_ids.append(existing_household.id)
                result.success_rows += 1
                continue

            village = self._resolve_household_village(
                villages, by_name, village_name, county, township, row_idx, result
            )
            if village is None:
                continue

            dup_key = (
                (village.id, household_code.lower())
                if household_code
                else (village.id, household_name.lower())
            )
            if mode == ImportMode.INCREMENTAL and dup_key in existing:
                result.skipped_rows += 1
                continue

            try:
                with self.db.begin_nested():
                    household = self._build_household(converted, village, household_name, household_code)
                    self.db.add(household)
                    self.db.flush()
                result.created_ids.append(household.id)
                result.success_rows += 1
                existing.add(dup_key)
            except Exception as exc:
                logger.warning("一户一档导入第 %d 行失败: %s", row_idx, exc, exc_info=True)
                result.errors.append(ImportError(
                    row_number=row_idx, field_name="",
                    error_code=ValidationErrorCode.DATABASE_ERROR.value,
                    message=f"创建一户一档失败: {exc}",
                ))
                result.failed_rows += 1

        result.success = result.failed_rows == 0
        return result

    def _resolve_household_village(
        self,
        villages: List[SupportedVillage],
        by_name: Dict[tuple, List[SupportedVillage]],
        village_name: str,
        county: str,
        township: str,
        row_idx: int,
        result: ImportResult,
    ) -> Optional[SupportedVillage]:
        """按 名称+县+乡镇 解析帮扶村；同名多村时要求补充县/乡镇。"""
        candidates = by_name.get((village_name, county, township), [])
        if not candidates:
            candidates = [
                v for v in villages
                if (v.village_name or "").strip() == village_name
            ]
        reachable = []
        for v in candidates:
            try:
                self._assert_org_reachable(v.organization_id)
            except PermissionError:
                continue
            reachable.append(v)
        if len(reachable) != 1:
            msg = "未找到帮扶村" if not reachable else "帮扶村不唯一，请补充县/市、乡镇"
            result.errors.append(ImportError(
                row_number=row_idx, field_name="village_name",
                error_code=ValidationErrorCode.INVALID_DATA_FORMAT.value,
                message=msg, value=village_name,
            ))
            result.failed_rows += 1
            return None
        return reachable[0]

    def _build_household(
        self, converted: Dict[str, Any], village: SupportedVillage,
        household_name: str, household_code: Optional[str],
    ) -> Household:
        housing_safe = converted.get("housing_safe")
        return Household(
            supported_village_id=village.id,
            household_code=household_code,
            household_name=household_name,
            address=converted.get("address"),
            household_type=converted.get("household_type") or "general",
            risk_type=converted.get("risk_type") or "none",
            risk_level=converted.get("risk_level") or "low",
            helper_name=converted.get("helper_name"),
            helper_phone=converted.get("helper_phone"),
            annual_income=converted.get("annual_income"),
            migrant_workers=converted.get("migrant_workers") or 0,
            has_serious_illness=bool(converted.get("has_serious_illness")),
            housing_safe=bool(housing_safe) if housing_safe is not None else True,
            last_visit_date=converted.get("last_visit_date"),
            monitoring_note=converted.get("monitoring_note"),
            organization_id=village.organization_id
            or getattr(self.current_user, "organization_id", None),
            created_by=getattr(self.current_user, "id", None),
        )

    # ============== 资金导入 ==============

    def _import_funds(
        self,
        rows: List[Dict[str, Any]],
        result: ImportResult,
        import_history: ImportHistory,
        mode: ImportMode,
    ) -> ImportResult:
        validator = EntityImportValidator("fund")
        existing_names = set()
        if mode == ImportMode.INCREMENTAL:
            existing_names = set(
                name[0].strip().lower()
                for name in self.db.query(Fund.name).all() if name[0]
            )
        else:
            # W18-D2：软删除（避免物理删除后无法恢复）
            self._soft_delete_scoped(Fund)

        # 预加载项目编号映射
        project_map = {p.code: p.id for p in self.db.query(Project).all() if p.code}

        for row_idx, row in enumerate(rows, 1):
            converted = validator.convert_row_types(row)
            row_id = self._coerce_row_id(converted.get("id"))
            if row_id:
                existing_fund = self._scoped_get(Fund, row_id)
                if existing_fund is None:
                    result.errors.append(ImportError(
                        row_number=row_idx, field_name="id",
                        error_code=ValidationErrorCode.INVALID_DATA_FORMAT.value,
                        message=f"ID={row_id} 不存在或无权限", value=row_id,
                    ))
                    result.failed_rows += 1
                    continue
                with self.db.begin_nested():
                    self._apply_update(existing_fund, converted)
                result.created_ids.append(existing_fund.id)
                result.success_rows += 1
                continue
            name = converted.get("name", "")
            if mode == ImportMode.INCREMENTAL and name and name.lower() in existing_names:
                result.skipped_rows += 1
                continue

            try:
                fund_data = {
                    "name": converted.get("name"),
                    "code": converted.get("code"),
                    "amount": converted.get("amount") or 0,
                    "fund_type": converted.get("fund_type") or "other",
                    "fund_source": converted.get("fund_source") or "other",
                    "purpose": converted.get("purpose"),
                    "status": converted.get("status") or "pending",
                    "operator": converted.get("operator"),
                    "receiver": converted.get("receiver"),
                    "date": converted.get("date"),
                    "remarks": converted.get("remarks"),
                }
                # 归属字段：与手工创建/帮扶村导入一致，否则非超管列表直接看不到
                if self.current_user is not None:
                    current_org = getattr(self.current_user, "organization_id", None)
                    if current_org:
                        fund_data["organization_id"] = current_org
                    fund_data["created_by"] = getattr(self.current_user, "id", None)
                project_code = converted.get("project_code")
                if project_code and project_code in project_map:
                    fund_data["project_id"] = project_map[project_code]

                with self.db.begin_nested():
                    fund = Fund(**fund_data)
                    self.db.add(fund)
                    self.db.flush()
                result.created_ids.append(fund.id)
                result.success_rows += 1
                if name:
                    existing_names.add(name.lower())
            except Exception as e:
                logger.warning('_parse_headers 兜底失败（已降级）: %s', e, exc_info=True)
                result.errors.append(
                    ImportError(
                        row_number=row_idx,
                        field_name="",
                        error_code=ValidationErrorCode.DATABASE_ERROR.value,
                        message=f"创建资金记录失败: {str(e)}",
                    )
                )
                result.failed_rows += 1

        result.success = result.failed_rows == 0
        return result

    # ============== 学校导入 ==============

    def _import_schools(
        self,
        rows: List[Dict[str, Any]],
        result: ImportResult,
        import_history: ImportHistory,
        mode: ImportMode,
    ) -> ImportResult:
        validator = EntityImportValidator("school")
        existing_names = set()
        if mode == ImportMode.INCREMENTAL:
            existing_names = set(
                name[0].strip().lower()
                for name in self.db.query(School.name).all() if name[0]
            )
        else:
            # W18-D2：软删除（避免物理删除后无法恢复）
            self._soft_delete_scoped(School)

        for row_idx, row in enumerate(rows, 1):
            converted = validator.convert_row_types(row)
            row_id = self._coerce_row_id(converted.get("id"))
            if row_id:
                existing_school = self._scoped_get(School, row_id)
                if existing_school is None:
                    result.errors.append(ImportError(
                        row_number=row_idx, field_name="id",
                        error_code=ValidationErrorCode.INVALID_DATA_FORMAT.value,
                        message=f"ID={row_id} 不存在或无权限", value=row_id,
                    ))
                    result.failed_rows += 1
                    continue
                with self.db.begin_nested():
                    self._apply_update(existing_school, converted)
                result.created_ids.append(existing_school.id)
                result.success_rows += 1
                continue
            name = converted.get("name", "")
            if mode == ImportMode.INCREMENTAL and name and name.lower() in existing_names:
                result.skipped_rows += 1
                continue

            try:
                school_data = {
                    "name": converted.get("name"),
                    "code": converted.get("code"),
                    "type": converted.get("type") or "other",
                    "province": converted.get("province"),
                    "city": converted.get("city"),
                    "district": converted.get("district"),
                    "address": converted.get("address"),
                    "principal": converted.get("principal"),
                    "contact_phone": converted.get("contact_phone"),
                    "student_count": converted.get("student_count") or 0,
                    "teacher_count": converted.get("teacher_count") or 0,
                    "support_unit": converted.get("support_unit"),
                    "support_status": converted.get("support_status") or "inactive",
                    "description": converted.get("description"),
                    "is_active": True,
                }
                # 归属字段：与手工创建一致（学校列表按组织/创建者收敛）
                if self.current_user is not None:
                    current_org = getattr(self.current_user, "organization_id", None)
                    if current_org:
                        school_data["organization_id"] = current_org
                    school_data["created_by"] = getattr(self.current_user, "id", None)
                with self.db.begin_nested():
                    school = School(**school_data)
                    self.db.add(school)
                    self.db.flush()
                result.created_ids.append(school.id)
                result.success_rows += 1
                if name:
                    existing_names.add(name.lower())
            except Exception as e:
                logger.warning('_parse_headers 兜底失败（已降级）: %s', e, exc_info=True)
                result.errors.append(
                    ImportError(
                        row_number=row_idx,
                        field_name="",
                        error_code=ValidationErrorCode.DATABASE_ERROR.value,
                        message=f"创建学校记录失败: {str(e)}",
                    )
                )
                result.failed_rows += 1

        result.success = result.failed_rows == 0
        return result

    async def import_data_async(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        user_id: int,
        mode: ImportMode = ImportMode.INCREMENTAL,
        entity_type: str = "supported_village",
    ) -> ImportResult:
        """
        异步导入Excel数据（可用于API端点、CLI或后台任务）

        Args:
            file_bytes: 文件内容字节
            filename: 原始文件名
            content_type: MIME 类型
            user_id: 操作用户ID
            mode: 导入模式
            entity_type: 实体类型

        Returns:
            ImportResult: 导入结果
        """
        # 验证文件格式
        is_valid, error_msg = self.validator.validate_file_format(filename or "")
        if not is_valid:
            return ImportResult(
                success=False,
                errors=[
                    ImportError(
                        row_number=0,
                        field_name="file",
                        error_code=ValidationErrorCode.INVALID_FILE_FORMAT.value,
                        message=error_msg or "文件格式错误",
                    )
                ],
            )

        # 文件内容已在调用方读取
        file_size = len(file_bytes)

        # 验证文件大小
        is_valid, error_msg = self.validator.validate_file_size(file_size)
        if not is_valid:
            return ImportResult(
                success=False,
                errors=[
                    ImportError(
                        row_number=0,
                        field_name="file",
                        error_code=ValidationErrorCode.FILE_TOO_LARGE.value,
                        message=error_msg or "文件过大",
                    )
                ],
            )

        # 执行导入
        return self.import_data(
            file_content=file_bytes,
            file_name=filename or "unknown.xlsx",
            file_size=file_size,
            user_id=user_id,
            mode=mode,
            entity_type=entity_type,
        )

    def get_import_history(
        self, user_id: Optional[int] = None, page: int = 1, page_size: int = 20
    ) -> Tuple[List[ImportHistory], int]:
        """
        获取导入历史记录

        Args:
            user_id: 用户ID（可选，不传则获取所有）
            page: 页码
            page_size: 每页数量

        Returns:
            Tuple[List[ImportHistory], int]: (历史记录列表, 总数)
        """
        query = self.db.query(ImportHistory)

        if user_id:
            query = query.filter(ImportHistory.user_id == user_id)

        total = query.count()

        histories = (
            query.order_by(ImportHistory.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        )

        return histories, total

    def get_import_history_by_id(self, history_id: int) -> Optional[ImportHistory]:
        """
        根据ID获取导入历史记录

        Args:
            history_id: 历史记录ID

        Returns:
            ImportHistory: 历史记录或None
        """
        return self.db.query(ImportHistory).filter(ImportHistory.id == history_id).first()
