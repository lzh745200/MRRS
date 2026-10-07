"""
Smart Conflict Resolver
智能冲突解决服务 - 处理数据导入时的ID和业务键冲突
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, inspect as sa_inspect
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


# 永不允许由导入数据写入的列（主键/审计/租户边界），
# 深审 #61：原实现只排除 id/created_at/created_by，organization_id、
# updated_at 等会被导入值覆盖，破坏租户隔离与 DateTime 列类型。
_PROTECTED_COLUMNS = frozenset({
    "id",
    "created_at",
    "updated_at",
    "created_by",
    "updated_by",
    "organization_id",
})

# 租户列：冲突检测/归属校验都按它收敛（深审 #63）
_TENANT_COLUMN = "organization_id"


def _to_datetime(value: Any) -> Optional[datetime]:
    """把导入/本地的时间值归一为可安全比较的 datetime（深审 #60）。

    - datetime → 原样（naive 统一补 UTC，避免 naive/aware 比较 TypeError）
    - str → fromisoformat，支持尾部 Z
    - 其余/无法解析 → None（调用方视为"不可比较"，退回默认策略）
    """
    from datetime import timezone

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _model_columns(model_class: Any) -> set:
    """模型的可映射列名集合（用于过滤导入键，深审 #61）。

    优先取类上的 `__mapper__`（探针/替身可显式借用真实模型的 mapper）；
    否则退化为 sa_inspect。两者都拿不到时返回空集，调用方**不得**据此放行
    任意键 —— 见 `_writable_items` 的处理。
    """
    mapper = getattr(model_class, "__mapper__", None)
    if mapper is not None:
        try:
            return {c.key for c in mapper.column_attrs}
        except Exception:  # pragma: no cover — 防御
            pass
    try:
        return {c.key for c in sa_inspect(model_class).mapper.column_attrs}
    except Exception:  # pragma: no cover — 非映射类
        return set()


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

    def __init__(self, db: Session, organization_id: Optional[int] = None):
        """深审 #63：可选租户收敛。

        organization_id 非空时，冲突检测只会命中**本组织**行；命中他组织的
        同业务键记录既不改写（OVERWRITE/MERGE）也不复制（KEEP_BOTH），
        避免跨组织串改数据。为 None 时退回旧行为（仅用于系统级任务）。
        """
        self.db = db
        self.organization_id = organization_id

    def detect_conflicts_by_business_key(self, import_records: List[Dict], data_type: str) -> ConflictDetectionResult:
        """
        基于业务唯一键检测冲突

        Args:
            import_records: 导入的记录列表
            data_type: 数据类型（villages/projects/funds/schools）

        Returns:
            冲突检测结果
        """
        return self._detect_conflicts_impl(import_records, data_type)

    def _detect_conflicts_impl(self, import_records: List[Dict], data_type: str) -> ConflictDetectionResult:
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

            # 深审 #63：租户列参与收敛（模型确实有该列时才加）
            model_cols = _model_columns(model_class)
            if self.organization_id is not None and _TENANT_COLUMN in model_cols:
                query_conditions.append(
                    getattr(model_class, _TENANT_COLUMN) == self.organization_id
                )

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

    def _writable_items(self, model_class: Any, import_record: Dict[str, Any]):
        """过滤出可安全 setattr 的 (key, value)（深审 #61）。

        只保留模型**真实映射列**，排除 _PROTECTED_COLUMNS（主键/审计/租户）。
        原实现直接对 import_record 全键 setattr，会把扁平化/派生键写成实例属性，
        并覆盖 organization_id / updated_at（字符串 updated_at 破坏 DateTime 列）。
        """
        allowed = _model_columns(model_class)
        for key, value in import_record.items():
            if key in _PROTECTED_COLUMNS:
                continue
            if allowed and key not in allowed:
                continue
            yield key, value

    def _import_is_newer(self, import_record: Dict[str, Any], local_record: Any) -> bool:
        """导入记录的 updated_at 是否严格新于本地（深审 #60）。

        统一经 _to_datetime 归一；任一侧不可解析时视为"不可比较"→ False，
        避免 naive/aware 或 str/datetime 直接 `>` 抛 TypeError 中断整包导入。
        """
        import_updated = _to_datetime(import_record.get("updated_at"))
        local_updated = _to_datetime(getattr(local_record, "updated_at", None))
        if import_updated is None or local_updated is None:
            return False
        return import_updated > local_updated

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
                # 用导入数据覆盖本地数据（仅模型真实列，排除主键/审计/租户）
                for key, value in self._writable_items(model_class, import_record):
                    setattr(local_record, key, value)
                self.db.flush()
                id_mapping[data_type][old_id] = local_record.id

            elif strategy == ConflictStrategy.KEEP_BOTH:
                self._keep_both(conflict, id_mapping)

            elif strategy == ConflictStrategy.MERGE:
                # 智能合并：优先使用非空值
                newer = self._import_is_newer(import_record, local_record)
                for key, import_value in self._writable_items(model_class, import_record):
                    local_value = getattr(local_record, key, None)
                    # 如果本地值为空，使用导入值
                    if local_value is None and import_value is not None:
                        setattr(local_record, key, import_value)
                    # 都非空时仅在导入记录更新时覆盖
                    elif import_value is not None and newer:
                        setattr(local_record, key, import_value)
                self.db.flush()
                id_mapping[data_type][old_id] = local_record.id

            elif strategy == ConflictStrategy.AUTO:
                # 自动选择最佳策略
                auto_strategy = self._determine_auto_strategy(conflict)
                if auto_strategy == ConflictStrategy.SKIP:
                    id_mapping[data_type][old_id] = local_record.id
                elif auto_strategy == ConflictStrategy.OVERWRITE:
                    for key, value in self._writable_items(model_class, import_record):
                        setattr(local_record, key, value)
                    self.db.flush()
                    id_mapping[data_type][old_id] = local_record.id
                elif auto_strategy == ConflictStrategy.MERGE:
                    newer = self._import_is_newer(import_record, local_record)
                    for key, import_value in self._writable_items(model_class, import_record):
                        local_value = getattr(local_record, key, None)
                        if local_value is None and import_value is not None:
                            setattr(local_record, key, import_value)
                        elif import_value is not None and newer:
                            setattr(local_record, key, import_value)
                    self.db.flush()
                    id_mapping[data_type][old_id] = local_record.id

        return id_mapping

    def _keep_both(
        self,
        conflict: DataConflict,
        id_mapping: Dict[str, Dict[int, int]],
    ) -> None:
        """KEEP_BOTH：把导入记录插为新行（业务键加时间戳后缀避免再次冲突）。

        深审 #62：外键必须经 id_mapping 重映射，否则新行会挂到**源机**的
        村/项目 ID 上（轻则 FK 报错，重则关联到无关记录）。
        """
        data_type = conflict.data_type
        model_class = DATA_TYPE_MODELS[data_type]
        import_record = conflict.import_record
        old_id = import_record.get("id")

        new_data = {k: v for k, v in self._writable_items(model_class, import_record)}

        # 修改业务键（添加时间戳后缀）
        code_field = self._get_code_field(data_type)
        if code_field and code_field in new_data:
            original_code = new_data[code_field]
            new_data[code_field] = f"{original_code}_imp_{int(time.time())}"

        self._update_foreign_keys(new_data, data_type, id_mapping)

        new_record = model_class(**new_data)
        self.db.add(new_record)
        self.db.flush()
        id_mapping.setdefault(data_type, {})[old_id] = new_record.id

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

        # 比较 updated_at 时间戳（深审 #60：统一经 _to_datetime 归一，
        # 任一侧缺失/不可解析时返回 None 比较，避免 naive/aware 抛 TypeError）
        import_updated = _to_datetime(conflict.import_record.get("updated_at"))
        local_updated = _to_datetime(getattr(conflict.local_record, "updated_at", None))

        if import_updated is not None and local_updated is not None:
            if import_updated > local_updated:
                return ConflictStrategy.OVERWRITE
            return ConflictStrategy.SKIP

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
        id_mapping = {}

        # 按依赖顺序处理
        import_order = ["villages", "schools", "projects", "funds"]

        # 深审 #63：租户上下文由构造参数决定；导入记录不得携带他组织 organization_id
        tenant = self.organization_id

        for data_type in import_order:
            if data_type not in data_dict:
                continue

            records = data_dict[data_type]
            if not records:
                continue

            # 转换日期时间字段（深审 #60：归一为 datetime，便于后续安全比较）
            for record in records:
                for field in ["created_at", "updated_at"]:
                    if field in record and isinstance(record[field], str):
                        record[field] = _to_datetime(record[field])
                # 深审 #61/#63：导入数据不得跨组织写入其 organization_id
                if tenant is not None:
                    record[_TENANT_COLUMN] = tenant

            records = data_dict[data_type]
            if not records:  # pragma: no cover — 与上方 369 行同为 data_dict[data_type] 的重复判空，369 行非空此处必非空，不可达
                continue

            # 检测冲突
            detection_result = self.detect_conflicts_by_business_key(records, data_type)

            # 导入新记录
            type_id_mapping = self._import_new_records(detection_result.new_records, data_type, id_mapping)

            # 解决冲突
            conflict_id_mapping = self.resolve_conflicts_with_strategy(detection_result.conflict_records, strategy)

            # 合并ID映射（data_type 的键必然已在本轮循环上方初始化——调用方从不在跨轮复用 id_mapping，此防御检查无可达假分支）
            if data_type not in id_mapping:  # pragma: no cover - 死防御：类型键同轮已初始化，假分支需跨轮复用 id_mapping，全仓调用方均不跨轮复用
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
            # 深审 #61：同样按模型列集合过滤，避免派生/扁平键污染实例属性
            new_data = {k: v for k, v in self._writable_items(model_class, record)}

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
