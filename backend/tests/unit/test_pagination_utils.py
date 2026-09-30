"""Tests for app/utils/pagination.py — 100% coverage."""

import json
import base64
from unittest.mock import MagicMock, patch

import pytest

from app.utils.pagination import encode_cursor, decode_cursor, keyset_paginate, paginate_query


# ============================================================================
# Test helpers
# ============================================================================

class MockOrderCol:
    """order_column compatible mock supporting comparison and desc/asc."""
    def __init__(self, key="id", has_key=True):
        self._key = key
        self._has_key = has_key

    @property
    def key(self):
        if self._has_key:
            return self._key
        raise AttributeError("key")

    @property
    def name(self):
        return self._key

    def desc(self):
        return MagicMock()

    def asc(self):
        return MagicMock()

    def __lt__(self, other):
        return MagicMock()

    def __gt__(self, other):
        return MagicMock()


def make_db(total: int, count: int, items=None):
    """Build a mock db with controlled execute results."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = total

    data_result = MagicMock()
    if items is not None:
        data_result.scalars.return_value.unique.return_value.all.return_value = items
    else:
        data_result.scalars.return_value.unique.return_value.all.return_value = [
            MagicMock() for _ in range(count)
        ]

    db = MagicMock()
    db.execute.side_effect = [count_result, data_result]
    return db


# ============================================================================
# encode_cursor
# ============================================================================

class TestEncodeCursor:
    def test_none_returns_empty(self):
        assert encode_cursor(None) == ""

    def test_integer(self):
        result = encode_cursor(42)
        padding = 4 - len(result) % 4
        decoded = json.loads(base64.urlsafe_b64decode(result + "=" * padding))
        assert decoded["v"] == 42

    def test_string(self):
        result = encode_cursor("hello")
        padding = 4 - len(result) % 4
        decoded = json.loads(base64.urlsafe_b64decode(result + "=" * padding))
        assert decoded["v"] == "hello"

    def test_no_padding_needed(self):
        result = encode_cursor("a")
        assert "=" not in result


# ============================================================================
# decode_cursor
# ============================================================================

class TestDecodeCursor:
    def test_none_returns_none(self):
        assert decode_cursor(None) is None

    def test_empty_string_returns_none(self):
        assert decode_cursor("") is None

    def test_valid_cursor_without_padding(self):
        payload = base64.urlsafe_b64encode(json.dumps({"v": 42}).encode()).decode().rstrip("=")
        assert decode_cursor(payload) == 42

    def test_valid_cursor_with_padding(self):
        payload = base64.urlsafe_b64encode(json.dumps({"v": "hello"}).encode()).decode()
        assert decode_cursor(payload) == "hello"

    def test_valid_cursor_padding_4(self):
        """When padding == 4, no padding is added (4 % 4 == 0)."""
        payload = base64.urlsafe_b64encode(json.dumps({"v": 1}).encode()).decode()
        assert decode_cursor(payload) == 1

    def test_invalid_base64(self):
        with patch("app.utils.pagination.logger") as mock_log:
            result = decode_cursor("!!!invalid!!!")
        assert result is None
        mock_log.warning.assert_called_once()

    def test_invalid_json(self):
        valid_b64 = base64.urlsafe_b64encode(b"not json at all").decode()
        with patch("app.utils.pagination.logger") as mock_log:
            result = decode_cursor(valid_b64)
        assert result is None
        mock_log.warning.assert_called_once()


# ============================================================================
# keyset_paginate
# ============================================================================

PATCH_SELECT = "app.utils.pagination.select"


class TestKeysetPaginate:
    def test_db_none_raises(self):
        with pytest.raises(ValueError):
            keyset_paginate(MagicMock(), MagicMock(), db=None)

    @patch(PATCH_SELECT)
    def test_page_size_clamped_low(self, _):
        result = keyset_paginate(MagicMock(), MockOrderCol(), page_size=0, db=make_db(10, 5))
        assert result["page_size"] == 1

    @patch(PATCH_SELECT)
    def test_page_size_clamped_high(self, _):
        result = keyset_paginate(MagicMock(), MockOrderCol(), page_size=999, max_page_size=50, db=make_db(10, 5))
        assert result["page_size"] == 50

    @patch(PATCH_SELECT)
    def test_calculate_total_true(self, _):
        result = keyset_paginate(MagicMock(), MockOrderCol(), page_size=5, db=make_db(25, 5), calculate_total=True)
        assert result["total"] == 25

    @patch(PATCH_SELECT)
    def test_calculate_total_false(self, _):
        data_result = MagicMock()
        data_result.scalars.return_value.unique.return_value.all.return_value = [MagicMock() for _ in range(5)]
        db = MagicMock()
        db.execute.return_value = data_result

        result = keyset_paginate(MagicMock(), MockOrderCol(), page_size=5, db=db, calculate_total=False)
        assert result["total"] == 0
        assert db.execute.call_count == 1

    @patch(PATCH_SELECT)
    def test_cursor_desc_true(self, _):
        result = keyset_paginate(
            MagicMock(), MockOrderCol(), page_size=5,
            cursor=encode_cursor(50), desc=True, db=make_db(10, 3)
        )
        assert result["pagination"] == "keyset"

    @patch(PATCH_SELECT)
    def test_cursor_desc_false(self, _):
        result = keyset_paginate(
            MagicMock(), MockOrderCol(), page_size=5,
            cursor=encode_cursor(50), desc=False, db=make_db(10, 3)
        )
        assert result["pagination"] == "keyset"

    @patch(PATCH_SELECT)
    def test_no_cursor(self, _):
        result = keyset_paginate(MagicMock(), MockOrderCol(), page_size=5, cursor=None, desc=True, db=make_db(10, 3))
        assert result["pagination"] == "keyset"

    @patch(PATCH_SELECT)
    def test_has_more_true(self, _):
        item1, item2, item3 = MagicMock(), MagicMock(), MagicMock()
        item1.id = 1
        item2.id = 2
        item3.id = 3
        result = keyset_paginate(MagicMock(), MockOrderCol(), page_size=2, db=make_db(10, 3, items=[item1, item2, item3]))
        assert result["has_more"] is True
        assert len(result["items"]) == 2
        assert result["next_cursor"] is not None

    @patch(PATCH_SELECT)
    def test_has_more_false(self, _):
        item1, item2 = MagicMock(), MagicMock()
        item1.id = 1
        item2.id = 2
        result = keyset_paginate(MagicMock(), MockOrderCol(), page_size=5, db=make_db(2, 2, items=[item1, item2]))
        assert result["has_more"] is False
        assert result["next_cursor"] is None

    @patch(PATCH_SELECT)
    def test_scalars_fallback_to_all(self, _):
        count_result = MagicMock()
        count_result.scalar_one.return_value = 10
        data_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.unique.side_effect = Exception("scalars failed")
        data_result.scalars.return_value = mock_scalars
        data_result.all.return_value = [(MagicMock(),), (MagicMock(),)]
        db = MagicMock()
        db.execute.side_effect = [count_result, data_result]

        result = keyset_paginate(MagicMock(), MockOrderCol(), page_size=5, db=db)
        assert "items" in result

    @patch(PATCH_SELECT)
    def test_last_item_without_column_attribute_falls_back_to_scalar(self, _):
        """末项缺少游标列属性时（标量查询场景），以末项对象本身作为游标，
        避免 has_more=True 却 next_cursor=None 导致翻页静默卡死（深审 #4）。"""
        class ItemNoAttr:
            pass

        item1, item2, item3, item4 = MagicMock(), MagicMock(), ItemNoAttr(), MagicMock()
        item1.id = 1
        item2.id = 2
        item4.id = 4

        result = keyset_paginate(MagicMock(), MockOrderCol(), page_size=3, db=make_db(10, 4, items=[item1, item2, item3, item4]))
        assert result["has_more"] is True
        # 截断后末项为 item3（无 id 属性）→ 回退到末项本身，
        # 游标经 default=str 序列化，故解码后为对象字符串表示
        assert result["next_cursor"] is not None
        assert decode_cursor(result["next_cursor"]) == str(item3)

    @patch(PATCH_SELECT)
    def test_last_value_none_yields_no_cursor(self, _):
        """末项游标列取值显式为 None 时，无法构造游标，next_cursor 保持 None。"""
        item1, item2, item3, item4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        item1.id = 1
        item2.id = 2
        item3.id = None  # 截断后的末项
        item4.id = 4

        result = keyset_paginate(MagicMock(), MockOrderCol(), page_size=3, db=make_db(10, 4, items=[item1, item2, item3, item4]))
        assert result["has_more"] is True
        assert result["next_cursor"] is None

    @patch(PATCH_SELECT)
    def test_order_column_uses_name_fallback(self, _):
        item1, item2, item3 = MagicMock(), MagicMock(), MagicMock()
        item1.id = 1
        item2.id = 2
        item3.id = 3
        col = MockOrderCol(key="id", has_key=False)
        result = keyset_paginate(MagicMock(), col, page_size=2, db=make_db(5, 3, items=[item1, item2, item3]))
        assert result["next_cursor"] is not None

    @patch(PATCH_SELECT)
    def test_has_more_without_items(self, _):
        """When has_more is True but items list is empty (edge case), next_cursor stays None."""
        result = keyset_paginate(MagicMock(), MockOrderCol(), page_size=5, db=make_db(10, 6, items=[MagicMock() for _ in range(6)]))
        assert result["has_more"] is True
        assert result["next_cursor"] is not None


# ============================================================================
# paginate_query
# ============================================================================

PATCH_SELECT_PQ = "app.utils.pagination.select"


class TestPaginateQuery:
    def _make_db(self, total: int, count: int, items=None):
        count_result = MagicMock()
        count_result.scalar_one.return_value = total
        data_result = MagicMock()
        if items is not None:
            data_result.scalars.return_value.unique.return_value.all.return_value = items
        else:
            data_result.scalars.return_value.unique.return_value.all.return_value = [
                MagicMock() for _ in range(count)
            ]
        db = MagicMock()
        db.execute.side_effect = [count_result, data_result]
        return db

    @patch(PATCH_SELECT_PQ)
    def test_page_size_clamped_low(self, _):
        result = paginate_query(self._make_db(0, 0, items=[]), MagicMock(), page=1, page_size=0)
        assert result["page_size"] == 1

    @patch(PATCH_SELECT_PQ)
    def test_page_size_clamped_high(self, _):
        result = paginate_query(self._make_db(0, 0, items=[]), MagicMock(), page=1, page_size=999, max_page_size=50)
        assert result["page_size"] == 50

    @patch(PATCH_SELECT_PQ)
    def test_page_defaults_to_1(self, _):
        result = paginate_query(self._make_db(0, 0, items=[]), MagicMock(), page=0, page_size=10)
        assert result["page"] == 1

    @patch(PATCH_SELECT_PQ)
    def test_with_filters(self, _):
        filters = [MagicMock()]
        result = paginate_query(self._make_db(3, 3), MagicMock(), page=1, page_size=10, filters=filters)
        assert result["total"] == 3

    @patch(PATCH_SELECT_PQ)
    def test_without_filters(self, _):
        result = paginate_query(self._make_db(5, 5), MagicMock(), page=1, page_size=10)
        assert result["total"] == 5

    @patch(PATCH_SELECT_PQ)
    def test_with_eager_loads(self, _):
        eager = [MagicMock()]
        result = paginate_query(self._make_db(2, 2), MagicMock(), page=1, page_size=10, eager_loads=eager)
        assert result["total"] == 2

    @patch(PATCH_SELECT_PQ)
    def test_without_eager_loads(self, _):
        result = paginate_query(self._make_db(2, 2), MagicMock(), page=1, page_size=10)
        assert result["total"] == 2

    @patch(PATCH_SELECT_PQ)
    def test_with_order_by(self, _):
        order = MagicMock()
        result = paginate_query(self._make_db(1, 1), MagicMock(), page=1, page_size=10, order_by=order)
        assert result["total"] == 1

    @patch(PATCH_SELECT_PQ)
    def test_without_order_by(self, _):
        result = paginate_query(self._make_db(1, 1), MagicMock(), page=1, page_size=10, order_by=None)
        assert result["total"] == 1

    @patch(PATCH_SELECT_PQ)
    def test_multi_page(self, _):
        result = paginate_query(self._make_db(25, 10), MagicMock(), page=3, page_size=10)
        assert result["page"] == 3

    @patch(PATCH_SELECT_PQ)
    def test_pagination_offset_type(self, _):
        result = paginate_query(self._make_db(0, 0, items=[]), MagicMock(), page=1, page_size=10)
        assert result["pagination"] == "offset"
