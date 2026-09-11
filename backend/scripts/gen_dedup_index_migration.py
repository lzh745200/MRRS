"""生成「历史孤儿索引」清理候选清单（权威判定）。

权威判定方式：以 SQLAlchemy 模型元数据（Base.metadata.tables[*].indexes）+
EXTRA_INDEXES 作为「当前源码会重建的索引集合」，凡存活于 DB 但不在此集合中、
且非 sqlite_autoindex_* 的索引，即为历史孤儿（迁移遗留、源码已无定义），删除安全。

只读分析，输出候选清单（不执行 DROP）。
"""
import os
import sqlite3
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def _resolve_db() -> str:
    try:
        from app.core.config import settings

        url = settings.DATABASE_URL
        if url.startswith("sqlite:///"):
            p = url[len("sqlite:///"):]
            if os.path.exists(p):
                return p
    except Exception:
        pass
    d = os.path.join(_BACKEND, "data")
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.endswith(".db"):
                return os.path.join(d, f)
    return os.path.join(d, "rural_revitalization.db")


def source_defined_indexes() -> set:
    import app.models  # noqa: F401 — 触发全部模型注册
    from app.core.database_indexes import EXTRA_INDEXES
    from app.models.base import Base

    # app.models 是懒加载入口：仅 import 不会注册具体表，需逐个 getattr 触发
    for name in getattr(app.models, "__all__", []):
        try:
            getattr(app.models, name)
        except Exception:
            pass

    names = set()
    for table in Base.metadata.tables.values():
        for idx in table.indexes:
            if idx.name:
                names.add(idx.name)
    for _t, iname, _c in EXTRA_INDEXES:
        names.add(iname)
    return names


def main():
    src = source_defined_indexes()
    db = _resolve_db()
    print("DB:", db)
    print(f"源码定义索引数: {len(src)}")

    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    live = []
    for t in tables:
        cur.execute(f'PRAGMA index_list("{t}")')
        for r in cur.fetchall():
            iname = r[1]
            if iname.startswith("sqlite_autoindex"):
                continue
            cur.execute(f'PRAGMA index_info("{iname}")')
            cols = [c[2] for c in cur.fetchall()]
            live.append((t, iname, cols))
    con.close()

    orphans = [(t, n, c) for (t, n, c) in live if n not in src]
    print(f"存活显式索引数: {len(live)}")
    print(f"\n=== 历史孤儿索引（可安全删除）: {len(orphans)} ===")
    for t, n, c in sorted(orphans):
        print(f'  DROP INDEX IF EXISTS "{n}";  -- {t}{list(c)}')


if __name__ == "__main__":
    main()
