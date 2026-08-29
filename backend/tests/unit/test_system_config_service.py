from unittest.mock import MagicMock, patch




class TestSystemConfigService:
    def test_init(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        assert svc.db is None
        svc2 = SystemConfigService(db=MagicMock())
        assert svc2.db is not None

    def test_get_no_db_with_default(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        result = svc.get("system_id")
        assert result == ""

    def test_get_no_db_without_default(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        result = svc.get("nonexistent", "fallback")
        assert result == "fallback"

    def test_get_no_db_nonexistent(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        assert svc.get("unknown") is None

    def test_get_with_db_found(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        config = MagicMock()
        config.value = "db_value"
        mock_db.query.return_value.filter.return_value.first.return_value = config
        svc = SystemConfigService(mock_db)
        assert svc.get("key") == "db_value"

    def test_get_with_db_not_found_in_defaults(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = SystemConfigService(mock_db)
        assert svc.get("system_id") == ""

    def test_get_with_db_not_found_no_default(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = SystemConfigService(mock_db)
        assert svc.get("unknown", "custom") == "custom"

    def test_get_int_none(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.get = MagicMock(return_value=None)
        assert svc.get_int("key") == 0

    def test_get_int_valid(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.get = MagicMock(return_value="42")
        assert svc.get_int("key") == 42

    def test_get_int_invalid(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.get = MagicMock(return_value="not_a_number")
        assert svc.get_int("key") == 0

    def test_get_bool_none(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.get = MagicMock(return_value=None)
        assert svc.get_bool("key") is False

    def test_get_bool_true_values(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        for val in ["true", "1", "yes", "on", "True"]:
            svc.get = MagicMock(return_value=val)
            assert svc.get_bool("key") is True, f"failed for {val}"

    def test_get_bool_false(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.get = MagicMock(return_value="false")
        assert svc.get_bool("key") is False

    def test_get_json_none(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.get = MagicMock(return_value=None)
        assert svc.get_json("key", {"default": True}) == {"default": True}

    def test_get_json_valid(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.get = MagicMock(return_value='{"a": 1}')
        assert svc.get_json("key") == {"a": 1}

    def test_get_json_invalid(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.get = MagicMock(return_value="not json")
        assert svc.get_json("key", "fallback") == "fallback"

    def test_set_no_db(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.set("key", "val")

    def test_set_new_bool_true(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = SystemConfigService(mock_db)
        svc.set("initialized", True)
        mock_db.add.assert_called_once()
        assert mock_db.add.call_args[0][0].value == "true"

    def test_set_new_bool_false(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = SystemConfigService(mock_db)
        svc.set("initialized", False)
        assert mock_db.add.call_args[0][0].value == "false"

    def test_set_new_dict(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = SystemConfigService(mock_db)
        svc.set("data", {"key": "val"})
        mock_db.add.assert_called_once()
        assert '"key"' in mock_db.add.call_args[0][0].value

    def test_set_new_list(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = SystemConfigService(mock_db)
        svc.set("items", [1, 2, 3])
        assert "1" in mock_db.add.call_args[0][0].value

    def test_set_new_str(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = SystemConfigService(mock_db)
        svc.set("key", "plain_value")
        assert mock_db.add.call_args[0][0].value == "plain_value"

    def test_set_existing(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        existing = MagicMock()
        existing.value = "old"
        existing.description = "old_desc"
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        svc = SystemConfigService(mock_db)
        svc.set("key", "new_value", "new_desc")
        assert existing.value == "new_value"
        assert existing.description == "new_desc"
        mock_db.add.assert_not_called()

    def test_set_existing_no_desc(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        existing = MagicMock()
        existing.value = "old"
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        svc = SystemConfigService(mock_db)
        svc.set("key", "new_value")
        assert existing.value == "new_value"

    def test_set_new_with_default_desc(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = SystemConfigService(mock_db)
        svc.set("system_id", "SYS-001")
        config = mock_db.add.call_args[0][0]
        assert config.description == "系统唯一标识"

    def test_get_all_no_db(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        result = svc.get_all()
        assert "system_id" in result

    def test_get_all_with_db(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        c1 = MagicMock()
        c1.key = "k1"
        c1.value = "v1"
        mock_db.query.return_value.all.return_value = [c1]
        svc = SystemConfigService(mock_db)
        result = svc.get_all()
        assert result == {"k1": "v1"}

    def test_initialize_defaults_no_db(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.initialize_defaults()

    def test_initialize_defaults_with_db(self):
        from app.services.system_config_service import SystemConfigService

        # 断言跟随 DEFAULT_CONFIGS 实际条目数：新增默认键时测试不必改号，
        # 语义为「每个默认键各 add 一次」
        expected = len(SystemConfigService.DEFAULT_CONFIGS)
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = SystemConfigService(mock_db)
        svc.initialize_defaults()
        assert mock_db.add.call_count == expected

    def test_initialize_defaults_skip_existing(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        existing = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        svc = SystemConfigService(mock_db)
        svc.initialize_defaults()
        mock_db.add.assert_not_called()

    def test_is_initialized_true(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.get_bool = MagicMock(return_value=True)
        assert svc.is_initialized() is True

    def test_is_initialized_false(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.get_bool = MagicMock(return_value=False)
        assert svc.is_initialized() is False

    def test_set_initialized(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        svc = SystemConfigService(mock_db)
        svc.set = MagicMock()
        svc.set_initialized(1)
        svc.set.assert_any_call("initialized", "true")
        svc.set.assert_any_call("organization_id", "1")
        assert svc.set.call_count == 3

    def test_set_initialized_with_system_id(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.set = MagicMock()
        svc.set_initialized(1, "SYS-CUSTOM")
        svc.set.assert_any_call("system_id", "SYS-CUSTOM")

    def test_delete_no_db(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        assert svc.delete("key") is False

    def test_delete_existing(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        existing = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        svc = SystemConfigService(mock_db)
        assert svc.delete("key") is True
        mock_db.delete.assert_called_once_with(existing)

    def test_delete_not_existing(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        svc = SystemConfigService(mock_db)
        assert svc.delete("key") is False

    def test_reload_with_db(self):
        from app.services.system_config_service import SystemConfigService
        mock_db = MagicMock()
        svc = SystemConfigService(mock_db)
        svc.reload()
        mock_db.expire_all.assert_called_once()

    def test_reload_no_db(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.reload()

    def test_export_config(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.get_all = MagicMock(return_value={"key": "val"})
        result = svc.export_config()
        assert '"key"' in result

    def test_import_config_valid(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        svc.set = MagicMock()
        result = svc.import_config('{"k1": "v1", "k2": "v2"}')
        assert result is True
        assert svc.set.call_count == 2

    def test_import_config_invalid(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        result = svc.import_config("not json")
        assert result is False

    def test_import_config_type_error(self):
        from app.services.system_config_service import SystemConfigService
        svc = SystemConfigService()
        with patch("json.loads", side_effect=TypeError("bad type")):
            result = svc.import_config("{}")
            assert result is False
