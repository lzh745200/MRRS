"""Tests for app.core.mock_data - zero coverage → 100%"""

import pytest
import random
from datetime import datetime, timezone
from app.core.mock_data import (
    _random_date,
    _random_string,
    _random_phone,
    _random_id_card,
    create_mock_user,
    create_mock_users,
    create_mock_village,
    create_mock_villages,
    seed_id,
    random_status,
    random_amount,
)


class TestRandomDate:
    def test_returns_datetime(self):
        result = _random_date()
        assert isinstance(result, datetime)

    def test_within_past_days(self):
        random.seed(0)
        now = datetime.now(timezone.utc)
        result = _random_date(days_ago=30)
        diff = now - result
        assert diff.total_seconds() >= 0
        assert diff.days <= 31  # allow 1 day margin

    def test_deterministic_with_seed(self):
        # 彻底消除墙钟依赖：仅验证同一 seed 下 _random_date 消费的随机序列一致
        # （两次 now() 的微秒级间隔不影响断言，杜绝高负载下的偶发失败）
        random.seed(42)
        x1 = random.randint(0, 365)
        random.seed(42)
        a = _random_date()
        random.seed(42)
        b = _random_date()
        random.seed(42)
        x2 = random.randint(0, 365)
        assert x1 == x2
        assert abs((a - b).total_seconds()) < 5


class TestRandomString:
    def test_returns_string_of_correct_length(self):
        result = _random_string(15)
        assert len(result) == 15

    def test_default_length_is_10(self):
        result = _random_string()
        assert len(result) == 10

    def test_only_alphanumeric(self):
        result = _random_string(100)
        assert result.isalnum()

    def test_deterministic_with_seed(self):
        random.seed(7)
        a = _random_string()
        random.seed(7)
        b = _random_string()
        assert a == b

    def test_zero_length(self):
        result = _random_string(0)
        assert result == ""


class TestRandomPhone:
    def test_returns_11_digits(self):
        result = _random_phone()
        assert len(result) == 11
        assert result.isdigit()

    def test_starts_with_valid_prefix(self):
        random.seed(0)
        result = _random_phone()
        valid_prefixes = ["138", "139", "158", "159", "186", "188"]
        assert result[:3] in valid_prefixes


class TestRandomIdCard:
    def test_returns_18_chars(self):
        result = _random_id_card()
        assert len(result) == 18

    def test_ends_with_x_uppercase(self):
        random.seed(0)
        result = _random_id_card()
        assert result[-1] == "X"

    def test_first_17_are_digits(self):
        result = _random_id_card()
        assert result[:17].isdigit()


class TestCreateMockUser:
    def test_default_user_dict(self):
        random.seed(0)
        user = create_mock_user()
        assert "username" in user
        assert user["password_hash"] == "hashed_mock_password"
        assert user["role"] == "viewer"
        assert user["is_active"] is True
        assert "@example.com" in user["email"]
        assert len(user["phone"]) == 11
        assert len(user["id_card"]) == 18

    def test_custom_username_and_role(self):
        user = create_mock_user(username="testuser", role="admin", is_active=False)
        assert user["username"] == "testuser"
        assert user["role"] == "admin"
        assert user["is_active"] is False

    def test_auto_username_when_none(self):
        user = create_mock_user(username=None)
        assert user["username"].startswith("user_")

    def test_includes_real_name(self):
        user = create_mock_user(username="张三")
        assert user["real_name"] == "测试_张三"


class TestCreateMockUsers:
    def test_returns_correct_count(self):
        random.seed(0)
        users = create_mock_users(5)
        assert len(users) == 5

    def test_default_count_is_10(self):
        users = create_mock_users()
        assert len(users) == 10

    def test_each_has_username(self):
        random.seed(0)
        users = create_mock_users(3)
        for user in users:
            assert "username" in user

    def test_zero_count(self):
        users = create_mock_users(0)
        assert users == []


class TestCreateMockVillage:
    def test_default_village_dict(self):
        random.seed(0)
        village = create_mock_village()
        assert "name" in village
        assert village["region"] == "西南地区"
        assert 200 <= village["population"] <= 5000
        assert "description" in village
        assert isinstance(village["created_at"], datetime)

    def test_custom_name_and_region(self):
        village = create_mock_village(name="龙井村", region="华东")
        assert village["name"] == "龙井村"
        assert village["region"] == "华东"

    def test_picks_from_name_list_when_none(self):
        random.seed(99)
        from app.core.mock_data import _VILLAGE_NAMES
        village = create_mock_village(name=None)
        assert village["name"] in _VILLAGE_NAMES


class TestCreateMockVillages:
    def test_returns_correct_count(self):
        villages = create_mock_villages(6)
        assert len(villages) == 6

    def test_default_count_is_8(self):
        villages = create_mock_villages()
        assert len(villages) == 8

    def test_each_has_name(self):
        villages = create_mock_villages(3)
        for v in villages:
            assert "name" in v

    def test_zero_count(self):
        villages = create_mock_villages(0)
        assert villages == []


class TestSeedId:
    def test_returns_12_char_string(self):
        result = seed_id()
        assert len(result) == 12

    def test_returns_hex_string(self):
        result = seed_id()
        assert all(c in "0123456789abcdef" for c in result)

    def test_unique_on_each_call(self):
        results = {seed_id() for _ in range(100)}
        assert len(results) == 100


class TestRandomStatus:
    def test_returns_from_default_list(self):
        random.seed(0)
        result = random_status()
        defaults = ["待审核", "审核中", "已通过", "已驳回", "执行中", "已完成"]
        assert result in defaults

    def test_custom_choices(self):
        random.seed(0)
        result = random_status(["A", "B", "C"])
        assert result in ["A", "B", "C"]

    def test_single_choice(self):
        result = random_status(["only"])
        assert result == "only"

    def test_empty_choices(self):
        with pytest.raises(IndexError):
            random_status([])


class TestRandomAmount:
    def test_returns_float(self):
        result = random_amount()
        assert isinstance(result, float)

    def test_within_bounds(self):
        for _ in range(20):
            result = random_amount(100, 200)
            assert 100 <= result <= 200

    def test_rounded_to_2_decimals(self):
        result = random_amount(10.123, 99.999)
        # round to 2 decimal places
        assert result == round(result, 2)

    def test_min_equals_max(self):
        result = random_amount(50, 50)
        assert result == 50.0
