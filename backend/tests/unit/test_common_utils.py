"""Tests for app/utils/common.py — 100% coverage."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from app.utils.common import (
    CryptoHelper,
    DataConverter,
    PageInfo,
    PaginationHelper,
    StringHelper,
    Validator,
    dict_keys_to_camel,
)


# ============================================================================
# Test helpers
# ============================================================================

class SimpleModel(BaseModel):
    name: str
    value: int = 0


class DumbModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def make_sa_model(**fields):
    obj = MagicMock()
    obj.__table__ = MagicMock()
    cols = []
    for name, val in fields.items():
        col = MagicMock()
        col.name = name
        cols.append(col)
        setattr(obj, name, val)
    obj.__table__.columns = cols
    return obj


# ============================================================================
# Test: DataConverter.to_dict
# ============================================================================

class TestToDict:
    def test_dict_input(self):
        result = DataConverter.to_dict({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_dict_input_with_exclude(self):
        result = DataConverter.to_dict({"a": 1, "b": 2, "c": 3}, exclude=["b"])
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_pydantic_model(self):
        m = SimpleModel(name="foo", value=42)
        result = DataConverter.to_dict(m)
        assert result == {"name": "foo", "value": 42}

    def test_pydantic_model_with_exclude(self):
        m = SimpleModel(name="foo", value=42)
        result = DataConverter.to_dict(m, exclude=["value"])
        assert result == {"name": "foo"}

    def test_sa_model(self):
        obj = make_sa_model(id=1, name="test", active=True)
        result = DataConverter.to_dict(obj)
        assert result == {"id": 1, "name": "test", "active": True}

    def test_sa_model_with_exclude(self):
        obj = make_sa_model(id=1, name="test")
        result = DataConverter.to_dict(obj, exclude=["name"])
        assert result == {"id": 1}

    def test_sa_model_with_datetime(self):
        dt = datetime(2024, 6, 15, 10, 30, 0)
        obj = make_sa_model(id=1, created_at=dt)
        result = DataConverter.to_dict(obj)
        assert result["created_at"] == "2024-06-15T10:30:00"

    def test_sa_model_with_date(self):
        d = date(2024, 6, 15)
        obj = make_sa_model(id=1, event_date=d)
        result = DataConverter.to_dict(obj)
        assert result["event_date"] == "2024-06-15"

    def test_regular_object(self):
        class Obj:
            def __init__(self):
                self.a = 1
                self.b = "hello"
                self._private = "secret"
        result = DataConverter.to_dict(Obj())
        assert result == {"a": 1, "b": "hello"}

    def test_regular_object_with_exclude(self):
        class Obj:
            def __init__(self):
                self.a = 1
                self.b = "hello"
                self.c = "world"
        result = DataConverter.to_dict(Obj(), exclude=["b"])
        assert result == {"a": 1, "c": "world"}


# ============================================================================
# Test: DataConverter.to_model
# ============================================================================

class TestToModel:
    def test_to_model(self):
        data = {"name": "test", "value": 42, "ignore": None}
        result = DataConverter.to_model(data, DumbModel)
        assert result.name == "test"
        assert result.value == 42
        assert not hasattr(result, "ignore")

    def test_to_model_empty(self):
        result = DataConverter.to_model({}, DumbModel)
        assert isinstance(result, DumbModel)


# ============================================================================
# Test: DataConverter.batch_to_dict
# ============================================================================

class TestBatchToDict:
    def test_batch_to_dict(self):
        items = [SimpleModel(name="a", value=1), SimpleModel(name="b", value=2)]
        result = DataConverter.batch_to_dict(items)
        assert result == [{"name": "a", "value": 1}, {"name": "b", "value": 2}]

    def test_batch_to_dict_with_exclude(self):
        items = [SimpleModel(name="a", value=1)]
        result = DataConverter.batch_to_dict(items, exclude=["value"])
        assert result == [{"name": "a"}]


# ============================================================================
# Test: PageInfo
# ============================================================================

class TestPageInfo:
    def test_defaults(self):
        p = PageInfo()
        assert p.page == 1
        assert p.page_size == 10
        assert p.total == 0
        assert p.total_pages == 0
        assert p.has_next is False
        assert p.has_prev is False

    def test_custom(self):
        p = PageInfo(page=3, page_size=20, total=100, total_pages=5, has_next=True, has_prev=True)
        assert p.page == 3


# ============================================================================
# Test: PaginationHelper.paginate
# ============================================================================

class TestPaginate:
    def make_query(self, total, items):
        query = MagicMock()
        query.count.return_value = total
        limited_q = MagicMock()
        limited_q.all.return_value = items
        offset_q = MagicMock()
        offset_q.limit.return_value = limited_q
        query.offset.return_value = offset_q
        return query

    def test_page_clamped_low(self):
        q = self.make_query(0, [])
        items, info = PaginationHelper.paginate(q, page=0, page_size=10)
        assert info.page == 1

    def test_page_size_clamped_low(self):
        q = self.make_query(0, [])
        items, info = PaginationHelper.paginate(q, page=1, page_size=0)
        assert info.page_size == 1

    def test_page_size_clamped_high(self):
        q = self.make_query(0, [])
        items, info = PaginationHelper.paginate(q, page=1, page_size=999, max_page_size=50)
        assert info.page_size == 50

    def test_first_page_no_items(self):
        q = self.make_query(0, [])
        items, info = PaginationHelper.paginate(q, page=1, page_size=10)
        assert items == []
        assert info.total == 0
        assert info.has_next is False
        assert info.has_prev is False

    def test_middle_page(self):
        q = self.make_query(50, [MagicMock() for _ in range(10)])
        items, info = PaginationHelper.paginate(q, page=3, page_size=10)
        assert info.page == 3
        assert info.total == 50
        assert info.total_pages == 5
        assert info.has_next is True
        assert info.has_prev is True

    def test_last_page(self):
        q = self.make_query(25, [MagicMock() for _ in range(5)])
        items, info = PaginationHelper.paginate(q, page=5, page_size=5)
        assert info.has_next is False
        assert info.has_prev is True

    def test_exact_fit(self):
        q = self.make_query(20, [MagicMock() for _ in range(10)])
        items, info = PaginationHelper.paginate(q, page=2, page_size=10)
        assert info.total_pages == 2
        assert info.has_next is False
        assert info.has_prev is True


# ============================================================================
# Test: PaginationHelper.create_page_result
# ============================================================================

class TestCreatePageResult:
    def test_create_page_result(self):
        info = PageInfo(page=1, page_size=10, total=5, total_pages=1)
        items = ["a", "b"]
        result = PaginationHelper.create_page_result(items, info)
        assert result["items"] == ["a", "b"]
        assert result["pagination"]["page"] == 1
        assert result["pagination"]["total"] == 5


# ============================================================================
# Test: CryptoHelper
# ============================================================================

class TestCryptoHelper:
    def test_generate_token(self):
        with patch("app.utils.common.secrets.token_urlsafe", return_value="mytoken"):
            assert CryptoHelper.generate_token(16) == "mytoken"

    def test_generate_token_default(self):
        with patch("app.utils.common.secrets.token_urlsafe") as mock_t:
            CryptoHelper.generate_token()
            mock_t.assert_called_with(32)

    def test_generate_hex_token(self):
        with patch("app.utils.common.secrets.token_hex", return_value="hex123"):
            assert CryptoHelper.generate_hex_token(16) == "hex123"

    def test_generate_hex_token_default(self):
        with patch("app.utils.common.secrets.token_hex") as mock_t:
            CryptoHelper.generate_hex_token()
            mock_t.assert_called_with(32)

    def test_hash_password_without_salt(self):
        with patch("app.utils.common.secrets.token_hex", return_value="abcdef123456"):
            h, s = CryptoHelper.hash_password("mypassword")
            assert s == "abcdef123456"
            assert isinstance(h, str)
            assert len(h) == 64

    def test_hash_password_with_salt(self):
        h, s = CryptoHelper.hash_password("mypassword", salt="fixedsalt123")
        assert s == "fixedsalt123"
        assert isinstance(h, str)
        assert len(h) == 64

    def test_verify_password_correct(self):
        h, s = CryptoHelper.hash_password("mypassword")
        assert CryptoHelper.verify_password("mypassword", h, s) is True

    def test_verify_password_incorrect(self):
        h, s = CryptoHelper.hash_password("correctpassword")
        assert CryptoHelper.verify_password("wrongpassword", h, s) is False

    def test_md5_hash(self):
        result = CryptoHelper.md5_hash("hello")
        assert isinstance(result, str)
        assert len(result) == 32

    def test_sha256_hash(self):
        result = CryptoHelper.sha256_hash("hello")
        assert isinstance(result, str)
        assert len(result) == 64


# ============================================================================
# Test: StringHelper
# ============================================================================

class TestMaskSensitive:
    def test_empty_string(self):
        assert StringHelper.mask_sensitive("") == ""

    def test_none_or_empty_returns_empty(self):
        assert StringHelper.mask_sensitive("") == ""
        assert StringHelper.mask_sensitive("", show_chars=4) == ""

    def test_shorter_or_equal_to_show_chars(self):
        result = StringHelper.mask_sensitive("ab", show_chars=4)
        assert result == "**"

    def test_longer_than_show_chars(self):
        result = StringHelper.mask_sensitive("hello12345", show_chars=5)
        assert result == "hello*****"

    def test_default_show_chars(self):
        result = StringHelper.mask_sensitive("hello12345")
        assert result == "hell******"


class TestTruncate:
    def test_shorter_than_length(self):
        assert StringHelper.truncate("hello", length=10) == "hello"

    def test_equal_to_length(self):
        assert StringHelper.truncate("hello", length=5) == "hello"

    def test_longer_than_length(self):
        result = StringHelper.truncate("hello world", length=8, suffix="...")
        assert result == "hello..."

    def test_default_suffix(self):
        result = StringHelper.truncate("hello world this is a long string that goes beyond fifty characters total", length=10)
        assert result == "hello w..."

    def test_custom_suffix(self):
        result = StringHelper.truncate("hello world", length=8, suffix="!")
        assert result == "hello w!"


class TestToSnakeCase:
    def test_simple(self):
        assert StringHelper.to_snake_case("camelCase") == "camel_case"

    def test_multiple_uppercase(self):
        assert StringHelper.to_snake_case("XMLParser") == "xml_parser"

    def test_already_snake(self):
        assert StringHelper.to_snake_case("already_snake") == "already_snake"

    def test_empty(self):
        assert StringHelper.to_snake_case("") == ""


class TestToCamelCase:
    def test_simple(self):
        assert StringHelper.to_camel_case("snake_case") == "snakeCase"

    def test_single_word(self):
        assert StringHelper.to_camel_case("hello") == "hello"

    def test_multi_word(self):
        assert StringHelper.to_camel_case("convert_to_camel_case") == "convertToCamelCase"


# ============================================================================
# Test: dict_keys_to_camel
# ============================================================================

class TestDictKeysToCamel:
    def test_non_dict_input(self):
        assert dict_keys_to_camel("string") == "string"
        assert dict_keys_to_camel(42) == 42
        assert dict_keys_to_camel(None) is None

    def test_simple_dict(self):
        result = dict_keys_to_camel({"user_name": "john", "user_age": 30})
        assert result == {"userName": "john", "userAge": 30}

    def test_nested_dict(self):
        result = dict_keys_to_camel({"user_info": {"first_name": "John", "last_name": "Doe"}})
        assert result == {"userInfo": {"firstName": "John", "lastName": "Doe"}}

    def test_nested_list(self):
        result = dict_keys_to_camel({"user_list": [{"item_name": "a"}, {"item_name": "b"}]})
        assert result == {"userList": [{"itemName": "a"}, {"itemName": "b"}]}

    def test_non_string_keys(self):
        result = dict_keys_to_camel({1: "one", 2: "two"})
        assert result == {1: "one", 2: "two"}

    def test_mixed_values(self):
        result = dict_keys_to_camel({"simple_value": 42, "nested_dict": {"inner_key": "val"}})
        assert result == {"simpleValue": 42, "nestedDict": {"innerKey": "val"}}

    def test_empty_dict(self):
        assert dict_keys_to_camel({}) == {}


# ============================================================================
# Test: Validator
# ============================================================================

class TestIsValidEmail:
    def test_valid_email(self):
        assert Validator.is_valid_email("a@a.zz") is True

    def test_invalid_email_no_at(self):
        assert Validator.is_valid_email("notanemail") is False

    def test_invalid_email_short_tld(self):
        assert Validator.is_valid_email("a@a.z") is False


class TestIsValidPhone:
    def test_valid_phone(self):
        assert Validator.is_valid_phone("13800138000") is True

    def test_invalid_phone_too_short(self):
        assert Validator.is_valid_phone("123") is False

    def test_invalid_phone_too_long(self):
        assert Validator.is_valid_phone("138001380001") is False


class TestIsValidIdCard:
    def test_valid_id_card(self):
        assert Validator.is_valid_id_card("110101199001011234") is True

    def test_valid_id_card_with_x(self):
        assert Validator.is_valid_id_card("11010119900101123X") is True
        assert Validator.is_valid_id_card("11010119900101123x") is True

    def test_invalid_id_card_too_long(self):
        assert Validator.is_valid_id_card("1101011990010112345") is False

    def test_invalid_id_card_too_short(self):
        assert Validator.is_valid_id_card("11010119900101123") is False
