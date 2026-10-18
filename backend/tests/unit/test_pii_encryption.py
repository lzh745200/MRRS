"""PII 字段透明加密（W5-T7 / ADR-0005）验收测试

验收标准（工单）：
1. id_card/phone 落库为密文、ORM 读取透明解密
2. 查询按密文等值匹配（确定性 AES-SIV）
3. DB 文件直接打开看不到明文 PII
4. 迁移回填清单与模型 EncryptedText 列一致（防漂移）
5. 历史明文行原样透出（兼容未迁移数据）
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.pii_crypto import decrypt_pii, encrypt_pii, is_encrypted
from app.models.base import EncryptedText


@pytest.fixture
def db(tmp_path):
    """文件型 SQLite（支持"直接打开文件看密文"验收），每用例独立"""
    engine = create_engine(f"sqlite:///{tmp_path/'pii_test.db'}", connect_args={"check_same_thread": False})
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session, str(tmp_path / "pii_test.db")
    session.close()
    engine.dispose()


ID_CARD = "110101199003077758"
PHONE = "13800138000"


def test_roundtrip_and_determinism():
    c1 = encrypt_pii(PHONE)
    c2 = encrypt_pii(PHONE)
    assert c1 == c2, "确定性加密：同明文必须同密文（等值查询前提）"
    assert c1 != PHONE and is_encrypted(c1)
    assert decrypt_pii(c1) == PHONE
    assert encrypt_pii(None) is None
    assert decrypt_pii(None) is None
    assert decrypt_pii(PHONE) == PHONE  # 历史明文原样透出
    assert decrypt_pii("enc.v1:!!!坏数据") == "enc.v1:!!!坏数据"  # 解密失败不抛异常


def test_orm_writes_ciphertext_reads_plaintext(db):
    """W22：villagers 表已删除；改用 School.contact_phone 验证 ORM 透明加解密。"""
    session, _ = db
    from app.models.organization import Organization
    from app.models.school import School

    session.add(Organization(id=1, name="测试单位"))
    session.flush()
    school = School(name="测试学校", contact_phone=PHONE, organization_id=1)
    session.add(school)
    session.commit()

    # 裸 SQL 直读存储层 → 必须是标记密文，且不含明文
    conn = session.connection()
    row = conn.exec_driver_sql(
        "SELECT contact_phone FROM schools WHERE id = ?", (school.id,)
    ).fetchone()
    assert is_encrypted(row[0]) and row[0] != PHONE

    # ORM 读取 → 透明解密
    session.expire_all()
    school2 = session.query(School).filter(School.id == school.id).one()
    assert school2.contact_phone == PHONE


def test_equality_query_matches_ciphertext(db):
    session, _ = db
    from app.models.user import User

    session.add(User(username="u1", hashed_password="x", phone=PHONE))
    session.add(User(username="u2", hashed_password="x", phone="13900139000"))
    session.commit()

    hit = session.query(User).filter(User.phone == PHONE).all()
    assert len(hit) == 1 and hit[0].username == "u1"


def test_db_file_has_no_plaintext(db):
    session, db_path = db
    from app.models.user import User

    session.add(User(username="u1", hashed_password="x", phone=PHONE))
    session.commit()
    session.close()  # 确保 WAL 落盘
    with open(db_path, "rb") as _f:
        raw = _f.read()
    assert PHONE.encode() not in raw, "DB 文件中出现明文手机号"
    assert b"enc.v1:" in raw, "DB 文件中未见密文标记"


def test_legacy_plaintext_row_passthrough(db):
    """迁移前的历史明文行：ORM 读取原样返回，不报错"""
    session, _ = db
    from app.models.user import User

    session.add(User(username="legacy", hashed_password="x"))
    session.commit()
    conn = session.connection()
    conn.exec_driver_sql("UPDATE users SET phone = ? WHERE username = 'legacy'", (PHONE,))
    session.expire_all()
    u = session.query(User).filter(User.username == "legacy").one()
    assert u.phone == PHONE


def test_migration_list_matches_model_metadata():
    import importlib.util
    from pathlib import Path

    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "pii_encrypt_001_backfill.py"
    spec = importlib.util.spec_from_file_location("pii_encrypt_001_backfill", migration_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from app.models import Base

    encrypted = set()
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, EncryptedText):
                encrypted.add((table.name, col.name))
    # W22 新表（households / household_members）由 w22 迁移直接建加密列，
    # 不属于历史回填迁移的职责范围（无历史明文，ORM 直接写密文）；
    # W22 同时删除了 villagers 表——历史回填清单中的 villagers 两列保留在迁移历史里
    # （旧库升级时仍会执行回填），但当前模型不再包含该表。
    w22_new_tables = {"households", "household_members"}
    historical = {item for item in encrypted if item[0] not in w22_new_tables}
    deleted_tables = {"villagers"}
    migration_cols = {item for item in mod._iter_pii_columns() if item[0] not in deleted_tables}
    assert migration_cols == historical, "迁移回填清单与模型加密列不一致"
    # 新表 PII 列必须都是 EncryptedText（ORM 层透明加密）
    assert {item for item in encrypted if item[0] in w22_new_tables} == {
        ("households", "helper_phone"),
        ("household_members", "id_card"),
    }
    # 被删除的表不得再出现在模型 metadata 中（防止"删表但忘删模型"）
    from app.models import Base as _Base

    assert all(table not in _Base.metadata.tables for table in deleted_tables)


def test_key_fingerprint_is_stable_and_not_the_key(monkeypatch):
    """W18-B：指纹用于比对密钥是否漂移，必须稳定、且不能等于密钥本身。"""
    from app.core import pii_crypto

    fp1 = pii_crypto.key_fingerprint()
    fp2 = pii_crypto.key_fingerprint()
    assert fp1 == fp2
    assert len(fp1) == 16
    assert all(c in "0123456789abcdef" for c in fp1)
    # 换一把密钥后指纹必须变（否则"漂移检测"形同虚设）
    monkeypatch.setattr("app.core.config.settings.ENCRYPTION_KEY", "another-key-" + "x" * 32)
    pii_crypto.reset_key_cache()
    try:
        assert pii_crypto.key_fingerprint() != fp1
    finally:
        pii_crypto.reset_key_cache()
