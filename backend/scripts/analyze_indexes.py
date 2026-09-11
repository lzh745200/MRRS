"""索引健康分析：统计索引、识别完全重复与冗余前缀索引。

只读，不修改任何数据/结构。输出候选清单供人工/迁移评估。
"""
import os
import sqlite3
from collections import defaultdict

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(_BACKEND_DIR, "data", "rural_revitalization.db")


def _resolve_db() -> str:
    """优先用应用配置解析数据库路径，回退到 backend/data 下的 db 文件。"""
    try:
        from app.core.config import settings

        url = settings.DATABASE_URL
        if url.startswith("sqlite:///"):
            p = url[len("sqlite:///"):]
            if os.path.exists(p):
                return p
    except Exception:
        pass
    if os.path.exists(DB):
        return DB
    data_dir = os.path.join(_BACKEND_DIR, "data")
    if os.path.isdir(data_dir):
        for f in os.listdir(data_dir):
            if f.endswith(".db"):
                return os.path.join(data_dir, f)
    return DB


def main():
    dB = _resolve_db()
    print("DB:", dB)
    con = sqlite3.connect(dB)
    cur = con.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    total_idx = 0
    per_table = {}
    idx_cols = {}  # (table, index_name) -> [cols]
    for t in tables:
        cur.execute(f'PRAGMA index_list("{t}")')
        rows = cur.fetchall()
        per_table[t] = len(rows)
        total_idx += len(rows)
        for r in rows:
            iname = r[1]
            cur.execute(f'PRAGMA index_info("{iname}")')
            cols = [c[2] for c in cur.fetchall()]
            idx_cols[(t, iname)] = cols

    print(f"tables={len(tables)} indexes={total_idx}")

    # 1) 完全重复：同表、同列序列、不同名字
    by_sig = defaultdict(list)
    for (t, iname), cols in idx_cols.items():
        by_sig[(t, tuple(cols))].append(iname)
    dup_groups = {k: v for k, v in by_sig.items() if len(v) > 1}

    # 2) 冗余前缀：索引 A 的列是索引 B 列的前缀（同表），则 A 冗余
    redundant = []
    per_table_cols = defaultdict(list)
    for (t, iname), cols in idx_cols.items():
        per_table_cols[t].append((iname, cols))
    for t, items in per_table_cols.items():
        for i, (n1, c1) in enumerate(items):
            for j, (n2, c2) in enumerate(items):
                if i == j or not c1:
                    continue
                if len(c1) < len(c2) and tuple(c2[: len(c1)]) == tuple(c1):
                    redundant.append((t, n1, c1, n2, c2))

    print(f"\n=== 完全重复索引组: {len(dup_groups)} ===")
    for (t, cols), names in sorted(dup_groups.items()):
        print(f"  {t} {cols} -> {names}")

    print(f"\n=== 冗余前缀索引: {len(redundant)} ===")
    for t, n1, c1, n2, c2 in redundant[:60]:
        print(f"  {t}: {n1}{c1} 被 {n2}{c2} 覆盖")

    con.close()


if __name__ == "__main__":
    main()
