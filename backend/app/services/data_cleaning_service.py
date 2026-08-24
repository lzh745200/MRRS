"""
数据清洗服务
提供数据去重、格式标准化、缺失值填充等功能
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DataCleaningService:
    """数据清洗服务"""

    @staticmethod
    def deduplicate(
        records: List[Dict[str, Any]],
        key_fields: List[str],
        similarity_threshold: float = 0.9,
    ) -> List[Dict[str, Any]]:
        """
        数据去重(支持模糊匹配)

        Args:
            records: 记录列表
            key_fields: 用于比较的关键字段
            similarity_threshold: 相似度阈值(0-1)

        Returns:
            去重后的记录列表
        """
        if not records:
            return []

        unique_records = []
        seen_keys = []

        for record in records:
            # 构建关键字段组合
            key_values = tuple(str(record.get(field, "")) for field in key_fields)

            # 检查是否与已有记录相似
            is_duplicate = False
            for seen_key in seen_keys:
                similarity = DataCleaningService._calculate_similarity(key_values, seen_key)
                if similarity >= similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_records.append(record)
                seen_keys.append(key_values)

        logger.info(f"去重: {len(records)} -> {len(unique_records)} 条记录")
        return unique_records

    @staticmethod
    def _calculate_similarity(tuple1: tuple, tuple2: tuple) -> float:
        """计算两个元组的相似度"""
        if len(tuple1) != len(tuple2):
            return 0.0

        similarities = []
        for val1, val2 in zip(tuple1, tuple2):
            sim = SequenceMatcher(None, val1, val2).ratio()
            similarities.append(sim)

        return sum(similarities) / len(similarities) if similarities else 0.0

    @staticmethod
    def standardize_phone(phone: str) -> Optional[str]:
        """
        标准化电话号码

        Args:
            phone: 原始电话号码

        Returns:
            标准化后的电话号码
        """
        if not phone:
            return None

        # 移除所有非数字字符
        digits = re.sub(r"\D", "", phone)

        # 中国手机号
        if len(digits) == 11 and digits.startswith("1"):
            return digits

        # 固定电话(带区号)
        if len(digits) >= 10:
            return digits

        return None

    @staticmethod
    def standardize_email(email: str) -> Optional[str]:
        """
        标准化邮箱地址

        Args:
            email: 原始邮箱

        Returns:
            标准化后的邮箱
        """
        if not email:
            return None

        # 转小写并去除空格
        email = email.lower().strip()

        # 验证格式
        if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            return email

        return None

    @staticmethod
    def standardize_address(address: str) -> Optional[str]:
        """
        标准化地址

        Args:
            address: 原始地址

        Returns:
            标准化后的地址
        """
        if not address:
            return None

        # 去除多余空格
        address = re.sub(r"\s+", " ", address.strip())

        # 统一省市县的写法
        replacements = {
            "省": "省",
            "市": "市",
            "县": "县",
            "区": "区",
            "镇": "镇",
            "乡": "乡",
            "村": "村",
        }

        for old, new in replacements.items():
            address = address.replace(old, new)

        return address

    @staticmethod
    def _fill_default(
        records: List[Dict[str, Any]], field_name: str, default_value: Any
    ) -> None:
        for record in records:
            if record.get(field_name) is None or record.get(field_name) == "":
                record[field_name] = default_value

    @staticmethod
    def _fill_mean(records: List[Dict[str, Any]], field_name: str) -> None:
        values = [record.get(field_name) for record in records if record.get(field_name) is not None]
        if not values:
            return
        try:
            mean_value = sum(values) / len(values)
            for record in records:
                if record.get(field_name) is None:
                    record[field_name] = mean_value
        except (TypeError, ValueError):
            logger.warning(f"无法计算{field_name}的平均值")

    @staticmethod
    def _fill_median(records: List[Dict[str, Any]], field_name: str) -> None:
        values = sorted([record.get(field_name) for record in records if record.get(field_name) is not None])
        if not values:
            return
        median_value = values[len(values) // 2]
        for record in records:
            if record.get(field_name) is None:
                record[field_name] = median_value

    @staticmethod
    def _fill_mode(records: List[Dict[str, Any]], field_name: str) -> None:
        from collections import Counter

        values = [record.get(field_name) for record in records if record.get(field_name) is not None]
        if not values:
            return
        mode_value = Counter(values).most_common(1)[0][0]
        for record in records:
            if record.get(field_name) is None:
                record[field_name] = mode_value

    @staticmethod
    def fill_missing_values(
        records: List[Dict[str, Any]],
        field_name: str,
        strategy: str = "default",
        default_value: Any = None,
    ) -> List[Dict[str, Any]]:
        """
        填充缺失值

        Args:
            records: 记录列表
            field_name: 字段名
            strategy: 填充策略(default/mean/median/mode)
            default_value: 默认值(strategy='default'时使用)

        Returns:
            填充后的记录列表
        """
        if not records:
            return []

        if strategy == "default":
            DataCleaningService._fill_default(records, field_name, default_value)
        elif strategy == "mean":
            DataCleaningService._fill_mean(records, field_name)
        elif strategy == "median":
            DataCleaningService._fill_median(records, field_name)
        elif strategy == "mode":
            DataCleaningService._fill_mode(records, field_name)

        return records

    @staticmethod
    def clean_dataset(records: List[Dict[str, Any]], cleaning_rules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        批量清洗数据集

        Args:
            records: 记录列表
            cleaning_rules: 清洗规则配置

        Returns:
            清洗后的记录列表
        """
        # 去重
        if cleaning_rules.get("deduplicate"):
            key_fields = cleaning_rules["deduplicate"].get("key_fields", [])
            threshold = cleaning_rules["deduplicate"].get("threshold", 0.9)
            records = DataCleaningService.deduplicate(records, key_fields, threshold)

        # 格式标准化
        if cleaning_rules.get("standardize"):
            for field_config in cleaning_rules["standardize"]:
                field_name = field_config["field"]
                field_type = field_config["type"]

                for record in records:
                    value = record.get(field_name)
                    if value:
                        if field_type == "phone":
                            record[field_name] = DataCleaningService.standardize_phone(value)
                        elif field_type == "email":
                            record[field_name] = DataCleaningService.standardize_email(value)
                        elif field_type == "address":
                            record[field_name] = DataCleaningService.standardize_address(value)

        # 填充缺失值
        if cleaning_rules.get("fill_missing"):
            for field_config in cleaning_rules["fill_missing"]:
                field_name = field_config["field"]
                strategy = field_config.get("strategy", "default")
                default_value = field_config.get("default_value")

                records = DataCleaningService.fill_missing_values(records, field_name, strategy, default_value)

        if cleaning_rules.get("trim_whitespace"):
            DataCleaningService._trim_strings(records)
        if cleaning_rules.get("normalize_empty"):
            DataCleaningService._normalize_empty(records)

        return records

    @staticmethod
    def _trim_strings(records: List[Dict[str, Any]]) -> None:
        """空白裁剪：所有字符串字段去除首尾空白。"""
        for record in records:
            for key, value in list(record.items()):
                if isinstance(value, str):
                    record[key] = value.strip()

    @staticmethod
    def _normalize_empty(records: List[Dict[str, Any]]) -> None:
        """空值规范化：空白串与常见占位符统一置 None。"""
        placeholders = {"", "-", "--", "无", "N/A", "n/a", "null", "None", "未知"}
        for record in records:
            for key, value in list(record.items()):
                if isinstance(value, str) and value.strip() in placeholders:
                    record[key] = None
