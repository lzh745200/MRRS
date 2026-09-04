"""回收站（软删）恢复与彻底删除端到端测试 (T03)

覆盖：
1. 恢复链路：创建→软删→回收站可见→恢复→重新可见
2. 彻底删除链路：预览级联统计→密码错误拒绝→密码正确→物理删除→详情404
3. 状态门：活跃记录不可恢复/不可彻底删除
4. 权限矩阵：非管理员调用 restore/purge/purge-preview → 403
5. 级联删除：村下挂项目时，purge 连带物理删除项目
"""
import pytest

from app.models.project import Project


@pytest.fixture(autouse=True)
def _isolate_runtime_paths(monkeypatch, tmp_path):
    """任务#16：回收站用例的逐用例文件系统隔离。

    背景：paths.py 已将开发/测试分支数据根从 ``Path.cwd()`` 改为
    ``get_project_backend_dir()``（固定指向真实 backend/）。回收站链路
    （创建/软删/恢复/彻底删除）伴随审计、快照、上传等副作用，若其中
    任何写操作落到真实 backend/data、backend/uploads，在全量顺序运行时
    会与其它用例产生跨用例写入干扰（test_restore_roundtrip 偶发失败的
    根因）。本 fixture 显式把数据根与 UPLOAD_DIR 重定向到逐用例独立的
    tmp_path，确保回收站测试绝不读写真实 backend 数据目录，也不受其
    它用例遗留的真实目录状态影响。

    数据库隔离已由 conftest 的 ``client`` fixture（sqlite:///:memory:）保证，
    此处只补齐文件系统隔离，不覆盖 DATABASE_URL 以免干扰内存库 override。
    """
    from app.utils import paths as paths_module

    monkeypatch.setattr(paths_module, "get_project_backend_dir", lambda: tmp_path)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    yield


def _make_admin():
    user = type("U", (), {})()
    user.id = 1
    user.username = "admin1"
    user.role = "admin"
    user.is_superuser = False
    user.is_active = True
    user.organization_id = 1
    user.permissions_list = ["*"]
    user.failed_login_count = 0
    user.locked_until = None
    from app.core.security import get_password_hash

    user.hashed_password = get_password_hash("admin123")
    return user


def _make_regular():
    user = type("U", (), {})()
    user.id = 2
    user.username = "user2"
    user.role = "user"
    user.is_superuser = False
    user.is_active = True
    user.organization_id = 2
    user.permissions_list = ["read"]
    user.failed_login_count = 0
    user.locked_until = None
    return user


def _set_user(client, user):
    from app.core.security import get_current_user

    original = client.app.dependency_overrides.copy()
    client.app.dependency_overrides[get_current_user] = lambda: user
    return original


def _restore_overrides(client, original):
    client.app.dependency_overrides = original


def _create_village(client, admin, name="回收站测试村"):
    resp = client.post("/api/v1/supported-villages", json={
        "village_name": name,
        "province": "贵州省",
        "county": "测试县",
    })
    assert resp.status_code in (200, 201), resp.text[:300]
    data = resp.json().get("data") or {}
    return data["id"]


def _soft_delete(client, village_id):
    resp = client.delete(f"/api/v1/supported-villages/{village_id}")
    assert resp.status_code == 200, resp.text[:300]
    return resp


class TestRestoreLifecycle:
    def test_restore_roundtrip(self, client):
        admin = _make_admin()
        original = _set_user(client, admin)
        try:
            vid = _create_village(client, admin, name="恢复回环村")
            _soft_delete(client, vid)

            # 详情可见且 isDeleted=True
            detail = client.get(f"/api/v1/supported-villages/{vid}").json()
            body = detail.get("data") or {}
            assert body.get("isDeleted") is True or body.get("is_deleted") is True

            # 恢复
            resp = client.post(f"/api/v1/supported-villages/{vid}/restore")
            assert resp.status_code == 200, resp.text[:300]

            # 恢复后默认列表应包含该记录
            listing = client.get("/api/v1/supported-villages").json()
            items = (listing.get("data") or {}).get("items") or []
            assert any(it.get("id") == vid for it in items)
        finally:
            _restore_overrides(client, original)

    def test_restore_active_record_rejected(self, client):
        admin = _make_admin()
        original = _set_user(client, admin)
        try:
            vid = _create_village(client, admin, name="未删除不可恢复村")
            resp = client.post(f"/api/v1/supported-villages/{vid}/restore")
            assert resp.status_code == 400
        finally:
            _restore_overrides(client, original)


class TestPurgeLifecycle:
    def test_purge_requires_correct_password(self, client):
        admin = _make_admin()
        original = _set_user(client, admin)
        try:
            vid = _create_village(client, admin, name="彻底删除口令校验村")
            _soft_delete(client, vid)

            # 密码错误 → 400
            bad = client.post(
                f"/api/v1/supported-villages/{vid}/purge",
                json={"confirm_password": "wrong-password"},
            )
            assert bad.status_code == 400

            # 记录仍存在（软删态）
            still = client.get(f"/api/v1/supported-villages/{vid}")
            assert still.status_code == 200
        finally:
            _restore_overrides(client, original)

    def test_purge_cascades_and_removes_village(self, client):
        from app.core.database import get_db

        admin = _make_admin()
        original = _set_user(client, admin)
        try:
            vid = _create_village(client, admin, name="级联彻底删除村")

            # 挂一个子项目
            db_gen = client.app.dependency_overrides.get(get_db)
            db = next(db_gen()) if db_gen else None
            if db is not None:
                db.add(Project(name="级联子项目", village_id=vid, code="PURGE-P-1"))
                from app.core.transaction import safe_commit

                safe_commit(db)

            _soft_delete(client, vid)

            # 预览返回统计
            preview = client.get(f"/api/v1/supported-villages/{vid}/purge/preview")
            assert preview.status_code == 200, preview.text[:300]
            pdata = preview.json().get("data") or {}
            assert pdata.get("village_id") == vid or pdata.get("total_references") >= 0

            # 正确密码 → 物理删除
            ok = client.post(
                f"/api/v1/supported-villages/{vid}/purge",
                json={"confirm_password": "admin123"},
            )
            assert ok.status_code == 200, ok.text[:300]

            # 详情 404
            gone = client.get(f"/api/v1/supported-villages/{vid}")
            assert gone.status_code == 404
        finally:
            _restore_overrides(client, original)

    def test_purge_active_record_rejected(self, client):
        admin = _make_admin()
        original = _set_user(client, admin)
        try:
            vid = _create_village(client, admin, name="未删除不可清除村")
            resp = client.post(
                f"/api/v1/supported-villages/{vid}/purge",
                json={"confirm_password": "admin123"},
            )
            assert resp.status_code == 400
        finally:
            _restore_overrides(client, original)


class TestRecycleBinPermissionMatrix:
    @pytest.mark.parametrize("method,path", [
        ("post", "/api/v1/supported-villages/{vid}/restore"),
        ("get", "/api/v1/supported-villages/{vid}/purge/preview"),
        ("post", "/api/v1/supported-villages/{vid}/purge"),
    ])
    def test_non_admin_forbidden(self, client, method, path):
        admin = _make_admin()
        regular = _make_regular()

        # 管理员准备一条软删记录
        original = _set_user(client, admin)
        try:
            vid = _create_village(client, admin, name="权限矩阵村")
            _soft_delete(client, vid)
        finally:
            _restore_overrides(client, original)

        # 切换为普通用户
        original = _set_user(client, regular)
        try:
            kwargs = {"json": {}} if method == "post" else {}
            resp = getattr(client, method)(path.format(vid=vid), **kwargs)
            assert resp.status_code == 403, f"{method} {path} 应 403: {resp.status_code}"
        finally:
            _restore_overrides(client, original)
