"""政策 FTS5 全文检索 — 离线语义搜索 + 关键词高亮.

使用 SQLite FTS5 虚拟表实现全文索引，支持 BM25 排序和结果摘要。
"""
import logging
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.transaction import safe_commit

logger = logging.getLogger(__name__)

FTS_TABLE = "policies_fts"


def ensure_fts_table(db: Session) -> None:
    """确保 FTS5 虚拟表存在，若不存在则创建."""
    result = db.execute(text(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{FTS_TABLE}'"  # nosec B608
    )).fetchone()
    if result:
        return
    db.execute(text(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE}
        USING fts5(title, content, summary, keywords,
                   content='policies', content_rowid='id',
                   tokenize='unicode61')
    """))  # nosec B608
    # 同步已有数据
    db.execute(text(f"""
        INSERT INTO {FTS_TABLE}(rowid, title, content, summary, keywords)
        SELECT id, title, content, summary, keywords FROM policies
    """))  # nosec B608
    safe_commit(db)
    logger.info("FTS5 表 %s 已创建并同步", FTS_TABLE)


def search_policies_fts(
    db: Session,
    query: str,
    limit: int = 20,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """使用 FTS5 全文搜索政策.

    Args:
        db: 数据库会话
        query: 搜索关键词
        limit: 返回数量上限
        offset: 分页偏移

    Returns:
        [{"id": int, "title": str, "summary": str, "snippet": str, "rank": float}, ...]
    """
    ensure_fts_table(db)

    if not query or not query.strip():
        return []

    # FTS5 查询语法：用双引号包裹精确短语，否则分词匹配
    sanitized = query.strip().replace('"', '""')
    fts_query = f'"{sanitized}"' if " " in sanitized else sanitized

    sql = """
        SELECT p.id, p.title, p.summary, p.keywords, p.level, p.category,
               snippet({FTS_TABLE}, 1, '<mark>', '</mark>', '...', 32) AS snippet,
               bm25({FTS_TABLE}, 8.0, 10.0, 5.0) AS rank
        FROM {FTS_TABLE} f
        JOIN policies p ON p.id = f.rowid
        WHERE {FTS_TABLE} MATCH :query
        ORDER BY rank
        LIMIT :limit OFFSET :offset
    """  # nosec B608
    try:
        rows = db.execute(
            text(sql),
            {"query": fts_query, "limit": limit, "offset": offset},
        ).fetchall()
    except Exception as e:
        logger.warning("FTS5 搜索失败: %s, query=%s", e, sanitized)
        # Fallback: LIKE 搜索
        like = f"%{sanitized}%"
        rows = db.execute(
            text("""
                SELECT id, title, summary, keywords, level, category,
                       substr(summary, 1, 60) AS snippet, 0.0 AS rank
                FROM policies
                WHERE title LIKE :like OR summary LIKE :like OR keywords LIKE :like OR content LIKE :like
                LIMIT :limit OFFSET :offset
            """),
            {"like": like, "limit": limit, "offset": offset},
        ).fetchall()

    return [
        {
            "id": r[0],
            "title": r[1],
            "summary": r[2],
            "keywords": r[3],
            "level": r[4],
            "category": r[5],
            "snippet": r[6] or "",
            "rank": round(float(r[7]), 2) if r[7] else 0.0,
        }
        for r in rows
    ]


def sync_policy_to_fts(db: Session, policy_id: int) -> None:
    """将单条政策同步到 FTS 索引（创建/更新后调用）."""
    try:
        row = db.execute(
            text("SELECT id, title, content, summary, keywords FROM policies WHERE id = :id"),
            {"id": policy_id},
        ).fetchone()
        if not row:
            return
        # 先删除旧记录再插入（INSERT OR REPLACE 在 FTS5 中不支持）
        db.execute(text(f"DELETE FROM {FTS_TABLE} WHERE rowid = :id"), {"id": policy_id})  # nosec B608
        # nosec B608 — FTS_TABLE 为模块级常量（非用户输入），数据均经 :param 参数化绑定
        insert_sql = (
            f"INSERT INTO {FTS_TABLE}(rowid, title, content, summary, keywords)"
            " VALUES (:id, :title, :content, :summary, :keywords)"  # nosec B608
        )
        db.execute(
            text(insert_sql),  # nosec B608
            {"id": row[0], "title": row[1] or "", "content": row[2] or "",
             "summary": row[3] or "", "keywords": row[4] or ""},
        )
        safe_commit(db)
    except Exception:
        logger.warning("FTS同步失败 policy_id=%s（全文检索可能搜不到该政策）", policy_id, exc_info=True)


def remove_policy_from_fts(db: Session, policy_id: int) -> None:
    """从 FTS 索引中删除政策（删除后调用）."""
    try:
        db.execute(text(f"DELETE FROM {FTS_TABLE} WHERE rowid = :id"), {"id": policy_id})  # nosec B608
        safe_commit(db)
    except Exception:
        logger.warning("FTS删除失败 policy_id=%s（已删除政策可能仍可被搜索到）", policy_id, exc_info=True)
