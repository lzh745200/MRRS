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
    session, _ = db
    from app.models.village import Villager, Village

    village = Village(name="测试村")
    session.add(village)
    session.flush()
    v = Villager(village_id=village.id, name="张三", id_card=ID_CARD, phone=PHONE)
    session.add(v)
    session.commit()

    # 裸 SQL 直读存储层 → 必须是标记密文，且不含明文
    conn = session.connection()
    row = conn.exec_driver_sql(
        'SELECT id_card, phone FROM villagers WHERE id = ?', (v.id,)
    ).fetchone()
    assert is_encrypted(row[0]) and row[0] != ID_CARD
    assert is_encrypted(row[1]) and row[1] != PHONE

    # ORM 读取 → 透明解密
    session.expire_all()
    v2 = session.query(Villager).filter(Villager.id == v.id).one()
    assert v2.id_card == ID_CARD
    assert v2.phone == PHONE


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
    raw = open(db_path, "rb").read()
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
    assert set(mod._iter_pii_columns()) == encrypted, "迁移回填清单与模型加密列不一致"
