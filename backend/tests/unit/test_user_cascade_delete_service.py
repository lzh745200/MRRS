"""Tests for app/services/user_cascade_delete_service.py — 目标 100% 覆盖。

覆盖要点：
- _safe_ident: 合法标识符 / 空字符串 / 数字开头 / 含空格 / 含特殊字符
- delete_user (async 兼容方法): 返回 True
- delete_user_cascade:
  * 用户不存在
  * 用户存在但无任何关联记录
  * CASCADE 分支：删除引用记录
  * SET NULL + nullable 分支：置空外键
  * SET NULL + NOT NULL 分支：回退为删除
  * NO ACTION + nullable 分支：走 SET NULL 路径
  * NO ACTION + NOT NULL 分支：回退为删除
  * 无 FK 到 users 的表：跳过
  * FK 引用 users 但非 id 列：跳过
  * 表名为非标识符：跳过 (_safe_ident ValueError)
  * 列名为非标识符：跳过 (_safe_ident ValueError)
"""
import asyncio

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.user import User
from app.services.user_cascade_delete_service import (
    UserCascadeDeleteService,
    _safe_ident,
)


# ---------------------------------------------------------------------------
# 内存 DB fixture —— 仅创建 users 表 + 自定义测试表，精确控制分支
# ---------------------------------------------------------------------------


def _build_session():
    """构建内存数据库，包含完整 Base.metadata + 自定义测试表。

    必须创建全部 Base.metadata 表，否则 ``db.delete(user)`` 会因 ORM
    关系（projects/two_factor_auth/sessions 等）懒加载失败抛
    ``NoReferencedTableError``。

    自定义表覆盖 cascade/set_null/set_null+notnull/no_action/no_action+notnull
    以及无 FK / FK 引用非 id 列 / 表名含空格 / 列名含空格 等分支。
    """
    import importlib
    from app.models import _MODULE_MAP
    # 强制导入所有模型子模块，确保 Base.metadata 完整
    for mod_path in set(_MODULE_MAP.values()):
        importlib.import_module(f"app.models{mod_path}")

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    # 用 raw SQL 创建各类测试表（外键约束不强制启用，PRAGMA 反射仍可见）
    with engine.begin() as conn:
        # CASCADE 分支
        conn.execute(text(
            "CREATE TABLE tbl_cascade ("
            " id INTEGER PRIMARY KEY,"
            " user_id INTEGER REFERENCES users(id) ON DELETE CASCADE)"
        ))
        # SET NULL + nullable 分支
        conn.execute(text(
            "CREATE TABLE tbl_set_null ("
            " id INTEGER PRIMARY KEY,"
            " user_id INTEGER REFERENCES users(id) ON DELETE SET NULL)"
        ))
        # SET NULL + NOT NULL 分支（应回退到 DELETE）
        conn.execute(text(
            "CREATE TABLE tbl_set_null_notnull ("
            " id INTEGER PRIMARY KEY,"
            " user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE SET NULL)"
        ))
        # NO ACTION + nullable 分支（应走 SET NULL 路径）
        conn.execute(text(
            "CREATE TABLE tbl_no_action ("
            " id INTEGER PRIMARY KEY,"
            " user_id INTEGER REFERENCES users(id) ON DELETE NO ACTION)"
        ))
        # NO ACTION + NOT NULL 分支（应回退到 DELETE）
        conn.execute(text(
            "CREATE TABLE tbl_no_action_notnull ("
            " id INTEGER PRIMARY KEY,"
            " user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE NO ACTION)"
        ))
        # 无 FK 到 users 的表（应跳过）
        conn.execute(text(
            "CREATE TABLE tbl_no_fk ("
            " id INTEGER PRIMARY KEY, other_id INTEGER)"
        ))
        # FK 引用 users 但非 id 列（应跳过）
        conn.execute(text(
            "CREATE TABLE tbl_fk_wrong_col ("
            " id INTEGER PRIMARY KEY,"
            " username TEXT REFERENCES users(username))"
        ))
        # 表名为非标识符（应跳过：_safe_ident 抛 ValueError）
        conn.execute(text(
            'CREATE TABLE "tbl with space" ('
            " id INTEGER PRIMARY KEY,"
            " user_id INTEGER REFERENCES users(id) ON DELETE CASCADE)"
        ))
        # 列名为非标识符（应跳过该列：_safe_ident 抛 ValueError）
        conn.execute(text(
            "CREATE TABLE tbl_bad_col ("
            " id INTEGER PRIMARY KEY,"
            ' "user id" INTEGER REFERENCES users(id) ON DELETE CASCADE)'
        ))

    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    return db, engine


@pytest.fixture
def svc():
    db, engine = _build_session()
    service = UserCascadeDeleteService(db)
    yield service, db
    db.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# _safe_ident —— 纯函数
# ---------------------------------------------------------------------------


class TestSafeIdent:
    def test_valid_simple(self):
        assert _safe_ident("users") == '"users"'

    def test_valid_with_underscore_and_digits(self):
        assert _safe_ident("user_id_1") == '"user_id_1"'

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="非法的数据库标识符"):
            _safe_ident("")

    def test_starts_with_digit_raises(self):
        with pytest.raises(ValueError):
            _safe_ident("1user")

    def test_contains_space_raises(self):
        with pytest.raises(ValueError):
            _safe_ident("user id")

    def test_contains_hyphen_raises(self):
        with pytest.raises(ValueError):
            _safe_ident("user-id")


# ---------------------------------------------------------------------------
# delete_user (async 兼容方法)
# ---------------------------------------------------------------------------


class TestDeleteUserCompat:
    def test_returns_true(self):
        result = asyncio.run(UserCascadeDeleteService.delete_user(1))
        assert result is True


# ---------------------------------------------------------------------------
# delete_user_cascade
# ---------------------------------------------------------------------------


class TestDeleteUserCascade:
    def test_user_not_found(self, svc):
        service, db = svc
        result = service.delete_user_cascade(9999)
        assert result == {
            "success": False,
            "message": "用户不存在",
            "deleted_records": 0,
            "set_null_records": 0,
        }

    def test_delete_user_with_no_references(self, svc):
        """用户无任何关联记录：仅删除用户本身。"""
        service, db = svc
        u = User(username="lonely", hashed_password="x")
        db.add(u)
        db.commit()
        result = service.delete_user_cascade(u.id)
        assert result["success"] is True
        assert result["deleted_records"] == 1  # 仅用户自己
        assert result["set_null_records"] == 0
        assert db.query(User).filter_by(id=u.id).first() is None

    def test_cascade_branch_deletes_referencing_rows(self, svc):
        """on_delete=CASCADE：引用记录应被删除。"""
        service, db = svc
        u = User(username="cascade_user", hashed_password="x")
        db.add(u)
        db.commit()
        db.execute(text("INSERT INTO tbl_cascade (user_id) VALUES (:uid)"), {"uid": u.id})
        db.commit()

        result = service.delete_user_cascade(u.id)
        assert result["success"] is True
        # 用户(1) + cascade 表的 1 条
        assert result["deleted_records"] >= 2
        assert db.execute(text("SELECT COUNT(*) FROM tbl_cascade")).scalar() == 0
        assert db.query(User).filter_by(id=u.id).first() is None

    def test_set_null_nullable_branch_sets_null(self, svc):
        """on_delete=SET NULL 且列可空：置空外键。"""
        service, db = svc
        u = User(username="setnull_user", hashed_password="x")
        db.add(u)
        db.commit()
        db.execute(text("INSERT INTO tbl_set_null (user_id) VALUES (:uid)"), {"uid": u.id})
        db.commit()

        result = service.delete_user_cascade(u.id)
        assert result["success"] is True
        assert result["set_null_records"] >= 1
        # tbl_set_null 中的记录仍在，但 user_id 已置空
        row = db.execute(text("SELECT user_id FROM tbl_set_null")).first()
        assert row[0] is None
        assert db.query(User).filter_by(id=u.id).first() is None

    def test_set_null_notnull_branch_falls_back_to_delete(self, svc):
        """on_delete=SET NULL 但列非空：回退为删除引用记录。"""
        service, db = svc
        u = User(username="notnull_user", hashed_password="x")
        db.add(u)
        db.commit()
        db.execute(text("INSERT INTO tbl_set_null_notnull (user_id) VALUES (:uid)"), {"uid": u.id})
        db.commit()

        result = service.delete_user_cascade(u.id)
        assert result["success"] is True
        assert db.execute(text("SELECT COUNT(*) FROM tbl_set_null_notnull")).scalar() == 0
        assert db.query(User).filter_by(id=u.id).first() is None

    def test_no_action_nullable_branch_sets_null(self, svc):
        """on_delete=NO ACTION 且列可空：代码走 SET NULL 路径。"""
        service, db = svc
        u = User(username="noaction_user", hashed_password="x")
        db.add(u)
        db.commit()
        db.execute(text("INSERT INTO tbl_no_action (user_id) VALUES (:uid)"), {"uid": u.id})
        db.commit()

        result = service.delete_user_cascade(u.id)
        assert result["success"] is True
        assert result["set_null_records"] >= 1
        row = db.execute(text("SELECT user_id FROM tbl_no_action")).first()
        assert row[0] is None
        assert db.query(User).filter_by(id=u.id).first() is None

    def test_no_action_notnull_branch_falls_back_to_delete(self, svc):
        """on_delete=NO ACTION 且列非空：回退为删除引用记录。"""
        service, db = svc
        u = User(username="noaction_notnull", hashed_password="x")
        db.add(u)
        db.commit()
        db.execute(text("INSERT INTO tbl_no_action_notnull (user_id) VALUES (:uid)"), {"uid": u.id})
        db.commit()

        result = service.delete_user_cascade(u.id)
        assert result["success"] is True
        assert db.execute(text("SELECT COUNT(*) FROM tbl_no_action_notnull")).scalar() == 0
        assert db.query(User).filter_by(id=u.id).first() is None

    def test_no_fk_table_is_skipped(self, svc):
        """无 FK 到 users 的表应被跳过（数据保留）。"""
        service, db = svc
        u = User(username="nofk_user", hashed_password="x")
        db.add(u)
        db.commit()
        db.execute(text("INSERT INTO tbl_no_fk (other_id) VALUES (42)"))
        db.commit()

        service.delete_user_cascade(u.id)
        # tbl_no_fk 数据应保留
        assert db.execute(text("SELECT other_id FROM tbl_no_fk")).scalar() == 42

    def test_fk_referencing_non_id_column_is_skipped(self, svc):
        """FK 引用 users 但非 id 列（如 username）应被跳过。"""
        service, db = svc
        u = User(username="wrong_col_user", hashed_password="x")
        db.add(u)
        db.commit()
        db.execute(text("INSERT INTO tbl_fk_wrong_col (username) VALUES (:name)"),
                   {"name": u.username})
        db.commit()

        service.delete_user_cascade(u.id)
        # 记录应保留（未触发删除/置空）
        assert db.execute(text("SELECT COUNT(*) FROM tbl_fk_wrong_col")).scalar() == 1

    def test_non_identifier_table_name_is_skipped(self, svc):
        """表名含空格（非标识符）应被跳过。"""
        service, db = svc
        u = User(username="bad_table_user", hashed_password="x")
        db.add(u)
        db.commit()
        db.execute(text('INSERT INTO "tbl with space" (user_id) VALUES (:uid)'),
                   {"uid": u.id})
        db.commit()

        service.delete_user_cascade(u.id)
        # 表名无法通过 _safe_ident，记录应保留
        assert db.execute(text('SELECT COUNT(*) FROM "tbl with space"')).scalar() == 1

    def test_non_identifier_column_name_is_skipped(self, svc):
        """列名含空格（非标识符）应跳过该列。"""
        service, db = svc
        u = User(username="bad_col_user", hashed_password="x")
        db.add(u)
        db.commit()
        db.execute(text('INSERT INTO tbl_bad_col ("user id") VALUES (:uid)'),
                   {"uid": u.id})
        db.commit()

        service.delete_user_cascade(u.id)
        # 列名无法通过 _safe_ident，记录应保留（用户已被删除）
        assert db.execute(text("SELECT COUNT(*) FROM tbl_bad_col")).scalar() == 1
        assert db.query(User).filter_by(id=u.id).first() is None

    def test_multiple_branches_combined(self, svc):
        """综合场景：一个用户被多张表引用，各分支按预期处理。"""
        service, db = svc
        u = User(username="combined_user", hashed_password="x")
        db.add(u)
        db.commit()
        for tbl, col in [
            ("tbl_cascade", "user_id"),
            ("tbl_set_null", "user_id"),
            ("tbl_set_null_notnull", "user_id"),
            ("tbl_no_action", "user_id"),
            ("tbl_no_action_notnull", "user_id"),
        ]:
            db.execute(text(f"INSERT INTO {tbl} ({col}) VALUES (:uid)"), {"uid": u.id})
        db.commit()

        result = service.delete_user_cascade(u.id)
        assert result["success"] is True
        # 5 张表 + 用户本身 = 6 条删除/置空
        # 删除类：cascade + set_null_notnull + no_action_notnull + 用户 = 4 deleted
        # 置空类：set_null + no_action = 2 set_null
        assert result["deleted_records"] == 4
        assert result["set_null_records"] == 2
        assert db.query(User).filter_by(id=u.id).first() is None

    def test_multiple_rows_in_cascade_table(self, svc):
        """CASCADE 表中有多行引用同一用户：rowcount 累加。"""
        service, db = svc
        u = User(username="multi_row_user", hashed_password="x")
        db.add(u)
        db.commit()
        for _ in range(3):
            db.execute(text("INSERT INTO tbl_cascade (user_id) VALUES (:uid)"), {"uid": u.id})
        db.commit()

        result = service.delete_user_cascade(u.id)
        assert result["success"] is True
        # 3 行 + 用户本身
        assert result["deleted_records"] >= 4
        assert db.execute(text("SELECT COUNT(*) FROM tbl_cascade")).scalar() == 0


# ---------------------------------------------------------------------------
# W2-T5 合规留痕保护：approval_records / import_histories 绝不物理删除
# ---------------------------------------------------------------------------


class TestAuditTrailPreserved:
    def test_approval_records_preserved_with_null_approver(self, svc):
        """删除用户后审批记录保留（approver_id 置空），合规痕迹不销毁"""
        from app.models.approval import ApprovalRecord, ApprovalTask

        service, db = svc
        u = User(username="auditor", hashed_password="x")
        db.add(u)
        db.commit()
        task = ApprovalTask(
            workflow_id=0, entity_type="fund", entity_id=1,
            submitter_id=u.id, current_level=1,
        )
        db.add(task)
        db.commit()
        rec = ApprovalRecord(
            task_id=task.id, level=1, approver_id=u.id, action="approve"
        )
        db.add(rec)
        db.commit()
        rec_id = rec.id

        result = service.delete_user_cascade(u.id)
        assert result["success"] is True
        row = db.query(ApprovalRecord).filter(ApprovalRecord.id == rec_id).first()
        assert row is not None, "审批留痕被物理删除（违反 W2-T5）"
        assert row.approver_id is None

    def test_import_histories_preserved_with_null_user(self, svc):
        """删除用户后导入历史保留（user_id 置空）"""
        from app.models.import_history import ImportHistory

        service, db = svc
        u = User(username="importer", hashed_password="x")
        db.add(u)
        db.commit()
        ih = ImportHistory(
            user_id=u.id, file_name="a.xlsx", file_size=10,
            entity_type="supported_village",
        )
        db.add(ih)
        db.commit()
        ih_id = ih.id

        result = service.delete_user_cascade(u.id)
        assert result["success"] is True
        row = db.query(ImportHistory).filter(ImportHistory.id == ih_id).first()
        assert row is not None, "导入历史被物理删除（违反 W2-T5）"
        assert row.user_id is None


class TestPolicyFavoriteCascade:
    def test_deleting_policy_removes_favorites(self, svc):
        """W2-T5：删除被收藏的政策成功，收藏行级联清除而非 IntegrityError"""
        from app.models.policy import Policy, PolicyFavorite

        _service, db = svc
        # SQLite 默认不启用外键强制，测试级联需显式开启（StaticPool 单连接内生效）
        db.execute(text("PRAGMA foreign_keys=ON"))
        u = User(username="fav_user", hashed_password="x")
        db.add(u)
        pol = Policy(title="政策A", content="c")
        db.add(pol)
        db.commit()
        fav = PolicyFavorite(user_id=u.id, policy_id=pol.id)
        db.add(fav)
        db.commit()
        fav_id = fav.id

        db.delete(pol)  # ondelete=CASCADE → 收藏行级联清除
        db.commit()
        remain = (
            db.query(PolicyFavorite)
            .filter(PolicyFavorite.id == fav_id)
            .count()
        )
        assert remain == 0

    def test_favorite_column_is_nullable_contract(self):
        """模型契约：policy_id 走 CASCADE；ImportHistory.user_id/ApprovalRecord.approver_id 可空"""
        from app.models.import_history import ImportHistory
        from app.models.approval import ApprovalRecord
        from app.models.policy import PolicyFavorite

        fav_fk = list(PolicyFavorite.__table__.c.policy_id.foreign_keys)[0]
        assert (fav_fk.ondelete or "").upper() == "CASCADE"
        assert ImportHistory.__table__.c.user_id.nullable is True
        assert ApprovalRecord.__table__.c.approver_id.nullable is True
