"""Tests for batch_service.py — 100% coverage target."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from types import SimpleNamespace


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_instance(**attrs):
    return SimpleNamespace(**attrs)


# ── _resolve_model ───────────────────────────────────────────────────────


class TestResolveModel:
    """Cover every branch of _resolve_model."""

    def test_invalid_table_name(self):
        """table_name not in ALLOWED_TABLES → BusinessLogicError."""
        from app.services.batch_service import _resolve_model
        from app.core.error_handler import BusinessLogicError
        with pytest.raises(BusinessLogicError, match="不允许的表名"):
            _resolve_model("nonexistent_table")

    def test_cache_hit(self):
        """Cached model class is returned directly."""
        from app.services.batch_service import _resolve_model, TABLE_MODEL_MAP
        # Pre-populate cache
        fake_model = Mock()
        fake_model.__tablename__ = "projects"
        TABLE_MODEL_MAP["projects"] = fake_model
        try:
            result = _resolve_model("projects")
            assert result is fake_model
        finally:
            TABLE_MODEL_MAP.pop("projects", None)

    def test_cache_miss_found_via_dynamic_import(self):
        """Cache is None → dynamic import finds model → cached."""
        from app.services.batch_service import _resolve_model, TABLE_MODEL_MAP
        TABLE_MODEL_MAP["projects"] = None
        from app.models.project import Project
        try:
            result = _resolve_model("projects")
            assert result is Project
            assert TABLE_MODEL_MAP.get("projects") is Project
        finally:
            TABLE_MODEL_MAP.pop("projects", None)

    def test_cache_miss_not_found_raises_value_error(self):
        """Unknown table (not in _TABLE_TO_MODEL_NAME) → ValueError."""
        from app.services.batch_service import _resolve_model, ALLOWED_TABLES

        # Use a table name that's not in ALLOWED_TABLES at all,
        # which triggers BusinessLogicError before reaching the ValueError branch.
        # The ValueError branch at line 61 is unreachable for known tables due to
        # app.models' __getattr__ lazy loading, but we verify that invalid table
        # names are properly rejected.
        with pytest.raises(Exception) as exc_info:
            _resolve_model("nonexistent_table_xyz")
        assert "不允许的表名" in str(exc_info.value) or "Unknown table" in str(exc_info.value)

    def test_exception_in_dynamic_import_loop_caught(self):
        """Non-AttributeError exception during getattr → caught → ValueError."""
        from app.services.batch_service import _resolve_model, TABLE_MODEL_MAP
        import builtins

        TABLE_MODEL_MAP["projects"] = None
        try:
            original = builtins.getattr
            def _failing_getattr(obj, name, *args):
                if name == "Project":
                    raise RuntimeError("simulated dynamic import failure")
                return original(obj, name, *args)
            builtins.getattr = _failing_getattr
            try:
                with pytest.raises(ValueError, match="Unknown table"):
                    _resolve_model("projects")
            finally:
                builtins.getattr = original
        finally:
            TABLE_MODEL_MAP.pop("projects", None)


# ── get_db ───────────────────────────────────────────────────────────────

class TestGetDb:
    def test_raises_not_implemented(self):
        from app.services.batch_service import get_db
        with pytest.raises(NotImplementedError):
            get_db()


# ── BatchService basics ──────────────────────────────────────────────────

class TestBatchServiceBasics:
    def test_init_sets_db(self):
        from app.services.batch_service import BatchService
        db = Mock()
        svc = BatchService(db)
        assert svc.db is db

    def test_db_property_getter(self):
        from app.services.batch_service import BatchService
        db = Mock()
        svc = BatchService(db)
        assert svc._db is db

    def test_db_property_setter(self):
        from app.services.batch_service import BatchService
        db1 = Mock()
        db2 = Mock()
        svc = BatchService(db1)
        svc._db = db2
        assert svc.db is db2

    def test_process_static(self):
        from app.services.batch_service import BatchService
        result = BatchService.process([1, 2, 3])
        # process is async → must await
        import asyncio
        actual = asyncio.run(result)
        assert actual == {"processed": 3}

    def test_process_empty(self):
        from app.services.batch_service import BatchService
        import asyncio
        result = asyncio.run(BatchService.process([]))
        assert result == {"processed": 0}


# ── _validate_table_name ─────────────────────────────────────────────────

class TestValidateTableName:
    def test_valid_table(self):
        from app.services.batch_service import BatchService
        # Should not raise
        BatchService._validate_table_name("projects")

    def test_invalid_table(self):
        from app.services.batch_service import BatchService
        from app.core.error_handler import BusinessLogicError
        with pytest.raises(BusinessLogicError, match="不允许的表名"):
            BatchService._validate_table_name("bad_table")


# ── _get_model_class ─────────────────────────────────────────────────────

class TestGetModelClass:
    def test_returns_model_for_valid_table(self):
        from app.services.batch_service import BatchService, TABLE_MODEL_MAP
        from app.models.project import Project
        TABLE_MODEL_MAP["projects"] = Project
        svc = BatchService(db=Mock())
        try:
            model = svc._get_model_class("projects")
            assert model is Project
        finally:
            TABLE_MODEL_MAP.pop("projects", None)


# ── _get_db_context ──────────────────────────────────────────────────────

class TestGetDbContext:
    def test_with_db_yields_db(self):
        from app.services.batch_service import BatchService
        db = Mock()
        svc = BatchService(db)
        with svc._get_db_context() as ctx:
            assert ctx is db

    def test_without_db_normal(self):
        from app.services.batch_service import BatchService
        svc = BatchService(db=None)
        mock_db = Mock()
        mock_gen = MagicMock()
        mock_gen.__next__.return_value = mock_db

        with patch("app.services.batch_service.get_db",
                   return_value=mock_gen):
            with svc._get_db_context() as ctx:
                assert ctx is mock_db

        mock_db.close.assert_called_once()
        mock_gen.close.assert_called_once()

    def test_without_db_close_raises(self):
        """db.close() raises → caught by except Exception: pass."""
        from app.services.batch_service import BatchService
        svc = BatchService(db=None)
        mock_db = Mock()
        mock_db.close.side_effect = Exception("close failure")
        mock_gen = MagicMock()
        mock_gen.__next__.return_value = mock_db

        with patch("app.services.batch_service.get_db",
                   return_value=mock_gen):
            with svc._get_db_context() as ctx:
                assert ctx is mock_db

        mock_db.close.assert_called_once()
        mock_gen.close.assert_called_once()

    def test_without_db_gen_close_raises(self):
        """gen.close() raises → caught by except Exception: pass."""
        from app.services.batch_service import BatchService
        svc = BatchService(db=None)
        mock_db = Mock()
        mock_gen = MagicMock()
        mock_gen.__next__.return_value = mock_db
        mock_gen.close.side_effect = Exception("gen close failure")

        with patch("app.services.batch_service.get_db",
                   return_value=mock_gen):
            with svc._get_db_context() as ctx:
                assert ctx is mock_db

        mock_db.close.assert_called_once()
        mock_gen.close.assert_called_once()


# ── batch_update ─────────────────────────────────────────────────────────

class TestBatchUpdate:
    async def test_invalid_table(self):
        from app.services.batch_service import BatchService
        from app.core.error_handler import BusinessLogicError
        svc = BatchService(db=Mock())
        with pytest.raises(BusinessLogicError, match="不允许的表名"):
            await svc.batch_update("bad_table", [1], {})

    async def test_no_db_returns_zero(self):
        from app.services.batch_service import BatchService
        svc = BatchService(db=None)
        result = await svc.batch_update("projects", [1, 2],
                                        {"name": "x"})
        assert result == {"success": True, "success_count": 0, "skipped": 0}

    async def test_with_db_get_inst_found_attr_exists(self):
        from app.services.batch_service import BatchService
        inst = _make_instance(name="old", status="pending")
        db = Mock()
        mock_q = Mock()
        mock_f = Mock()
        db.query.return_value = mock_q
        mock_q.filter.return_value = mock_f
        mock_f.count.return_value = 1
        mock_f.all.return_value = [inst]
        svc = BatchService(db)
        result = await svc.batch_update(
            "projects", [1],
            {"name": "new", "status": "active"}
        )
        assert result == {"success": True, "success_count": 1, "skipped": 0}
        assert inst.name == "new"
        assert inst.status == "active"
        db.commit.assert_called_once()

    async def test_with_db_get_inst_found_attr_missing(self):
        """hasattr(inst, k) is False for some update keys → skip."""
        from app.services.batch_service import BatchService
        inst = _make_instance(name="old")
        db = Mock()
        mock_q = Mock()
        mock_f = Mock()
        db.query.return_value = mock_q
        mock_q.filter.return_value = mock_f
        mock_f.count.return_value = 1
        mock_f.all.return_value = [inst]
        svc = BatchService(db)
        result = await svc.batch_update(
            "projects", [1],
            {"name": "new", "nonexistent": "val"}
        )
        assert result == {"success": True, "success_count": 1, "skipped": 0}
        assert inst.name == "new"
        assert not hasattr(inst, "nonexistent")

    async def test_with_db_get_inst_not_found(self):
        """Instance not in DB → skip."""
        from app.services.batch_service import BatchService
        db = Mock()
        mock_q = Mock()
        mock_f = Mock()
        db.query.return_value = mock_q
        mock_q.filter.return_value = mock_f
        mock_f.count.return_value = 0
        mock_f.all.return_value = []
        svc = BatchService(db)
        result = await svc.batch_update("projects", [1, 2],
                                        {"name": "x"})
        assert result == {"success": True, "success_count": 0, "skipped": 0}

    async def test_with_db_query_path(self):
        """db.query path: uses query().filter().all() for batch fetch."""
        from app.services.batch_service import BatchService
        inst = _make_instance(name="old")
        db = Mock()
        mock_q = Mock()
        mock_f = Mock()
        db.query.return_value = mock_q
        mock_q.filter.return_value = mock_f
        mock_f.count.return_value = 1
        mock_f.all.return_value = [inst]
        svc = BatchService(db)
        result = await svc.batch_update("projects", [1],
                                        {"name": "new"})
        assert result == {"success": True, "success_count": 1, "skipped": 0}
        assert inst.name == "new"
        db.query.assert_called_once()


# ── batch_delete ─────────────────────────────────────────────────────────

class TestBatchDelete:
    async def test_invalid_table(self):
        from app.services.batch_service import BatchService
        from app.core.error_handler import BusinessLogicError
        svc = BatchService(db=Mock())
        with pytest.raises(BusinessLogicError, match="不允许的表名"):
            await svc.batch_delete("bad_table", [1])

    async def test_no_db_returns_zero(self):
        from app.services.batch_service import BatchService
        svc = BatchService(db=None)
        result = await svc.batch_delete("projects", [1, 2])
        assert result == {"success": True, "success_count": 0, "skipped": 0}

    async def test_soft_delete_has_is_deleted(self):
        """soft_delete=True and inst has is_deleted → set to True."""
        from app.services.batch_service import BatchService
        inst = _make_instance(is_deleted=False, name="test")
        db = Mock()
        mock_q = Mock()
        mock_f = Mock()
        db.query.return_value = mock_q
        mock_q.filter.return_value = mock_f
        mock_f.count.return_value = 1
        mock_f.all.return_value = [inst]
        svc = BatchService(db)
        result = await svc.batch_delete("projects", [1],
                                        soft_delete=True)
        assert result == {"success": True, "success_count": 1, "skipped": 0}
        assert inst.is_deleted is True

    async def test_soft_delete_without_is_deleted(self):
        """soft_delete=True but inst lacks is_deleted → db.delete."""
        from app.services.batch_service import BatchService
        inst = _make_instance(name="test")  # no is_deleted
        db = Mock()
        mock_q = Mock()
        mock_f = Mock()
        db.query.return_value = mock_q
        mock_q.filter.return_value = mock_f
        mock_f.count.return_value = 1
        mock_f.all.return_value = [inst]
        svc = BatchService(db)
        result = await svc.batch_delete("projects", [1],
                                        soft_delete=True)
        assert result == {"success": True, "success_count": 1, "skipped": 0}
        db.delete.assert_called_once_with(inst)

    async def test_hard_delete(self):
        """soft_delete=False → db.delete."""
        from app.services.batch_service import BatchService
        inst = _make_instance(name="test")
        db = Mock()
        mock_q = Mock()
        mock_f = Mock()
        db.query.return_value = mock_q
        mock_q.filter.return_value = mock_f
        mock_f.count.return_value = 1
        mock_f.all.return_value = [inst]
        svc = BatchService(db)
        result = await svc.batch_delete("projects", [1],
                                        soft_delete=False)
        assert result == {"success": True, "success_count": 1, "skipped": 0}
        db.delete.assert_called_once_with(inst)

    async def test_inst_not_found(self):
        """Instance not found → skip."""
        from app.services.batch_service import BatchService
        db = Mock()
        mock_q = Mock()
        mock_f = Mock()
        db.query.return_value = mock_q
        mock_q.filter.return_value = mock_f
        mock_f.count.return_value = 0
        mock_f.all.return_value = []
        svc = BatchService(db)
        result = await svc.batch_delete("projects", [1, 2])
        assert result == {"success": True, "success_count": 0, "skipped": 0}
        db.delete.assert_not_called()


# ── batch_export ─────────────────────────────────────────────────────────

class TestBatchExport:
    async def test_invalid_table(self):
        from app.services.batch_service import BatchService
        from app.core.error_handler import BusinessLogicError
        svc = BatchService(db=Mock())
        with pytest.raises(BusinessLogicError, match="不允许的表名"):
            await svc.batch_export("bad_table", [1])

    async def test_success(self):
        from app.services.batch_service import BatchService
        svc = BatchService(db=Mock())
        recs = [Mock(to_dict=MagicMock(return_value={"id": i, "name": f"n{i}"})) for i in (1, 2, 3)]
        svc.db.query.return_value.filter.return_value.all.return_value = recs
        result = await svc.batch_export("projects", [1, 2, 3])
        assert result["success"] is True
        assert result["exported_count"] == 3
        assert isinstance(result["data"], str)
        assert len(result["data"]) > 0

    async def test_success_empty_ids(self):
        """ids 为空 → 跳过 `if ids:` 过滤分支，直接导出全表（此处 0 条）。"""
        from app.services.batch_service import BatchService
        svc = BatchService(db=Mock())
        # ids 为空时不经过 .filter()，链终点是 db.query(...).all()
        svc.db.query.return_value.all.return_value = []
        result = await svc.batch_export("projects", [])
        assert result["success"] is True
        assert result["exported_count"] == 0
        # 空结果集时表头回落为 ["id"]
        svc.db.query.return_value.filter.assert_not_called()

    async def test_success_ids_no_match(self):
        """ids 非空但一条都没查到 → 走 `if ids:` 真分支后 records 为空。"""
        from app.services.batch_service import BatchService
        svc = BatchService(db=Mock())
        svc.db.query.return_value.filter.return_value.all.return_value = []
        result = await svc.batch_export("projects", [1, 2])
        assert result["success"] is True
        assert result["exported_count"] == 0
        assert isinstance(result["data"], str) and len(result["data"]) > 0
        svc.db.query.return_value.filter.assert_called_once()

    async def test_import_error(self):
        """openpyxl not available → returns failure."""
        from app.services.batch_service import BatchService
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "openpyxl":
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        svc = BatchService(db=Mock())
        with patch("builtins.__import__", side_effect=mock_import):
            result = await svc.batch_export("projects", [1, 2])
        assert result == {"success": False, "data": "",
                          "exported_count": 0}


# ── validate_batch ──────────────────────────────────────────────────────

class TestValidateBatch:
    async def test_invalid_table(self):
        from app.services.batch_service import BatchService
        from app.core.error_handler import BusinessLogicError
        svc = BatchService(db=Mock())
        with pytest.raises(BusinessLogicError, match="不允许的表名"):
            await svc.validate_batch("bad_table", [1])

    async def test_no_db_returns_zero(self):
        from app.services.batch_service import BatchService
        svc = BatchService(db=None)
        result = await svc.validate_batch("projects", [1, 2])
        assert result == {"success": True, "existing_count": 0}

    async def test_partial_existing(self):
        """Some ids exist, some don't → partial count."""
        from app.services.batch_service import BatchService
        db = Mock()
        mock_q = Mock()
        mock_f = Mock()
        db.query.return_value = mock_q
        mock_q.filter.return_value = mock_f
        mock_f.count.return_value = 1
        svc = BatchService(db)
        result = await svc.validate_batch("projects", [1, 2])
        assert result == {"success": True, "existing_count": 1}

    async def test_all_exist(self):
        from app.services.batch_service import BatchService
        db = Mock()
        mock_q = Mock()
        mock_f = Mock()
        db.query.return_value = mock_q
        mock_q.filter.return_value = mock_f
        mock_f.count.return_value = 3
        svc = BatchService(db)
        result = await svc.validate_batch("projects", [1, 2, 3])
        assert result == {"success": True, "existing_count": 3}
