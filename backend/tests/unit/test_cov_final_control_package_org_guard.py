"""app.api.v1.control_package 覆盖补全（R30 守卫批次）。

覆盖两行：
- line 177 —— 导出时 system_config_data 非空才写入 system_config.json 成员
  （白名单键有值；空字典时整段跳过）。
- line 291 —— _resolve_package_target_org 对**不受信**上传清单里的
  target_organization_id 做类型/范围校验（缺失、布尔、非正整数一律 400），
  缺此校验可被编辑过的包把策略写到任意其它组织（跨组织写）。
"""

import io
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.control_package import (
    GenerateControlPackageRequest,
    _resolve_package_target_org,
    generate_control_package,
    import_control_package,
)
from app.models.org_module_policy import OrgModulePolicy
from app.models.system_config import SystemConfig


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _zip_bytes(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in files.items():
            zf.writestr(name, payload)
    return buf.getvalue()


def _super_admin():
    return SimpleNamespace(
        id=1, username="admin", role="super_admin", is_superuser=True,
        is_active=True, organization_id=1,
    )


def _org_admin():
    """部门级 admin：is_admin 放行，但非超管（组织可达性守卫会真实生效）。"""
    return SimpleNamespace(
        id=2, username="dept", role="admin", is_superuser=False,
        is_active=True, organization_id=2,
    )


def _generate_db(config_rows):
    """按模型分派查询：仅 SystemConfig 返回白名单配置行。"""
    db = MagicMock(name="db")
    issued = {}

    def _query(model):
        q = MagicMock(name="query[%s]" % getattr(model, "__name__", model))
        q.filter.return_value = q
        q.all.return_value = list(config_rows) if model is SystemConfig else []
        q.first.return_value = None
        issued[getattr(model, "__name__", str(model))] = q
        return q

    db.query.side_effect = _query
    db.issued_queries = issued
    return db


async def _read_streaming_body(response) -> bytes:
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    return b"".join(chunks)


# ---------------------------------------------------------------------------
# line 177 —— 白名单系统配置有值 → 打包 system_config.json
# ---------------------------------------------------------------------------

class TestGeneratePackageSystemConfigMember:
    async def test_whitelisted_config_is_written_into_package(self):
        """白名单键有值 → 包内出现 system_config.json 且内容为该键值对（line 177）。"""
        db = _generate_db([SimpleNamespace(key="system_name", value="某某帮扶单位")])
        req = GenerateControlPackageRequest(
            organization_id=1, include_users=False, include_system_config=True,
        )

        with patch("app.api.v1.control_package.write_work_log") as work_log:
            resp = generate_control_package(body=req, db=db, current_user=_super_admin())

        content = await _read_streaming_body(resp)

        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = zf.namelist()
            assert "manifest.json" in names
            assert "system_config.json" in names
            assert json.loads(zf.read("system_config.json")) == {"system_name": "某某帮扶单位"}
            # 未勾选用户 → 不产生 users.json（对照：打包是按内容条件写入的）
            assert "users.json" not in names
            manifest = json.loads(zf.read("manifest.json"))
            assert manifest["contents"]["system_config"] == 1

        work_log.assert_called_once()
        # 导出走白名单 in_ 过滤（一次 filter），绝不整表导出；
        # 未勾选用户时不查 User 表。
        assert db.issued_queries[SystemConfig.__name__].filter.call_count == 1
        assert "User" not in db.issued_queries
        assert db.issued_queries[OrgModulePolicy.__name__].all.call_count == 1


# ---------------------------------------------------------------------------
# line 291 —— 目标组织 id 校验（不受信清单）
# ---------------------------------------------------------------------------

class TestResolvePackageTargetOrgGuard:
    @pytest.mark.parametrize(
        "bad_value, manifest",
        [
            ("missing", {}),
            ("string", {"target_organization_id": "1"}),
            ("bool", {"target_organization_id": True}),
            ("zero", {"target_organization_id": 0}),
            ("negative", {"target_organization_id": -7}),
            ("float", {"target_organization_id": 1.5}),
            ("null", {"target_organization_id": None}),
            ("list", {"target_organization_id": [1]}),
        ],
    )
    def test_invalid_target_org_id_is_rejected_with_400(self, bad_value, manifest):
        """非法/缺失 target_organization_id 一律 400（line 291），不得落到任何组织上。"""
        db = MagicMock(name="db")
        with pytest.raises(HTTPException) as excinfo:
            _resolve_package_target_org(db, manifest, _org_admin())

        assert excinfo.value.status_code == 400
        assert "target_organization_id" in excinfo.value.detail
        # 校验失败必须早于任何组织可达性/写库动作
        db.query.assert_not_called()
        db.add.assert_not_called()


class TestImportPackageTargetOrgGuard:
    async def test_import_with_manifest_missing_target_org_is_400(self):
        """导入路径端到端：清单缺 target_organization_id → 400，且不写入任何策略。"""
        content = _zip_bytes({
            "manifest.json": json.dumps({"package_type": "control"}),
            "module_policy.json": json.dumps([
                {"module_key": "funds", "visibility": "visible", "edit_mode": "editable"},
            ]),
        })
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(return_value=content))
        db = MagicMock(name="db")

        with pytest.raises(HTTPException) as excinfo:
            await import_control_package(file=file, db=db, current_user=_org_admin())

        assert excinfo.value.status_code == 400
        assert "target_organization_id" in excinfo.value.detail
        db.add.assert_not_called()

    async def test_import_with_boolean_target_org_is_400(self):
        """True 能通过 isinstance(x, int)，必须被显式 bool 判断拦下（line 290-291）。"""
        content = _zip_bytes({
            "manifest.json": json.dumps({"package_type": "control", "target_organization_id": True}),
            "module_policy.json": json.dumps([]),
        })
        file = SimpleNamespace(filename="pkg.zip", read=AsyncMock(return_value=content))
        db = MagicMock(name="db")

        with pytest.raises(HTTPException) as excinfo:
            await import_control_package(file=file, db=db, current_user=_org_admin())

        assert excinfo.value.status_code == 400
        db.add.assert_not_called()
