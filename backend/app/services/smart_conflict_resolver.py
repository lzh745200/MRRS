"""
Smart Conflict Resolver
智能冲突解决服务 - 处理数据导入时的ID和业务键冲突
"""

import time
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.project import Fund, Project
from app.models.school import School
from app.models.supported_village import SupportedVillage


class ConflictStrategy:
    """冲突解决策略"""

    SKIP = "SKIP"  # 跳过导入数据，保留本地数据
    OVERWRITE = "OVERWRITE"  # 用导入数据覆盖本地数据
    KEEP_BOTH = "KEEP_BOTH"  # 保留两者，导入数据创建新记录
    MERGE = "MERGE"  # 智能合并（优先使用非空值）
    AUTO = "AUTO"  # 自动选择最佳策略（根据冲突类型智能判断）


class DataConflict:
    """数据冲突信息"""

    def __init__(
        self,
        data_type: str,
        business_key: Dict[str, Any],
        local_record: Any,
        import_record: Dict[str, Any],
        differences: List[str],
    ):
        self.data_type = data_type
        self.business_key = business_key
        self.local_record = local_record
        self.import_record = import_record
        self.differences = differences


class ConflictDetectionResult:
    """冲突检测结果"""

    def __init__(
        self,
        new_records: List[Dict[str, Any]],
        conflict_records: List[DataConflict],
        no_conflict_records: List[Dict[str, Any]],
    ):
        self.new_records = new_records
        self.conflict_records = conflict_records
        self.no_conflict_records = no_conflict_records


# 业务唯一键映射（不依赖org_id）
BUSINESS_KEY_FIELDS = {
    "villages": ["village_name"],  # 帮扶村使用村名作为唯一键
    "projects": ["code"],  # 项目使用code作为唯一键
    "funds": ["code"],  # 资金使用code作为唯一键
    "schools": ["code"],  # 学校使用code作为唯一键
}

# 数据类型模型映射
DATA_TYPE_MODELS = {
    "villages": SupportedVillage,
    "projects": Project,
    "funds": Fund,
    "schools": School,
}


class SmartConflictResolver:
    """智能冲突解决器"""

    def __init__(self, db: Session):
        self.db = db

    def detect_conflicts_by_business_key(self, import_records: List[Dict], data_type: str) -> ConflictDetectionResult:
        """
        基于业务唯一键检测冲突

        Args:
            import_records: 导入的记录列表
            data_type: 数据类型（villages/projects/funds/schools）

        Returns:
            冲突检测结果
        """
        model_class = DATA_TYPE_MODELS.get(data_type)
        if not model_class:
            raise ValueError(f"不支持的数据类型: {data_type}")

        key_fields = BUSINESS_KEY_FIELDS.get(data_type, [])
        if not key_fields:
            raise ValueError(f"未定义业务键: {data_type}")

        new_records = []
        conflict_records = []
        no_conflict_records = []

        for import_record in import_records:
            # 构建业务键查询条件（仅使用code字段）
            business_key = {field: import_record.get(field) for field in key_fields}

            # 查询本地是否存在相同业务键的记录
            query_conditions = [getattr(model_class, k) == v for k, v in business_key.items() if v is not None]

            if not query_conditions:
                # 如果没有有效的业务键，视为新记录
                new_records.append(import_record)
                continue

            local_record = self.db.query(model_class).filter(and_(*query_conditions)).first()

            if not local_record:
                # 本地不存在，标记为新记录
                new_records.append(import_record)
            else:
                # 本地存在，检查字段差异
                differences = self._find_differences(local_record, import_record)

                if differences:
                    # 有差异，标记为冲突
                    conflict = DataConflict(
                        data_type=data_type,
                        business_key=business_key,
                        local_record=local_record,
                        import_record=import_record,
                        differences=differences,
                    )
                    conflict_records.append(conflict)
                else:
                    # 无差异，标记为无冲突
                    no_conflict_records.append(import_record)

        return ConflictDetectionResult(
            new_records=new_records,
            conflict_records=conflict_records,
            no_conflict_records=no_conflict_records,
        )

    def _find_differences(self, local_record: Any, import_record: Dict[str, Any]) -> List[str]:
        """
        查找本地记录和导入记录的差异字段

        Args:
            local_record: 本地数据库记录
            import_record: 导入的记录字典

        Returns:
            差异字段名列表
        """
        differences = []

        # 忽略的字段（ID、时间戳等）
        ignore_fields = {"id", "created_at", "updated_at", "created_by", "updated_by"}

        for key, import_value in import_record.items():
            if key in ignore_fields:
                continue

            if hasattr(local_record, key):
                local_value = getattr(local_record, key)

                # 处理None值比较
                if local_value is None and import_value is None:
                    continue

                # 类型转换后比较
                if str(local_value) != str(import_value):
                    differences.append(key)

        return differences

    def resolve_conflicts_with_strategy(  # noqa: C901
        self, conflicts: List[DataConflict], strategy: str
    ) -> Dict[str, Dict[int, int]]:
        """
        按策略解决冲突

        Args:
            conflicts: 冲突列表
            strategy: 解决策略（SKIP/OVERWRITE/KEEP_BOTH/MERGE）

        Returns:
            ID映射表 {data_type: {old_id: new_id}}
        """
        id_mapping = {}

        for conflict in conflicts:
            data_type = conflict.data_type
            model_class = DATA_TYPE_MODELS[data_type]
            local_record = conflict.local_record
            import_record = conflict.import_record
            old_id = import_record.get("id")

            if data_type not in id_mapping:
                id_mapping[data_type] = {}

            if strategy == ConflictStrategy.SKIP:
                # 保留本地数据，记录ID映射
                id_mapping[data_type][old_id] = local_record.id

            elif strategy == ConflictStrategy.OVERWRITE:
                # 用导入数据覆盖本地数据
                for key, value in import_record.items():
                    if key not in {"id", "created_at", "created_by"}:
                        setattr(local_record, key, value)
                self.db.flush()
                id_mapping[data_type][old_id] = local_record.id

            elif strategy == ConflictStrategy.KEEP_BOTH:
                # 创建新记录，修改业务键避免冲突
                new_data = import_record.copy()
                new_data.pop("id", None)

                # 修改业务键（添加时间戳后缀）
                code_field = self._get_code_field(data_type)
                if code_field and code_field in new_data:
                    original_code = new_data[code_field]
                    new_data[code_field] = f"{original_code}_imp_{int(time.time())}"

                new_record = model_class(**new_data)
                self.db.add(new_record)
                self.db.flush()
                id_mapping[data_type][old_id] = new_record.id

            elif strategy == ConflictStrategy.MERGE:
                # 智能合并：优先使用非空值
                for key, import_value in import_record.items():
                    if key not in {"id", "created_at", "created_by"}:
                        local_value = getattr(local_record, key, None)
                        # 如果本地值为空，使用导入值
                        if local_value is None and import_value is not None:
                            setattr(local_record, key, import_value)
                        # 如果都不为空，比较updated_at（如果有）
                        elif import_value is not None:
                            import_updated = import_record.get("updated_at")
                            local_updated = getattr(local_record, "updated_at", None)
                            if import_updated and local_updated and import_updated > local_updated:
                                setattr(local_record, key, import_value)
                self.db.flush()
                id_mapping[data_type][old_id] = local_record.id

            elif strategy == ConflictStrategy.AUTO:
                # 自动选择最佳策略
                auto_strategy = self._determine_auto_strategy(conflict)
                if auto_strategy == ConflictStrategy.SKIP:
                    id_mapping[data_type][old_id] = local_record.id
                elif auto_strategy == ConflictStrategy.OVERWRITE:
                    for key, value in import_record.items():
                        if key not in {"id", "created_at", "created_by"}:
                            setattr(local_record, key, value)
                    self.db.flush()
                    id_mapping[data_type][old_id] = local_record.id
                elif auto_strategy == ConflictStrategy.MERGE:
                    for key, import_value in import_record.items():
                        if key not in {"id", "created_at", "created_by"}:
                            local_value = getattr(local_record, key, None)
                            if local_value is None and import_value is not None:
                                setattr(local_record, key, import_value)
                            elif import_value is not None:
                                import_updated = import_record.get("updated_at")
                                local_updated = getattr(local_record, "updated_at", None)
                                if import_updated and local_updated and import_updated > local_updated:
                                    setattr(local_record, key, import_value)
                    self.db.flush()
                    id_mapping[data_type][old_id] = local_record.id

        return id_mapping

    def _get_code_field(self, data_type: str) -> Optional[str]:
        """获取数据类型的编码字段名"""
        code_fields = {
            "villages": "village_name",
            "projects": "code",
            "funds": "code",
            "schools": "code",
        }
        return code_fields.get(data_type)

    def _determine_auto_strategy(self, conflict: "DataConflict") -> str:
        """
        根据冲突特征自动选择最佳解决策略

        决策规则：
        1. 如果差异字段很少（≤2个），使用 MERGE（智能合并）
        2. 如果本地记录更新时间更近，使用 SKIP（保留本地）
        3. 如果导入记录更新时间更近，使用 OVERWRITE（使用导入）
        4. 默认使用 MERGE（最安全的策略）

        Args:
            conflict: 冲突信息

        Returns:
            最佳策略名称
        """
        # 差异字段数量
        diff_count = len(conflict.differences)

        # 少量差异 → 合并
        if diff_count <= 2:
            return ConflictStrategy.MERGE

        # 比较 updated_at 时间戳
        import_record = conflict.import_record
        local_record = conflict.local_record

        import_updated = import_record.get("updated_at")
        local_updated = getattr(local_record, "updated_at", None)

        if import_updated and local_updated:
            try:
                from datetime import datetime

                # 解析时间戳（兼容字符串和datetime对象）
                if isinstance(import_updated, str):
                    import_updated = datetime.fromisoformat(
                        import_updated.replace("Z", "+00:00")
                    )
                if isinstance(local_updated, str):
                    local_updated = datetime.fromisoformat(
                        local_updated.replace("Z", "+00:00")
                    )

                if import_updated > local_updated:
                    return ConflictStrategy.OVERWRITE
                else:
                    return ConflictStrategy.SKIP
            except (ValueError, TypeError):
                pass

        # 默认：智能合并
        return ConflictStrategy.MERGE

    def import_with_id_mapping(
        self,
        data_dict: Dict[str, List[Dict]],
        strategy: str = ConflictStrategy.KEEP_BOTH,
    ) -> Dict[str, Dict[int, int]]:
        """
        导入数据并维护ID映射表

        按依赖顺序导入：villages -> projects -> funds -> schools

        Args:
            data_dict: 数据字典 {data_type: [records]}
            strategy: 冲突解决策略

        Returns:
            ID映射表 {data_type: {old_id: new_id}}
        """
        from datetime import datetime

        id_mapping = {}

        # 按依赖顺序处理
        import_order = ["villages", "schools", "projects", "funds"]

        for data_type in import_order:
            if data_type not in data_dict:
                continue

            records = data_dict[data_type]
            if not records:
                continue

            # 转换日期时间字段
            for record in records:
                for field in ["created_at", "updated_at"]:
                    if field in record and isinstance(record[field], str):
                        try:
                            record[field] = datetime.fromisoformat(record[field].replace("Z", "+00:00"))
                        except (ValueError, AttributeError):
                            record[field] = None

            records = data_dict[data_type]
            if not records:  # pragma: no cover — 与上方 369 行同为 data_dict[data_type] 的重复判空，369 行非空此处必非空，不可达
                continue

            # 检测冲突
            detection_result = self.detect_conflicts_by_business_key(records, data_type)

            # 导入新记录
            type_id_mapping = self._import_new_records(detection_result.new_records, data_type, id_mapping)

            # 解决冲突
            conflict_id_mapping = self.resolve_conflicts_with_strategy(detection_result.conflict_records, strategy)

            # 合并ID映射
            if data_type not in id_mapping:
                id_mapping[data_type] = {}
            id_mapping[data_type].update(type_id_mapping.get(data_type, {}))
            id_mapping[data_type].update(conflict_id_mapping.get(data_type, {}))

        return id_mapping

    def _import_new_records(
        self,
        new_records: List[Dict],
        data_type: str,
        id_mapping: Dict[str, Dict[int, int]],
    ) -> Dict[str, Dict[int, int]]:
        """
        导入新记录

        Args:
            new_records: 新记录列表
            data_type: 数据类型
            id_mapping: 已有的ID映射表（用于更新外键）

        Returns:
            新记录的ID映射
        """
        model_class = DATA_TYPE_MODELS[data_type]
        type_id_mapping = {}

        for record in new_records:
            old_id = record.get("id")
            new_data = record.copy()
            new_data.pop("id", None)

            # 更新外键引用
            self._update_foreign_keys(new_data, data_type, id_mapping)

            new_record = model_class(**new_data)
            self.db.add(new_record)
            self.db.flush()

            type_id_mapping[old_id] = new_record.id

        return {data_type: type_id_mapping}

    def _update_foreign_keys(self, record_data: Dict, data_type: str, id_mapping: Dict[str, Dict[int, int]]) -> None:
        """
        更新记录中的外键引用

        Args:
            record_data: 记录数据
            data_type: 数据类型
            id_mapping: ID映射表
        """
        # 外键映射关系
        foreign_key_mapping = {
            "projects": {"village_id": "villages"},
            "funds": {"project_id": "projects"},
        }

        if data_type in foreign_key_mapping:
            for fk_field, ref_type in foreign_key_mapping[data_type].items():
                if fk_field in record_data and record_data[fk_field]:
                    old_fk_id = record_data[fk_field]
                    if ref_type in id_mapping and old_fk_id in id_mapping[ref_type]:
                        record_data[fk_field] = id_mapping[ref_type][old_fk_id]
