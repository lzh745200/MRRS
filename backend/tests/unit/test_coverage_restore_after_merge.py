"""覆盖率补丁：合并后新增代码的零散缺口（W27 收尾）。

## 背景
登录页改造完成后按 CI 口径复跑 12 段，12/12 通过，但 `backend/.coveragerc`
曾被误删导致 `fail_under=100` 静默失效；恢复配置后暴露 **5 处缺口**，
全部位于**本次登录页改造未触碰**的文件（均为后续合并进来的新代码）：

* `app/models/fund_budget.py:139`      —— `FundTransaction.__repr__` 从未被调用
* `app/models/machine_code.py:76`      —— `MachineCode.__repr__` 从未被调用
* `app/services/backup_service.py:111->113` —— `_parse_backup_info` 只测过 bytes 入参
* `app/services/backup_service.py:1453->1455` —— 增量 ZIP 未测「无密钥指纹」分支
* `app/api/v1/data/data/data_packages.py:785->787` —— 既无 organization_id
  也无 org_id 的模型未测（现有 fake 模型各带其一，永远走不到假分支）

`__repr__` 不是可有可无的装饰：对象会出现在日志、审计详情与调试输出里，
一个抛异常的 `__repr__` 会让"记录日志"这个动作本身炸掉。
"""

import zipfile
from datetime import datetime
from unittest.mock import MagicMock, patch


class TestModelRepr:
    """`__repr__` 必须能在字段为 None/空时安全输出（日志与审计会调用它）。"""

    def test_fund_transaction_repr(self):
        from app.models.fund_budget import FundTransaction

        tx = FundTransaction()
        tx.id = 7
        tx.amount = 100
        tx.purpose = "修路"
        text = repr(tx)
        assert "FundTransaction" in text
        assert "id=7" in text
        assert "修路" in text

    def test_fund_transaction_repr_without_purpose(self):
        """purpose 为空时取空串，不能因 None 切片而抛错。"""
        from app.models.fund_budget import FundTransaction

        tx = FundTransaction()
        tx.id = 8
        tx.amount = None
        tx.purpose = None
        assert "FundTransaction" in repr(tx)

    def test_machine_code_repr(self):
        from app.models.machine_code import MachineCode

        mc = MachineCode()
        mc.machine_code = "ABCDEF0123456789XYZ"
        mc.status = "approved"
        mc.user_id = 3
        text = repr(mc)
        assert "MachineCode" in text
        # 只截前 16 位，避免日志里出现完整机器码
        assert "ABCDEF0123456789" in text
        assert "XYZ" not in text
        assert "status='approved'" in text


class TestParseBackupInfo:
    """`_parse_backup_info` 需同时吃 bytes / JSON / 历史 `str(dict)` 三种形态。"""

    def test_accepts_str_json(self):
        from app.services.backup_service import _parse_backup_info

        # 覆盖 111->113：入参已是 str → 跳过 decode
        assert _parse_backup_info('{"version": "1.0"}') == {"version": "1.0"}

    def test_accepts_str_dict_repr(self):
        from app.services.backup_service import _parse_backup_info

        assert _parse_backup_info("{'version': '1.0'}") == {"version": "1.0"}

    def test_accepts_bytes(self):
        from app.services.backup_service import _parse_backup_info

        assert _parse_backup_info(b'{"version": "1.0"}') == {"version": "1.0"}

    def test_rejects_non_object_and_garbage(self):
        from app.services.backup_service import _parse_backup_info

        assert _parse_backup_info("not-a-dict") is None
        assert _parse_backup_info("[1, 2]") is None
        assert _parse_backup_info(None) is None


class TestIncrementalZipFingerprint:
    """增量备份包是否写入密钥指纹（1453->1455 的假分支：取不到指纹就不写）。"""

    @staticmethod
    def _svc():
        from app.services.backup_service import BackupService

        svc = BackupService.__new__(BackupService)
        svc.compression_level = 6
        return svc

    def test_no_fingerprint_when_unavailable(self, tmp_path):
        from app.services import backup_service as bs

        target = tmp_path / "inc.zip"
        with patch.object(bs, "_current_key_fingerprint", return_value=None):
            self._svc()._write_incremental_backup_zip(
                str(target), [], {"files": {}}, "2026-01-01T00:00:00", "desc", False
            )
        assert target.exists()
        with zipfile.ZipFile(target) as zf:
            info = __import__("json").loads(zf.read("backup_info.json").decode("utf-8"))
        assert bs.KEY_FINGERPRINT_FIELD not in info

    def test_fingerprint_written_when_available(self, tmp_path):
        from app.services import backup_service as bs

        target = tmp_path / "inc2.zip"
        with patch.object(bs, "_current_key_fingerprint", return_value="deadbeefdeadbeef"):
            self._svc()._write_incremental_backup_zip(
                str(target), [], {"files": {}}, "2026-01-01T00:00:00", "desc", False
            )
        with zipfile.ZipFile(target) as zf:
            info = __import__("json").loads(zf.read("backup_info.json").decode("utf-8"))
        assert info[bs.KEY_FINGERPRINT_FIELD] == "deadbeefdeadbeef"


class TestRestoreUploadKeyMismatchCleanup:
    """`POST /system/backup/upload-restore`：密钥不一致 → 409 **且清理临时包**。

    如果不清理，每次跨机误导入都会在备份目录里留下一个 10GB 级别的残包，
    长时间运行会把这台机器的磁盘吃满 —— 这是个"只在出错路径上发生"的泄漏，
    正常流程测试永远发现不了。
    """

    URL = "/api/v1/system/backup/upload-restore"

    @staticmethod
    def _zip_bytes():
        import io

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("data/rural_revitalization.db", b"sqlite")
        return buf.getvalue()

    def _client(self):
        from fastapi.testclient import TestClient

        from app.api.v1.deps import get_current_user
        from app.core.database import get_db
        from app.main import app

        app.dependency_overrides[get_db] = lambda: MagicMock()
        app.dependency_overrides[get_current_user] = lambda: type(
            "U", (), {"id": 1, "username": "admin", "role": "super_admin", "is_superuser": True}
        )()
        return TestClient(app, raise_server_exceptions=False), app

    def test_mismatch_removes_temp_package(self):
        from app.services.backup_service import BackupKeyMismatchError

        client, app = self._client()
        svc = MagicMock()
        svc.restore_backup.side_effect = BackupKeyMismatchError()
        try:
            with (
                patch(
                    "app.api.v1.system.backup.get_backup_service", return_value=svc, create=True
                ),
                patch("app.api.v1.system.backup.os.path.exists", return_value=True),
                patch("app.api.v1.system.backup.os.remove") as mock_remove,
            ):
                resp = client.post(
                    self.URL, files={"file": ("b.zip", self._zip_bytes(), "application/zip")}
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 409
        mock_remove.assert_called_once()

    def test_mismatch_tolerates_remove_failure(self):
        """删除失败（文件被占用等）不得把 409 变成 500。"""
        from app.services.backup_service import BackupKeyMismatchError

        client, app = self._client()
        svc = MagicMock()
        svc.restore_backup.side_effect = BackupKeyMismatchError()
        try:
            with (
                patch(
                    "app.api.v1.system.backup.get_backup_service", return_value=svc, create=True
                ),
                patch("app.api.v1.system.backup.os.path.exists", return_value=True),
                patch("app.api.v1.system.backup.os.remove", side_effect=OSError("busy")),
            ):
                resp = client.post(
                    self.URL, files={"file": ("b.zip", self._zip_bytes(), "application/zip")}
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 409

    def test_mismatch_skips_remove_when_file_gone(self):
        """落盘文件已被移除（并发/清理）→ 跳过删除，仍返回 409。"""
        from app.services.backup_service import BackupKeyMismatchError

        client, app = self._client()
        svc = MagicMock()
        svc.restore_backup.side_effect = BackupKeyMismatchError()
        try:
            with (
                patch(
                    "app.api.v1.system.backup.get_backup_service", return_value=svc, create=True
                ),
                patch("app.api.v1.system.backup.os.path.exists", return_value=False),
                patch("app.api.v1.system.backup.os.remove") as mock_remove,
            ):
                resp = client.post(
                    self.URL, files={"file": ("b.zip", self._zip_bytes(), "application/zip")}
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 409
        mock_remove.assert_not_called()


class _FakePlainModel:
    """既无 organization_id 也无 org_id，但有 updated_at。

    现有两个 fake 模型各带其中一个字段，`hasattr(model, "org_id")` 的**假分支**
    （785->787）因此从未被走到 —— 真实世界里 DATA_TYPE_MODELS 一旦接入
    按 id 而非组织归属的表，就会落到这条路径。

    对应的端点级用例放在 `test_data_packages_cov2.py::TestDetectChanges`
    （那里有现成的依赖注入 harness，重复搭一套只会得到两套易漂移的替身）。
    """

    id = 1
    updated_at = datetime(2026, 1, 1)
    created_at = datetime(2026, 1, 1)
    is_active = 1
