"""R28 回归锁定：`DataPackage.data_types` 不得双重编码。

R28 探针实测：`POST /data-packages/export` 把 `json.dumps(data_types)` 写进
**JSON 列** `data_types` —— 落库的是 JSON *字符串*，读出来是
`'["villages", "projects", …]'`。后果：

- `POST /data-packages/{id}/versions` 生成的版本变更摘要按可迭代对象遍历该字符串，
  于是 `changes` 的键变成 **单个字符**：`{"[": {...}, "\\"": {...}, "v": {...}, …}`
  （探针响应里可直接看到）；
- 任何把 `data_types` 当数组消费的地方（接收记录、数据上报包摘要）拿到的是字符串。

修复：JSON 列直接存列表（导出/导入两条写入路径），并在读取侧加
`_normalize_data_types` 归一历史双重编码行。
"""

import json

import pytest

from app.api.v1.data.data.data_packages import _normalize_data_types, _package_version_changes
from app.models.data_package import DataPackage


class TestNormalizeDataTypes:
    def test_native_list(self):
        assert _normalize_data_types(["villages", "funds"]) == ["villages", "funds"]

    def test_tuple(self):
        assert _normalize_data_types(("villages",)) == ["villages"]

    def test_legacy_json_string(self):
        assert _normalize_data_types('["villages", "projects"]') == ["villages", "projects"]

    def test_unparseable_string_falls_back_to_single_item(self):
        assert _normalize_data_types("villages") == ["villages"]

    def test_json_string_scalar(self):
        assert _normalize_data_types('"villages"') == ["villages"]

    def test_non_sequence_returns_empty(self):
        assert _normalize_data_types(None) == []
        assert _normalize_data_types(123) == []

    def test_items_coerced_to_str(self):
        assert _normalize_data_types([1, "funds"]) == ["1", "funds"]


class TestPackageVersionChanges:
    def test_native_list_keys_are_type_names(self):
        package = DataPackage(id=1, data_types=["villages", "funds"])
        changes = _package_version_changes(package)
        assert set(changes) == {"villages", "funds"}
        assert changes["villages"] == {"added": [], "modified": [], "deleted": []}

    def test_legacy_double_encoded_string_not_iterated_char_by_char(self):
        """修复前这里会产出 `{`、`[`、`"`、`v`… 这类单字符键。"""
        package = DataPackage(id=2, data_types=json.dumps(["villages", "funds"]))
        changes = _package_version_changes(package)
        assert set(changes) == {"villages", "funds"}
        assert all(len(k) > 1 for k in changes)

    def test_empty_falls_back_to_default_types(self):
        package = DataPackage(id=3, data_types=None)
        assert set(_package_version_changes(package)) == {"villages", "projects", "funds", "schools"}


class TestColumnRoundTrip:
    """JSON 列存列表 → 读回仍是列表（不再双重编码）。"""

    def test_list_round_trip(self, real_db_session):
        pkg = DataPackage(
            package_code="R28-LIST", org_id=1, file_path="/tmp/x.zip", file_name="x.zip",
            file_size=10, data_types=["villages", "schools"], record_count=0,
        )
        real_db_session.add(pkg)
        real_db_session.commit()
        real_db_session.expire_all()
        got = real_db_session.query(DataPackage).filter(DataPackage.id == pkg.id).first()
        assert got.data_types == ["villages", "schools"]

    def test_legacy_string_row_is_normalized_on_read(self, real_db_session):
        pkg = DataPackage(
            package_code="R28-LEGACY", org_id=1, file_path="/tmp/y.zip", file_name="y.zip",
            file_size=10, data_types=json.dumps(["villages"]), record_count=0,
        )
        real_db_session.add(pkg)
        real_db_session.commit()
        real_db_session.expire_all()
        got = real_db_session.query(DataPackage).filter(DataPackage.id == pkg.id).first()
        # 历史行读回是字符串，归一后必须是列表
        assert isinstance(got.data_types, str)
        assert _normalize_data_types(got.data_types) == ["villages"]
        assert set(_package_version_changes(got)) == {"villages"}


class TestExportServiceStoresList:
    """导出/导入两条写入路径都必须直接传列表（不再 json.dumps）。"""

    def test_export_package_passes_list_to_model(self):
        import inspect

        from app.services import data_package_service as mod

        src = inspect.getsource(mod.DataPackageService.export_package)
        assert "data_types=json.dumps(" not in src
        assert "data_types=data_types," in src

    def test_import_path_passes_list_to_model(self):
        import inspect

        from app.services import data_package_service as mod

        src = inspect.getsource(mod.DataPackageService.import_package)
        assert "data_types=json.dumps(" not in src
        assert "data_types=validation.manifest.data_types," in src
