"""通用工具函数模块"""

import hashlib
import hmac
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class DataConverter:
    """数据转换器"""

    @staticmethod
    def to_dict(obj: Any, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """将对象转换为字典

        Args:
            obj: 要转换的对象
            exclude: 要排除的字段列表

        Returns:
            转换后的字典
        """
        if isinstance(obj, dict):
            return obj

        exclude = exclude or []

        # Pydantic模型
        if isinstance(obj, BaseModel):
            return obj.model_dump(exclude=set(exclude))

        # SQLAlchemy模型
        if hasattr(obj, "__table__"):
            result = {}
            for column in obj.__table__.columns:
                if column.name not in exclude:
                    value = getattr(obj, column.name)
                    if isinstance(value, (datetime, date)):
                        value = value.isoformat()
                    result[column.name] = value
            return result

        # 普通对象
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_") and k not in exclude}

    @staticmethod
    def to_model(data: Dict[str, Any], model_class: Type[T]) -> T:
        """将字典转换为模型

        Args:
            data: 数据字典
            model_class: 模型类

        Returns:
            模型实例
        """
        filtered_data = {k: v for k, v in data.items() if v is not None}
        return model_class(**filtered_data)

    @staticmethod
    def batch_to_dict(objects: List[Any], exclude: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """批量将对象转换为字典

        Args:
            objects: 对象列表
            exclude: 要排除的字段列表

        Returns:
            字典列表
        """
        return [DataConverter.to_dict(obj, exclude) for obj in objects]


class PageInfo(BaseModel):
    """分页信息"""

    page: int = 1
    page_size: int = 10
    total: int = 0
    total_pages: int = 0
    has_next: bool = False
    has_prev: bool = False


class PaginationHelper:
    """分页助手"""

    @staticmethod
    def paginate(query, page: int = 1, page_size: int = 10, max_page_size: int = 100) -> tuple:
        """对查询进行分页

        Args:
            query: SQLAlchemy查询
            page: 页码
            page_size: 每页数量
            max_page_size: 最大每页数量

        Returns:
            (items, page_info)元组
        """
        page = max(1, page)
        page_size = min(max(1, page_size), max_page_size)

        total = query.count()
        total_pages = (total + page_size - 1) // page_size
        has_next = page < total_pages
        has_prev = page > 1

        offset = (page - 1) * page_size
        items = query.offset(offset).limit(page_size).all()

        page_info = PageInfo(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
        )

        return items, page_info

    @staticmethod
    def create_page_result(items: List[T], page_info: PageInfo) -> Dict[str, Any]:
        """创建分页结果

        Args:
            items: 数据项列表
            page_info: 分页信息

        Returns:
            分页结果字典
        """
        return {"items": items, "pagination": page_info.model_dump()}


class DateTimeHelper:
    """日期时间助手"""

    FORMAT_DATE = "%Y-%m-%d"
    FORMAT_DATETIME = "%Y-%m-%d %H:%M:%S"
    FORMAT_ISO = "%Y-%m-%dT%H:%M:%S"

    @staticmethod
    def now() -> datetime:
        """获取当前时间"""
        return datetime.now()

    @staticmethod
    def today() -> date:
        """获取今天日期"""
        return date.today()

    @staticmethod
    def format_datetime(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M:%S") -> Optional[str]:
        """格式化日期时间

        Args:
            dt: 日期时间对象
            fmt: 格式字符串

        Returns:
            格式化后的字符串
        """
        if not dt:
            return None
        return dt.strftime(fmt)

    @staticmethod
    def parse_datetime(dt_str: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
        """解析日期时间字符串

        Args:
            dt_str: 日期时间字符串
            fmt: 格式字符串

        Returns:
            日期时间对象
        """
        try:
            return datetime.strptime(dt_str, fmt)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def to_iso_string(dt: Optional[datetime]) -> Optional[str]:
        """转换为ISO格式字符串"""
        if not dt:
            return None
        return dt.isoformat()

    @staticmethod
    def from_iso_string(iso_str: str) -> Optional[datetime]:
        """从ISO格式字符串解析"""
        try:
            return datetime.fromisoformat(iso_str)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def add_days(dt: datetime, days: int) -> datetime:
        """添加天数"""
        return dt + timedelta(days=days)

    @staticmethod
    def add_hours(dt: datetime, hours: int) -> datetime:
        """添加小时数"""
        return dt + timedelta(hours=hours)

    @staticmethod
    def diff_days(dt1: datetime, dt2: datetime) -> int:
        """计算天数差"""
        return (dt1 - dt2).days

    @staticmethod
    def is_expired(dt: datetime) -> bool:
        """检查是否过期"""
        return dt < datetime.now()

    @staticmethod
    def get_date_range(start: date, end: date) -> List[date]:
        """获取日期范围

        Args:
            start: 开始日期
            end: 结束日期

        Returns:
            日期列表
        """
        days = (end - start).days + 1
        return [start + timedelta(days=i) for i in range(days)]


class CryptoHelper:
    """加密助手"""

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """生成随机token

        Args:
            length: token长度

        Returns:
            随机token
        """
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_hex_token(length: int = 32) -> str:
        """生成十六进制token

        Args:
            length: token长度

        Returns:
            十六进制token
        """
        return secrets.token_hex(length)

    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> tuple:
        """哈希密码

        Args:
            password: 密码
            salt: 盐值

        Returns:
            (哈希值, 盐值)元组
        """
        if not salt:
            salt = secrets.token_hex(16)

        hash_obj = hashlib.sha256()
        hash_obj.update(f"{password}{salt}".encode("utf-8"))
        hashed = hash_obj.hexdigest()

        return hashed, salt

    @staticmethod
    def verify_password(password: str, hashed: str, salt: str) -> bool:
        """验证密码

        Args:
            password: 密码
            hashed: 哈希值
            salt: 盐值

        Returns:
            是否匹配
        """
        new_hash, _ = CryptoHelper.hash_password(password, salt)
        return hmac.compare_digest(new_hash, hashed)

    @staticmethod
    def md5_hash(text: str) -> str:
        """计算MD5哈希"""
        return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()

    @staticmethod
    def sha256_hash(text: str) -> str:
        """计算SHA256哈希"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class StringHelper:
    """字符串助手"""

    @staticmethod
    def mask_sensitive(text: str, show_chars: int = 4) -> str:
        """掩码敏感信息

        Args:
            text: 原始文本
            show_chars: 显示的字符数

        Returns:
            掩码后的文本
        """
        if not text or len(text) <= show_chars:
            return "*" * len(text) if text else ""
        return text[:show_chars] + "*" * (len(text) - show_chars)

    @staticmethod
    def truncate(text: str, length: int = 50, suffix: str = "...") -> str:
        """截断文本

        Args:
            text: 原始文本
            length: 最大长度
            suffix: 后缀

        Returns:
            截断后的文本
        """
        if len(text) <= length:
            return text
        return text[: length - len(suffix)] + suffix

    @staticmethod
    def to_snake_case(text: str) -> str:
        """转换为蛇形命名"""
        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", text)
        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    @staticmethod
    def to_camel_case(text: str) -> str:
        """转换为驼峰命名"""
        components = text.split("_")
        return components[0] + "".join(x.title() for x in components[1:])


def dict_keys_to_camel(d: dict) -> dict:
    """将字典所有键名从 snake_case 转为 camelCase（递归）"""
    if not isinstance(d, dict):
        return d
    result = {}
    for k, v in d.items():
        if isinstance(k, str):
            new_key = StringHelper.to_camel_case(k)
        else:
            new_key = k
        if isinstance(v, dict):
            result[new_key] = dict_keys_to_camel(v)
        elif isinstance(v, list):
            result[new_key] = [dict_keys_to_camel(i) if isinstance(i, dict) else i for i in v]
        else:
            result[new_key] = v
    return result


class Validator:
    """验证器"""

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """验证邮箱格式"""
        # 原字符类里混入了空格（"[a - zA - Z0 - 9...]"），实际匹配的是
        # {a,' ','-','z','A','Z','0','9',…} 而非 a-z/A-Z/0-9 区间，
        # user@example.com 这类正常邮箱会被拒（深审 #82）。
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @staticmethod
    def is_valid_phone(phone: str) -> bool:
        """验证手机号格式"""
        # 原 "[3 - 9]" 是字面集合 {3,' ','-',9}，不是 3-9 区间 ——
        # 第二位为 4~8 的合法号段（145/156/176/188…）全被拒（深审 #83）。
        pattern = r"^1[3-9]\d{9}$"
        return bool(re.match(pattern, phone))

    @staticmethod
    def is_valid_id_card(id_card: str) -> bool:
        """验证身份证号格式"""
        pattern = r"^\d{17}[\dXx]$"
        return bool(re.match(pattern, id_card))
