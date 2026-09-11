"""P2-2 附件体系完善：新增 file_blobs 内容去重表

背景
----
三套上传实现各自落盘导致同一内容重复存储。新增 ``file_blobs`` 表以内容
SHA-256 为主键（内容寻址），配合引用计数实现「同内容复用物理存储 + 归零
回收」。表结构与 ``app.models.file_blob.FileBlob`` 严格对齐。

幂等与安全性
------------
- ``upgrade`` 使用 ``CREATE TABLE IF NOT EXISTS``，重复执行为 no-op；
- ``downgrade`` 使用 ``DROP TABLE IF EXISTS``，仅删除本表，不影响其它数据。

Revision ID: file_blob_001
Revises: index_dedup_001
"""
from alembic import op

revision = "file_blob_001"
down_revision = "index_dedup_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建 file_blobs 表（幂等）。"""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS file_blobs (
            sha256 VARCHAR(64) NOT NULL,
            path VARCHAR(500) NOT NULL,
            size INTEGER NOT NULL DEFAULT 0,
            ref_count INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (sha256)
        )
        """
    )


def downgrade() -> None:
    """删除 file_blobs 表（幂等）。"""
    op.execute("DROP TABLE IF EXISTS file_blobs")
