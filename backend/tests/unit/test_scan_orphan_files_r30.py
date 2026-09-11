"""P2-2 孤立附件扫描脚本 核心逻辑全覆盖测试。

覆盖：``resolve_reference`` / ``scan_orphans`` / ``collect_db_references`` /
``delete_orphans`` / ``format_report`` / ``main``（只读 + 删除 + 拒绝删除）。
"""

import importlib.util
import json
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_BACKEND = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _BACKEND / "scripts" / "scan_orphan_files.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("scan_orphan_files_r30", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scan = _load_script()


class _EmptyDB:
    """空库 stub：任何 query().all() 均返回空列表。"""

    def query(self, *args, **kwargs):  # noqa: D102
        return self

    def all(self):  # noqa: D102
        return []

    def close(self):  # noqa: D102
        return None


class _RaisingDB:
    """异常 stub：任何 query 都抛错，用于触发「引用解析错误」保护。"""

    def query(self, *args, **kwargs):  # noqa: D102
        raise RuntimeError("boom")

    def close(self):  # noqa: D102
        return None


class TestResolveReference:
    def test_uploads_url(self, tmp_path):
        got = scan.resolve_reference("/uploads/policies/a.pdf", str(tmp_path))
        assert got == os.path.normpath(os.path.join(str(tmp_path), "policies", "a.pdf"))

    def test_relative_uploads_url(self, tmp_path):
        got = scan.resolve_reference("uploads/policies/b.pdf", str(tmp_path))
        assert got == os.path.normpath(os.path.join(str(tmp_path), "policies", "b.pdf"))

    def test_absolute_path(self, tmp_path):
        f = tmp_path / "x.pdf"
        assert scan.resolve_reference(str(f), str(tmp_path)) == os.path.normpath(str(f))

    def test_empty_and_none(self, tmp_path):
        assert scan.resolve_reference(None, str(tmp_path)) is None
        assert scan.resolve_reference("", str(tmp_path)) is None
        assert scan.resolve_reference("   ", str(tmp_path)) is None
        assert scan.resolve_reference(123, str(tmp_path)) is None


class TestScanOrphans:
    def test_missing_dir_returns_empty(self, tmp_path):
        assert scan.scan_orphans(str(tmp_path / "nope"), set()) == []
        assert scan.scan_orphans("", set()) == []

    def test_orphan_detected_and_sorted(self, tmp_path):
        (tmp_path / "used.txt").write_bytes(b"u")
        (tmp_path / "big.bin").write_bytes(b"x" * 100)
        (tmp_path / "small.bin").write_bytes(b"y")
        referenced = {scan._norm(str(tmp_path / "used.txt"))}

        orphans = scan.scan_orphans(str(tmp_path), referenced)
        names = [os.path.basename(o["path"]) for o in orphans]
        assert "used.txt" not in names
        assert names == ["big.bin", "small.bin"]  # 按大小降序
        assert orphans[0]["size"] == 100


class TestDeleteOrphans:
    def test_delete_removes_files(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"a")
        f2.write_bytes(b"b")
        orphans = scan.scan_orphans(str(tmp_path), set())
        deleted, failed = scan.delete_orphans(orphans)
        assert set(deleted) == {str(f1), str(f2)}
        assert failed == []
        assert not f1.exists() and not f2.exists()


class TestFormatReport:
    def test_report_contents(self, tmp_path):
        (tmp_path / "o.txt").write_bytes(b"z")
        orphans = scan.scan_orphans(str(tmp_path), set())
        report = scan.format_report(orphans, str(tmp_path), 3, [])
        assert "孤立文件数      : 1" in report
        assert "DB 引用文件数   : 3" in report

    def test_report_with_errors_and_limit(self, tmp_path):
        for i in range(3):
            (tmp_path / f"f{i}.txt").write_bytes(b"x" * (i + 1))
        orphans = scan.scan_orphans(str(tmp_path), set())
        report = scan.format_report(orphans, str(tmp_path), 0, ["db down"], limit=1)
        assert "引用解析错误    : 1 项" in report
        assert "已省略" in report


class TestCollectDbReferences:
    def test_collects_from_blob_and_business_tables(self, tmp_path):
        import app.main  # noqa: F401 - 注册全部模型以建表
        from app.models.base import Base
        from app.models.file_blob import FileBlob
        from app.models.fund import FundAttachment
        from app.models.policy import Policy

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()

        blob_file = tmp_path / "blob.bin"
        blob_file.write_bytes(b"b")
        policy_file = tmp_path / "policy.pdf"
        policy_file.write_bytes(b"p")

        db.add(FileBlob(sha256="a" * 64, path=str(blob_file), size=1, ref_count=1))
        db.add(FundAttachment(fund_id=1, file_path=str(tmp_path / "fund.pdf"), file_name="f"))
        db.add(
            Policy(
                title="p",
                file_path=str(policy_file),
                attachment_urls=json.dumps(["/uploads/policies/extra.pdf"]),
            )
        )
        db.commit()

        referenced, errors = scan.collect_db_references(db, str(tmp_path))
        db.close()

        assert errors == []
        assert scan._norm(str(blob_file)) in referenced
        assert scan._norm(str(policy_file)) in referenced
        assert scan._norm(str(tmp_path / "fund.pdf")) in referenced
        assert scan._norm(os.path.join(str(tmp_path), "policies", "extra.pdf")) in referenced

    def test_query_errors_are_reported(self, tmp_path):
        referenced, errors = scan.collect_db_references(_RaisingDB(), str(tmp_path))
        assert referenced == set()
        assert errors, "引用来源异常必须被记录以阻止误删"

    def test_invalid_attachment_urls_json_ignored(self, tmp_path):
        import app.main  # noqa: F401
        from app.models.base import Base
        from app.models.policy import Policy

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        db.add(Policy(title="p", file_path=None, attachment_urls="{not-json}"))
        db.add(Policy(title="q", file_path=None, attachment_urls=json.dumps({"a": 1})))
        db.commit()
        referenced, errors = scan.collect_db_references(db, str(tmp_path))
        db.close()
        assert errors == []
        assert referenced == set()


class TestMainEntrypoint:
    def test_read_only_mode(self, tmp_path, monkeypatch, capsys):
        import app.core.database as db_module

        (tmp_path / "orphan.txt").write_bytes(b"x")
        monkeypatch.setattr(db_module, "SessionLocal", lambda: _EmptyDB())

        rc = scan.main(["--upload-dir", str(tmp_path)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "只读模式" in out
        assert (tmp_path / "orphan.txt").exists()

    def test_delete_mode(self, tmp_path, monkeypatch, capsys):
        import app.core.database as db_module

        f = tmp_path / "orphan.txt"
        f.write_bytes(b"x")
        monkeypatch.setattr(db_module, "SessionLocal", lambda: _EmptyDB())

        rc = scan.main(["--upload-dir", str(tmp_path), "--delete"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "删除完成" in out
        assert not f.exists()

    def test_refuses_delete_on_reference_errors(self, tmp_path, monkeypatch, capsys):
        import app.core.database as db_module

        f = tmp_path / "orphan.txt"
        f.write_bytes(b"x")
        monkeypatch.setattr(db_module, "SessionLocal", lambda: _RaisingDB())

        rc = scan.main(["--upload-dir", str(tmp_path), "--delete"])
        out = capsys.readouterr().out
        assert rc == 2
        assert "拒绝删除" in out
        assert f.exists()  # 宁可漏报，不可误删
