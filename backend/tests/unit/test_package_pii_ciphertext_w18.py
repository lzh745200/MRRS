"""W18-D8 回归：数据包导出对 PII 列必须保持**密文**（两条同步链口径统一）。

缺陷：_export_data_type 走 ORM，EncryptedText 的 TypeDecorator 把 PII 解密成
明文带进数据包（uploads/packages/*.zip 明文存活 7 天 + 被 include_uploads 备份
带走）；而 data_sync 链走 raw SQL 拿的是密文 —— 两条链相反，跨机导入必坏。
修复：导出统一走 raw SQL（库内原样密文）；同密钥跨机导入后 TypeDecorator 透明解密。

PII 载体用 Project.contact_phone（ADR-0005 列之一，且 projects 在 DATA_TYPE_MODELS 内）。
"""
import zipfile

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def svc(db):
    from unittest.mock import patch

    from app.services.data_package_service import DataPackageService

    with patch("app.services.data_package_service.os.makedirs"), patch(
        "app.utils.paths.get_app_data_dir",
    ):
        return DataPackageService(db, upload_dir="/tmp/test_pkg_d8")


@pytest.fixture
def org(db):
    from app.models.organization import Organization

    o = Organization(name="测试组织", code="D8", is_active=True)
    db.add(o)
    db.commit()
    return o


def _project_with_phone(db, org, phone, code="P1"):
    from app.models.project import Project

    p = Project(
        name=f"项目{code}", organization_id=org.id, is_active=True,
        code=code, contact_phone=phone,
    )
    db.add(p)
    db.commit()
    return p


class TestPackageKeepsCiphertext:
    def test_export_stores_ciphertext_not_plaintext(self, db, svc, org):
        """核心：导出记录里 PII 列必须是 enc.v1: 密文，绝不能是明文手机号。"""
        from app.core.pii_crypto import MARKER
        from app.models.project import Project

        _project_with_phone(db, org, "13800138000")
        raw = db.execute(
            text("SELECT contact_phone FROM projects LIMIT 1")
        ).scalar()
        assert raw and raw.startswith(MARKER), "前置失败：库内不是密文"

        records = svc._export_data_type(org.id, Project)
        assert len(records) == 1
        exported = records[0]["contact_phone"]
        assert exported.startswith(MARKER), f"导出成了明文: {exported!r}"
        assert "13800138000" not in exported

    def test_plaintext_never_enters_zip(self, db, svc, org, tmp_path):
        """端到端：写出的 zip 内 JSON 不含明文手机号。"""
        import json as _json

        from app.core.pii_crypto import MARKER
        from app.models.project import Project
        from app.services.data_package_service import CustomJSONEncoder

        _project_with_phone(db, org, "13800138000")
        records = svc._export_data_type(org.id, Project)
        zip_path = tmp_path / "pkg.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr(
                "data/projects.json",
                _json.dumps(records, ensure_ascii=False, cls=CustomJSONEncoder),
            )
        with zipfile.ZipFile(str(zip_path)) as zf:
            content = zf.read("data/projects.json").decode("utf-8")
        assert "13800138000" not in content
        assert MARKER in content

    def test_roundtrip_same_key_readable(self, db, svc, org):
        """同密钥下，包内密文写入库 → TypeDecorator 透明解密 → 字段可读。

        跨机契约：包内是密文（D8），目标机以相同 ENCRYPTION_KEY 打开即透明可读。
        用 raw INSERT 模拟"导入落库"（绕开 D1 主键策略的干扰，聚焦密文可读性）。
        """
        from app.core.pii_crypto import MARKER
        from app.models.project import Project

        _project_with_phone(db, org, "13800138000")
        records = svc._export_data_type(org.id, Project)
        assert records[0]["contact_phone"].startswith(MARKER)

        # 模拟目标机导入落库：密文字符串直接 bind（与 bulk upsert 的绑定形态一致）
        db.add(Project(
            name="导入的项目", code="P2", organization_id=org.id, is_active=True,
            contact_phone=records[0]["contact_phone"],
        ))
        db.commit()
        row = db.query(Project).filter(Project.code == "P2").one()
        assert row.contact_phone == "13800138000"   # 透明解密成功

    def test_import_accepts_ciphertext_records(self, db, svc, org):
        """bulk upsert 接受密文记录：同 id 同 org → same → DO NOTHING（D4 计数）。"""
        from app.models.project import Project

        _project_with_phone(db, org, "13800138000")
        records = svc._export_data_type(org.id, Project)
        imp, skip, errs = svc._bulk_upsert_records(
            Project, records, org_id=org.id, overwrite=False,
        )
        assert errs == []
        assert imp == 0 and skip == 1        # 同一条记录 → 跳过（D4 真实计数）

    def test_no_pii_column_models_unaffected(self, db, svc, org):
        """无 PII 列的模型走 raw SQL 同样正常导出（回归不伤别处）。"""
        from app.models.project import Project

        p = Project(name="普通项目", organization_id=org.id, is_active=True, code="P9")
        db.add(p)
        db.commit()
        records = svc._export_data_type(org.id, Project)
        assert len(records) == 1
        assert records[0]["name"] == "普通项目"